import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl

logger = logging.getLogger(__name__)

SECTION_MARKERS = {
    "本周完成事项": "completed",
    "本周关键指标": "metrics",
    "下周计划": "next_week",
    "风险与问题": "risks",
}


@dataclass
class Metric:
    name: str
    value: float
    mom_change: float  # absolute percentage, e.g., 5.2 means 5.2%
    mom_direction: str  # '上升' / '下降' / '持平'


@dataclass
class DepartmentReport:
    file_path: str
    dept_name: str
    period: str
    completed_items: list = field(default_factory=list)
    metrics: list = field(default_factory=list)
    next_week_plan: list = field(default_factory=list)
    risks: list = field(default_factory=list)


def _parse_mom(raw) -> tuple:
    """Parse MoM change string like '+8.3%', '-2.1%', '持平'.
    Returns (absolute_value: float, direction: str).
    """
    if raw is None:
        return 0.0, "持平"
    s = str(raw).strip().replace("%", "")
    if not s or s in ("持平", "-", "—"):
        return 0.0, "持平"
    try:
        val = float(s)
        if val > 0:
            return val, "上升"
        elif val < 0:
            return abs(val), "下降"
        return 0.0, "持平"
    except ValueError:
        return 0.0, "持平"


def _cell(row, col: int):
    """Safe column access with None guard."""
    return row[col] if col < len(row) else None


def extract_excel(file_path: str) -> tuple:
    """
    Parse one department Excel file.
    Returns (DepartmentReport, None) on success, (None, error_str) on failure.
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as exc:
        return None, f"无法打开文件: {exc}"

    dept_name = None
    period = None
    completed_items: list[str] = []
    metrics: list[Metric] = []
    next_week_plan: list[str] = []
    risks: list[str] = []

    current_section: Optional[str] = None
    metrics_header_skipped = False

    for row in rows:
        a = str(_cell(row, 0)).strip() if _cell(row, 0) is not None else ""
        b = _cell(row, 1)
        c = _cell(row, 2)

        # ── Basic info fields ──────────────────────────────────────────────
        if a == "部门名称":
            dept_name = str(b).strip() if b is not None else None
            continue
        if a == "汇报周期":
            period = str(b).strip() if b is not None else None
            continue

        # ── Section header detection ───────────────────────────────────────
        matched_section = None
        for marker, section in SECTION_MARKERS.items():
            if marker in a:
                matched_section = section
                break
        if matched_section:
            current_section = matched_section
            metrics_header_skipped = False
            continue

        # ── Skip blank rows ────────────────────────────────────────────────
        if not a and b is None:
            continue

        # ── Section content processing ─────────────────────────────────────
        if current_section == "completed":
            item = a.lstrip("-• ").strip()
            if item:
                completed_items.append(item)

        elif current_section == "metrics":
            # Always skip the first non-blank row (header: 指标名/数值/环比变化)
            if not metrics_header_skipped:
                metrics_header_skipped = True
                continue
            if not a:
                continue
            try:
                value = float(b) if b is not None else None
                if value is None:
                    raise ValueError("数值为空")
            except (ValueError, TypeError):
                return None, f"指标「{a}」的数值格式错误（得到: {b!r}）"
            mom_val, mom_dir = _parse_mom(c)
            metrics.append(Metric(name=a, value=value, mom_change=mom_val, mom_direction=mom_dir))

        elif current_section == "next_week":
            item = a.lstrip("-• ").strip()
            if item:
                next_week_plan.append(item)

        elif current_section == "risks":
            item = a.lstrip("-• ").strip()
            if item:
                risks.append(item)

    # ── Validation ─────────────────────────────────────────────────────────
    missing = []
    if not dept_name:
        missing.append("部门名称")
    if not period:
        missing.append("汇报周期")
    if not completed_items:
        missing.append("本周完成事项")
    if not next_week_plan:
        missing.append("下周计划")
    if missing:
        return None, "必填字段缺失: " + "、".join(missing)

    return DepartmentReport(
        file_path=file_path,
        dept_name=dept_name,
        period=period,
        completed_items=completed_items,
        metrics=metrics,
        next_week_plan=next_week_plan,
        risks=risks,
    ), None
