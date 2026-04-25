#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
from collections import defaultdict


def run_jfr_command(jfr_file, event_type):
    """Run jfr command and return parsed output."""
    try:
        result = subprocess.run(
            ["jfr", "print", "--events", event_type, "--json", str(jfr_file)],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else {"events": []}
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return {"events": []}


def analyze_cpu_usage(jfr_file):
    """Analyze CPU usage from JFR."""
    data = run_jfr_command(jfr_file, "jdk.CPULoad")
    events = data.get("events", [])
    if not events:
        return None

    total_cpu = sum(e.get("machineTotal", 0) for e in events)
    jvm_cpu = sum(e.get("jvmUser", 0) + e.get("jvmSystem", 0) for e in events)
    count = len(events)

    return {
        "avg_machine_cpu": (total_cpu / count * 100) if count > 0 else 0,
        "avg_jvm_cpu": (jvm_cpu / count * 100) if count > 0 else 0,
    }


def analyze_memory(jfr_file):
    """Analyze memory usage from JFR."""
    data = run_jfr_command(jfr_file, "jdk.GCHeapSummary")
    events = data.get("events", [])
    if not events:
        return None

    heap_used = [e.get("heapUsed", 0) for e in events if "heapUsed" in e]
    if not heap_used:
        return None

    return {
        "max_heap_mb": max(heap_used) / (1024 * 1024),
        "avg_heap_mb": sum(heap_used) / len(heap_used) / (1024 * 1024),
    }


def analyze_gc(jfr_file):
    """Analyze GC statistics from JFR."""
    data = run_jfr_command(jfr_file, "jdk.GarbageCollection")
    events = data.get("events", [])
    if not events:
        return None

    total_pause = sum(e.get("sumOfPauses", 0) for e in events)
    longest_pause = max((e.get("longestPause", 0) for e in events), default=0)

    return {
        "gc_count": len(events),
        "total_pause_ms": total_pause / 1_000_000,
        "longest_pause_ms": longest_pause / 1_000_000,
    }


def analyze_compilation(jfr_file):
    """Analyze JIT compilation from JFR."""
    data = run_jfr_command(jfr_file, "jdk.Compilation")
    events = data.get("events", [])
    if not events:
        return None

    return {
        "compilation_count": len(events),
        "total_compilation_ms": sum(e.get("duration", 0) for e in events) / 1_000_000,
    }


def format_metric(value, unit=""):
    """Format metric value."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}{unit}"
    return f"{value}{unit}"


def generate_report(jfr_files, output_path):
    """Generate JFR analysis report."""
    lines = ["# JFR 性能分析报告", ""]

    if not jfr_files:
        lines.append("未找到 JFR 文件。")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    results = defaultdict(dict)

    for jfr_file in jfr_files:
        name = jfr_file.stem
        results[name]["cpu"] = analyze_cpu_usage(jfr_file)
        results[name]["memory"] = analyze_memory(jfr_file)
        results[name]["gc"] = analyze_gc(jfr_file)
        results[name]["compilation"] = analyze_compilation(jfr_file)

    lines.extend([
        f"分析了 {len(jfr_files)} 个 JFR 文件。",
        "",
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
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    jfr_files = sorted(input_path.glob("*.jfr")) if input_path.is_dir() else []
    generate_report(jfr_files, output_path)


if __name__ == "__main__":
    main()
