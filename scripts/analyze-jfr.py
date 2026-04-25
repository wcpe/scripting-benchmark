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


def generate_report(jfr_files, output_path, max_files=20):
    """Generate JFR analysis report."""
    lines = ["# JFR 性能分析报告", ""]

    if not jfr_files:
        lines.append("未找到 JFR 文件。")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    total_files = len(jfr_files)
    if total_files > max_files:
        import random
        sampled_files = random.sample(jfr_files, max_files)
        lines.extend([
            f"找到 {total_files} 个 JFR 文件，随机采样 {max_files} 个进行分析。",
            "",
        ])
    else:
        sampled_files = jfr_files
        lines.extend([
            f"分析 {total_files} 个 JFR 文件。",
            "",
        ])

    results = defaultdict(dict)

    for jfr_file in sampled_files:
        name = jfr_file.stem
        results[name]["cpu"] = analyze_cpu_usage(jfr_file)
        results[name]["memory"] = analyze_memory(jfr_file)
        results[name]["gc"] = analyze_gc(jfr_file)
        results[name]["compilation"] = analyze_compilation(jfr_file)

    lines.extend([
        "## CPU 使用率",
        "",
        "| 测试 | 平均机器 CPU | 平均 JVM CPU |",
        "|---|---:|---:|",
    ])

    for name, data in sorted(results.items()):
        cpu = data.get("cpu")
        if cpu:
            lines.append(
                f"| {name} "
                f"| {format_metric(cpu['avg_machine_cpu'], '%')} "
                f"| {format_metric(cpu['avg_jvm_cpu'], '%')} |"
            )

    lines.extend([
        "",
        "## 内存使用",
        "",
        "| 测试 | 最大堆内存 | 平均堆内存 |",
        "|---|---:|---:|",
    ])

    for name, data in sorted(results.items()):
        memory = data.get("memory")
        if memory:
            lines.append(
                f"| {name} "
                f"| {format_metric(memory['max_heap_mb'], ' MB')} "
                f"| {format_metric(memory['avg_heap_mb'], ' MB')} |"
            )

    lines.extend([
        "",
        "## GC 统计",
        "",
        "| 测试 | GC 次数 | 总暂停时间 | 最长暂停 |",
        "|---|---:|---:|---:|",
    ])

    for name, data in sorted(results.items()):
        gc = data.get("gc")
        if gc:
            lines.append(
                f"| {name} "
                f"| {format_metric(gc['gc_count'])} "
                f"| {format_metric(gc['total_pause_ms'], ' ms')} "
                f"| {format_metric(gc['longest_pause_ms'], ' ms')} |"
            )

    lines.extend([
        "",
        "## JIT 编译",
        "",
        "| 测试 | 编译次数 | 总编译时间 |",
        "|---|---:|---:|",
    ])

    for name, data in sorted(results.items()):
        compilation = data.get("compilation")
        if compilation:
            lines.append(
                f"| {name} "
                f"| {format_metric(compilation['compilation_count'])} "
                f"| {format_metric(compilation['total_compilation_ms'], ' ms')} |"
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
        "--max-files",
        type=int,
        default=20,
        help="最大分析文件数（默认 20）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    jfr_files = sorted(input_path.rglob("*.jfr")) if input_path.is_dir() else []
    generate_report(jfr_files, output_path, args.max_files)


if __name__ == "__main__":
    main()
