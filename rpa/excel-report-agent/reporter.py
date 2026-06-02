import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _metrics_table(metrics: list) -> str:
    if not metrics:
        return ""
    rows = ["| 指标名 | 数值 | 环比变化 |", "| --- | --- | --- |"]
    for m in metrics:
        arrow = {"上升": "↑", "下降": "↓"}.get(m.mom_direction, "→")
        sign = "+" if m.mom_direction == "上升" else ("-" if m.mom_direction == "下降" else "")
        rows.append(f"| {m.name} | {m.value} | {arrow} {sign}{m.mom_change}% |")
    return "\n".join(rows)


def generate_report(
    dept_reports: list,
    dept_analyses: dict,
    summary_analysis: str,
    errors: list,
    period: str,
    deepseek_calls: int,
    report_dir: str,
) -> str:
    """Write Markdown report to report_dir. Returns the file path."""
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_period = period.replace("/", "-")
    file_path = os.path.join(report_dir, f"weekly_report_{safe_period}_{timestamp}.md")

    blocks: list[str] = []

    # ── Title ──────────────────────────────────────────────────────────────
    blocks.append(f"# 周报分析 · {period}\n")

    # ── Executive summary ──────────────────────────────────────────────────
    blocks.append("## 执行摘要\n")
    blocks.append(summary_analysis or "*（暂无汇总分析）*")
    blocks.append("")

    # ── Per-department ─────────────────────────────────────────────────────
    blocks.append("## 各部门分析\n")
    for report in dept_reports:
        blocks.append(f"### {report.dept_name}\n")
        blocks.append(dept_analyses.get(report.dept_name, "*（分析失败）*"))
        blocks.append("")
        tbl = _metrics_table(report.metrics)
        if tbl:
            blocks.append("**指标概览**\n")
            blocks.append(tbl)
            blocks.append("")

    # ── Error records ──────────────────────────────────────────────────────
    blocks.append("## 数据异常记录\n")
    if errors:
        for err in errors:
            blocks.append(f"- **{err['file']}**：{err['reason']}")
    else:
        blocks.append("*本次运行无数据异常。*")
    blocks.append("")

    # ── Footer ─────────────────────────────────────────────────────────────
    blocks.append("## 生成信息\n")
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    blocks.append(
        f"生成时间：{gen_time}　"
        f"处理文件数：{len(dept_reports)}　"
        f"调用DeepSeek次数：{deepseek_calls}"
    )

    content = "\n".join(blocks)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"报告已写入: {file_path}")
    return file_path
