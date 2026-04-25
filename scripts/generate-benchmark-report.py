#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path
from collections import defaultdict


def load_jmh_summary(jmh_report_path):
    """Extract key metrics from JMH report."""
    if not jmh_report_path.exists():
        return None

    content = jmh_report_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    summary = {
        "fastest_engines": defaultdict(list),
        "total_tests": 0,
    }

    current_phase = None
    current_case = None

    for line in lines:
        if line.startswith("## ") and "测试" in line:
            current_phase = line.replace("##", "").strip()
        elif line.startswith("### "):
            current_case = line.replace("###", "").strip()
        elif line.startswith("| 1 |") and current_phase and current_case:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) > 2:
                engine = parts[2]
                summary["fastest_engines"][current_phase].append(
                    {"case": current_case, "engine": engine}
                )
                summary["total_tests"] += 1

    return summary


def load_jfr_summary(jfr_report_path):
    """Extract key metrics from JFR report."""
    if not jfr_report_path.exists():
        return None

    content = jfr_report_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    summary = {
        "cpu_data": [],
        "memory_data": [],
        "gc_data": [],
    }

    section = None
    for line in lines:
        if "## CPU 使用率" in line:
            section = "cpu"
        elif "## 内存使用" in line:
            section = "memory"
        elif "## GC 统计" in line:
            section = "gc"
        elif line.startswith("|") and section and not line.startswith("| 测试"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) > 2 and parts[1]:
                if section == "cpu":
                    summary["cpu_data"].append(parts[1])
                elif section == "memory":
                    summary["memory_data"].append(parts[1])
                elif section == "gc":
                    summary["gc_data"].append(parts[1])

    return summary


def generate_executive_summary(jmh_summary, jfr_summary):
    """Generate executive summary section."""
    lines = ["## 执行摘要", ""]

    if jmh_summary:
        lines.append(f"- 完成测试用例: {jmh_summary['total_tests']} 个")

        engine_wins = defaultdict(int)
        for phase_results in jmh_summary["fastest_engines"].values():
            for result in phase_results:
                engine_wins[result["engine"]] += 1

        if engine_wins:
            top_engine = max(engine_wins.items(), key=lambda x: x[1])
            lines.append(
                f"- 性能最优引擎: {top_engine[0]} (在 {top_engine[1]} 个测试中最快)"
            )

    if jfr_summary:
        if jfr_summary["cpu_data"]:
            lines.append(f"- JFR 分析覆盖: {len(jfr_summary['cpu_data'])} 个测试")

    lines.append("")
    return lines


def generate_performance_highlights(jmh_summary):
    """Generate performance highlights section."""
    if not jmh_summary:
        return []

    lines = ["## 性能亮点", ""]

    for phase, results in jmh_summary["fastest_engines"].items():
        if results:
            lines.extend([f"### {phase}", ""])
            engine_counts = defaultdict(int)
            for result in results:
                engine_counts[result["engine"]] += 1

            sorted_engines = sorted(
                engine_counts.items(), key=lambda x: x[1], reverse=True
            )
            for engine, count in sorted_engines[:3]:
                lines.append(f"- **{engine}**: 在 {count} 个测试中表现最佳")
            lines.append("")

    return lines


def generate_resource_analysis(jfr_summary):
    """Generate resource usage analysis section."""
    if not jfr_summary or not jfr_summary["cpu_data"]:
        return []

    lines = ["## 资源使用分析", ""]

    if jfr_summary["memory_data"]:
        lines.extend([
            "### 内存使用",
            "",
            f"- 分析了 {len(jfr_summary['memory_data'])} 个测试的内存使用情况",
            "- 详细数据请参考 JFR 分析报告",
            "",
        ])

    if jfr_summary["gc_data"]:
        lines.extend([
            "### GC 性能",
            "",
            f"- 分析了 {len(jfr_summary['gc_data'])} 个测试的 GC 行为",
            "- 详细数据请参考 JFR 分析报告",
            "",
        ])

    return lines


def generate_recommendations(jmh_summary, jfr_summary):
    """Generate recommendations section."""
    lines = ["## 建议", ""]

    if jmh_summary:
        engine_wins = defaultdict(int)
        for phase_results in jmh_summary["fastest_engines"].values():
            for result in phase_results:
                engine_wins[result["engine"]] += 1

        if engine_wins:
            sorted_engines = sorted(
                engine_wins.items(), key=lambda x: x[1], reverse=True
            )
            top_engine = sorted_engines[0]
            lines.extend([
                f"1. **推荐引擎**: {top_engine[0]} 在大多数测试场景中表现最佳",
                "",
            ])

    if jfr_summary and jfr_summary["gc_data"]:
        lines.extend([
            "2. **性能优化**: 查看 JFR 分析报告中的 GC 统计，识别潜在的内存优化机会",
            "",
        ])

    lines.extend([
        "3. **持续监控**: 建议在生产环境中持续监控关键性能指标",
        "",
    ])

    return lines


def main():
    parser = argparse.ArgumentParser(description="生成综合基准测试报告")
    parser.add_argument(
        "--jmh-report",
        default="build/reports/jmh/report.md",
        help="JMH 报告路径",
    )
    parser.add_argument(
        "--jfr-report",
        default="build/reports/jfr/analysis.md",
        help="JFR 分析报告路径",
    )
    parser.add_argument(
        "--output",
        default="build/reports/benchmark-report.md",
        help="输出报告路径",
    )
    parser.add_argument("--matrix-json", default="", help="测试矩阵 JSON")
    parser.add_argument("--jmh-args", default="", help="JMH 参数")
    parser.add_argument("--enable-jfr", default="false", help="是否启用 JFR")
    args = parser.parse_args()

    jmh_report_path = Path(args.jmh_report)
    jfr_report_path = Path(args.jfr_report)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    jmh_summary = load_jmh_summary(jmh_report_path)
    jfr_summary = (
        load_jfr_summary(jfr_report_path) if args.enable_jfr == "true" else None
    )

    lines = [
        "# 脚本引擎基准测试报告",
        "",
        f"生成时间: {dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()}",
        "",
    ]

    lines.extend(generate_executive_summary(jmh_summary, jfr_summary))
    lines.extend(generate_performance_highlights(jmh_summary))
    lines.extend(generate_resource_analysis(jfr_summary))
    lines.extend(generate_recommendations(jmh_summary, jfr_summary))

    lines.extend([
        "---",
        "",
        "## 测试配置",
        "",
        f"- JMH 参数: `{args.jmh_args or '默认参数'}`",
        f"- JFR 启用: `{args.enable_jfr}`",
    ])

    if args.matrix_json:
        try:
            matrix = json.loads(args.matrix_json)
            lines.extend([
                "",
                "### 测试矩阵",
                "",
                "```json",
                json.dumps(matrix, indent=2, ensure_ascii=False),
                "```",
            ])
        except json.JSONDecodeError:
            pass

    lines.extend([
        "",
        "---",
        "",
        "## 详细报告",
        "",
        "- [JMH 性能测试详细报告](jmh/report.md)",
    ])

    if args.enable_jfr == "true":
        lines.append("- [JFR 性能分析详细报告](jfr/analysis.md)")

    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
