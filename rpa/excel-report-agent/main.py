"""
Excel 报表 AI 分析自动化 — 入口文件

用法:
  python main.py --run-now          # 立即执行一次
  python main.py --date 2025-W22   # 处理指定周期的文件
  python main.py --dry-run         # 只提取数据，不调用 DeepSeek
  python main.py                   # 启动定时任务（按 config.yaml 配置）
"""

import argparse
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

import schedule
import yaml

from analyzer import analyze_department, analyze_summary
from extractor import extract_excel
from notifier import notify_dingtalk, notify_email
from reporter import generate_report

logger = logging.getLogger(__name__)


# ── Config & logging ───────────────────────────────────────────────────────────

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(log_dir: str) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = os.path.join(log_dir, f"run_{date.today().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def current_iso_week() -> str:
    today = date.today()
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def scan_excels(excel_dir: str, date_filter: str | None) -> list[str]:
    p = Path(excel_dir)
    if not p.exists():
        logger.warning(f"Excel 目录不存在: {excel_dir}")
        return []
    files = sorted(p.glob("*.xlsx"))
    if date_filter:
        files = [f for f in files if date_filter in f.name]
    return [str(f) for f in files]


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run_pipeline(
    config: dict,
    date_filter: str | None = None,
    dry_run: bool = False,
) -> str | None:
    logger.info("=" * 60)
    logger.info(f"开始运行{'  [dry-run]' if dry_run else ''}")

    excel_dir = config["paths"]["excel_dir"]
    report_dir = config["paths"]["report_dir"]
    current_week = date_filter or current_iso_week()
    logger.info(f"目标周期: {current_week}")

    # ── 1. Scan ────────────────────────────────────────────────────────────
    files = scan_excels(excel_dir, date_filter)
    if not files:
        logger.warning("未找到可处理的 Excel 文件，退出")
        return None
    logger.info(f"发现 {len(files)} 个 Excel 文件")

    # ── 2. Extract ─────────────────────────────────────────────────────────
    dept_reports = []
    errors = []
    for fp in files:
        name = Path(fp).name
        report, err = extract_excel(fp)
        if err:
            logger.error(f"解析失败 [{name}]: {err}")
            errors.append({"file": name, "reason": err})
        else:
            logger.info(f"  √ {report.dept_name}  周期={report.period}")
            dept_reports.append(report)

    # ── 3. Dry-run: print & exit ───────────────────────────────────────────
    if dry_run:
        _print_dry_run(dept_reports, errors)
        return None

    if not dept_reports:
        logger.error("没有可分析的部门数据，退出")
        return None

    # ── 4. Analyse per department ──────────────────────────────────────────
    dept_analyses: dict[str, str] = {}
    deepseek_calls = 0
    for report in dept_reports:
        logger.info(f"分析: {report.dept_name}")
        try:
            dept_analyses[report.dept_name] = analyze_department(report, config)
            deepseek_calls += 1
        except Exception as exc:
            logger.error(f"单部门分析失败 [{report.dept_name}]: {exc}")
            dept_analyses[report.dept_name] = f"*分析调用失败: {exc}*"

    # ── 5. Cross-department summary ────────────────────────────────────────
    summary = ""
    if len(dept_reports) > 1:
        logger.info("生成跨部门汇总分析")
        try:
            summary = analyze_summary(dept_reports, config)
            deepseek_calls += 1
        except Exception as exc:
            logger.error(f"汇总分析失败: {exc}")
            summary = f"*汇总分析调用失败: {exc}*"
    else:
        summary = dept_analyses.get(dept_reports[0].dept_name, "")

    # ── 6. Determine report period ─────────────────────────────────────────
    periods = list({r.period for r in dept_reports})
    report_period = periods[0] if len(periods) == 1 else " / ".join(sorted(periods))

    # ── 7. Generate report ─────────────────────────────────────────────────
    report_path = generate_report(
        dept_reports=dept_reports,
        dept_analyses=dept_analyses,
        summary_analysis=summary,
        errors=errors,
        period=report_period,
        deepseek_calls=deepseek_calls,
        report_dir=report_dir,
    )

    # ── 8. Notify (optional) ───────────────────────────────────────────────
    notify_cfg = config.get("notify", {})
    if notify_cfg.get("enabled", False):
        channel = notify_cfg.get("channel", "dingtalk")
        if channel == "dingtalk":
            webhook = notify_cfg.get("dingtalk_webhook", "")
            if webhook:
                notify_dingtalk(webhook, summary, report_path)
            else:
                logger.warning("钉钉 Webhook 未配置，跳过推送")
        elif channel == "email":
            notify_email(config, report_path, len(dept_reports), report_period)

    logger.info("运行完成")
    return report_path


def _print_dry_run(dept_reports: list, errors: list) -> None:
    print("\n" + "=" * 60)
    print("【Dry-Run 模式 — 仅提取数据，不调用 DeepSeek，不生成报告】")
    print("=" * 60)
    for r in dept_reports:
        print(f"\n▶ 部门: {r.dept_name}  |  周期: {r.period}")
        print(f"  完成事项 ({len(r.completed_items)} 条):")
        for item in r.completed_items:
            print(f"    - {item}")
        if r.metrics:
            print(f"  关键指标 ({len(r.metrics)} 项):")
            for m in r.metrics:
                arrow = {"上升": "↑", "下降": "↓"}.get(m.mom_direction, "→")
                print(f"    - {m.name}: {m.value}  {arrow}{m.mom_change}%")
        print(f"  下周计划 ({len(r.next_week_plan)} 条):")
        for item in r.next_week_plan:
            print(f"    - {item}")
        if r.risks:
            print(f"  风险问题 ({len(r.risks)} 条):")
            for item in r.risks:
                print(f"    - {item}")
    if errors:
        print(f"\n⚠  解析失败文件 ({len(errors)} 个):")
        for e in errors:
            print(f"    [{e['file']}] {e['reason']}")
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Excel 报表 AI 分析自动化")
    parser.add_argument("--run-now", action="store_true", help="立即执行一次")
    parser.add_argument("--date", type=str, metavar="WEEK", help="处理指定周期文件，如 2025-W22")
    parser.add_argument("--dry-run", action="store_true", help="只提取数据，不调用 DeepSeek")
    parser.add_argument("--config", type=str, default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config["paths"].get("log_dir", "./logs"))

    if args.run_now or args.date or args.dry_run:
        run_pipeline(config, date_filter=args.date, dry_run=args.dry_run)
        return

    # ── Scheduled mode ─────────────────────────────────────────────────────
    weekday = config["schedule"]["weekday"]   # e.g. "monday"
    run_at = config["schedule"]["run_at"]     # e.g. "09:00"
    logger.info(f"定时模式启动，将于每{weekday} {run_at} 运行（Ctrl+C 退出）")

    getattr(schedule.every(), weekday).at(run_at).do(run_pipeline, config=config)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
