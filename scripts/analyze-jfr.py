#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path
from collections import defaultdict


def parse_duration(duration_str):
    """Parse ISO 8601 duration string (e.g., 'PT0.008921627S') to milliseconds."""
    if not duration_str or not isinstance(duration_str, str):
        return 0.0
    match = re.match(r"PT([\d.]+)S", duration_str)
    if match:
        return float(match.group(1)) * 1000.0
    return 0.0


def run_jfr_command(jfr_file, event_type, timeout=10):
    """Run jfr command and return parsed output."""
    try:
        result = subprocess.run(
            ["jfr", "print", "--events", event_type, "--json", str(jfr_file)],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        if not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        # Handle both direct events array and nested recording.events structure
        if isinstance(data, dict):
            return data.get("recording", {}).get("events", [])
        return data if isinstance(data, list) else []
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, subprocess.TimeoutExpired):
        return []


def analyze_cpu_usage(jfr_file):
    """Analyze CPU usage from JFR."""
    events = run_jfr_command(jfr_file, "jdk.CPULoad")
    if not events:
        return None

    total_cpu = sum(e.get("values", {}).get("machineTotal", 0) for e in events)
    jvm_cpu = sum(
        e.get("values", {}).get("jvmUser", 0) + e.get("values", {}).get("jvmSystem", 0)
        for e in events
    )
    count = len(events)

    return {
        "avg_machine_cpu": (total_cpu / count * 100) if count > 0 else 0,
        "avg_jvm_cpu": (jvm_cpu / count * 100) if count > 0 else 0,
    }


def analyze_memory(jfr_file):
    """Analyze memory usage from JFR."""
    events = run_jfr_command(jfr_file, "jdk.GCHeapSummary")
    if not events:
        return None

    heap_used = [
        e.get("values", {}).get("heapUsed", 0)
        for e in events
        if "heapUsed" in e.get("values", {})
    ]
    if not heap_used:
        return None

    return {
        "max_heap_mb": max(heap_used) / (1024 * 1024),
        "avg_heap_mb": sum(heap_used) / len(heap_used) / (1024 * 1024),
    }


def analyze_gc(jfr_file):
    """Analyze GC statistics from JFR."""
    events = run_jfr_command(jfr_file, "jdk.GarbageCollection")
    if not events:
        return None

    total_pause = sum(
        parse_duration(e.get("values", {}).get("sumOfPauses")) for e in events
    )
    longest_pause = max(
        (parse_duration(e.get("values", {}).get("longestPause")) for e in events),
        default=0,
    )

    return {
        "gc_count": len(events),
        "total_pause_ms": total_pause,
        "longest_pause_ms": longest_pause,
    }


def analyze_compilation(jfr_file):
    """Analyze JIT compilation from JFR."""
    events = run_jfr_command(jfr_file, "jdk.Compilation")
    if not events:
        return None

    return {
        "compilation_count": len(events),
        "total_compilation_ms": sum(
            parse_duration(e.get("values", {}).get("duration")) for e in events
        ),
    }


def format_metric(value, unit=""):
    """Format metric value."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}{unit}"
    return f"{value}{unit}"


def extract_matrix_key(jfr_filename):
    """Extract engine-phase key from artifact filename pattern."""
    import re
    match = re.search(r'jfr-results-([^-]+)-([^-]+)-', jfr_filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return "unknown"


def aggregate_metrics(metrics_list):
    """Aggregate multiple metrics into summary statistics."""
    if not metrics_list:
        return None

    valid_metrics = [m for m in metrics_list if m is not None]
    if not valid_metrics:
        return None

    result = {}
    for key in valid_metrics[0].keys():
        values = [m[key] for m in valid_metrics if key in m and m[key] is not None]
        if values:
            result[f"avg_{key}"] = sum(values) / len(values)
            result[f"max_{key}"] = max(values)
            result[f"min_{key}"] = min(values)

    return result


def generate_report(jfr_files, output_path, max_files_per_group=10):
    """Generate JFR analysis report grouped by matrix (engine-phase)."""
    lines = ["# JFR 性能分析报告", ""]

    if not jfr_files:
        lines.append("未找到 JFR 文件。")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    grouped_files = defaultdict(list)
    for jfr_file in jfr_files:
        parent_dir = jfr_file.parent.name
        matrix_key = extract_matrix_key(parent_dir)
        grouped_files[matrix_key].append(jfr_file)

    lines.extend([
        f"找到 {len(jfr_files)} 个 JFR 文件，按矩阵分组为 {len(grouped_files)} 个类别。",
        f"每个类别采样最多 {max_files_per_group} 个文件进行分析。",
        "",
    ])

    matrix_results = {}

    for matrix_key in sorted(grouped_files.keys()):
        files = grouped_files[matrix_key]
        sampled = files[:max_files_per_group]

        cpu_metrics = []
        memory_metrics = []
        gc_metrics = []
        compilation_metrics = []

        for jfr_file in sampled:
            cpu_metrics.append(analyze_cpu_usage(jfr_file))
            memory_metrics.append(analyze_memory(jfr_file))
            gc_metrics.append(analyze_gc(jfr_file))
            compilation_metrics.append(analyze_compilation(jfr_file))

        matrix_results[matrix_key] = {
            "cpu": aggregate_metrics(cpu_metrics),
            "memory": aggregate_metrics(memory_metrics),
            "gc": aggregate_metrics(gc_metrics),
            "compilation": aggregate_metrics(compilation_metrics),
            "sample_count": len(sampled),
            "total_count": len(files),
        }

    lines.extend([
        "## CPU 使用率",
        "",
        "| 引擎-阶段 | 平均机器 CPU | 平均 JVM CPU | 样本数 |",
        "|---|---:|---:|---:|",
    ])

    for matrix_key in sorted(matrix_results.keys()):
        data = matrix_results[matrix_key]
        cpu = data.get("cpu")
        if cpu:
            lines.append(
                f"| {matrix_key} "
                f"| {format_metric(cpu.get('avg_avg_machine_cpu'), '%')} "
                f"| {format_metric(cpu.get('avg_avg_jvm_cpu'), '%')} "
                f"| {data['sample_count']}/{data['total_count']} |"
            )

    lines.extend([
        "",
        "## 内存使用",
        "",
        "| 引擎-阶段 | 平均最大堆 | 平均堆使用 | 样本数 |",
        "|---|---:|---:|---:|",
    ])

    for matrix_key in sorted(matrix_results.keys()):
        data = matrix_results[matrix_key]
        memory = data.get("memory")
        if memory:
            lines.append(
                f"| {matrix_key} "
                f"| {format_metric(memory.get('avg_max_heap_mb'), ' MB')} "
                f"| {format_metric(memory.get('avg_avg_heap_mb'), ' MB')} "
                f"| {data['sample_count']}/{data['total_count']} |"
            )

    lines.extend([
        "",
        "## GC 统计",
        "",
        "| 引擎-阶段 | 平均 GC 次数 | 平均总暂停 | 平均最长暂停 | 样本数 |",
        "|---|---:|---:|---:|---:|",
    ])

    for matrix_key in sorted(matrix_results.keys()):
        data = matrix_results[matrix_key]
        gc = data.get("gc")
        if gc:
            lines.append(
                f"| {matrix_key} "
                f"| {format_metric(gc.get('avg_gc_count'))} "
                f"| {format_metric(gc.get('avg_total_pause_ms'), ' ms')} "
                f"| {format_metric(gc.get('avg_longest_pause_ms'), ' ms')} "
                f"| {data['sample_count']}/{data['total_count']} |"
            )

    lines.extend([
        "",
        "## JIT 编译",
        "",
        "| 引擎-阶段 | 平均编译次数 | 平均总编译时间 | 样本数 |",
        "|---|---:|---:|---:|",
    ])

    for matrix_key in sorted(matrix_results.keys()):
        data = matrix_results[matrix_key]
        compilation = data.get("compilation")
        if compilation:
            lines.append(
                f"| {matrix_key} "
                f"| {format_metric(compilation.get('avg_compilation_count'))} "
                f"| {format_metric(compilation.get('avg_total_compilation_ms'), ' ms')} "
                f"| {data['sample_count']}/{data['total_count']} |"
            )

    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="分析 JFR 文件并生成报告")
    parser.add_argument(
        "--input",
        required=True,
        help="JFR 文件目录",
    )
    parser.add_argument(
        "--output",
        default="build/reports/jfr/analysis.md",
        help="报告输出路径",
    )
    parser.add_argument(
        "--max-files-per-group",
        type=int,
        default=10,
        help="每个矩阵组最大分析文件数（默认 10）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    jfr_files = sorted(input_path.rglob("*.jfr")) if input_path.is_dir() else []
    generate_report(jfr_files, output_path, args.max_files_per_group)


if __name__ == "__main__":
    main()
