import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


def _fmt_report(report) -> str:
    """Serialize a DepartmentReport to human-readable text for the prompt."""
    lines = [
        f"部门：{report.dept_name}",
        f"周期：{report.period}",
    ]
    if report.metrics:
        lines.append("\n关键指标：")
        for m in report.metrics:
            arrow = {"上升": "↑", "下降": "↓"}.get(m.mom_direction, "→")
            lines.append(f"  - {m.name}：{m.value}（{arrow}{m.mom_change}%）")
    if report.completed_items:
        lines.append("\n本周完成：")
        lines.extend(f"  - {x}" for x in report.completed_items)
    if report.next_week_plan:
        lines.append("\n下周计划：")
        lines.extend(f"  - {x}" for x in report.next_week_plan)
    if report.risks:
        lines.append("\n风险与问题：")
        lines.extend(f"  - {x}" for x in report.risks)
    return "\n".join(lines)


def _call(prompt: str, config: dict) -> str:
    client = OpenAI(
        api_key=config["deepseek"]["api_key"],
        base_url="https://api.deepseek.com",
    )
    resp = client.chat.completions.create(
        model=config["deepseek"]["model"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def analyze_department(report, config: dict) -> str:
    prompt = (
        f"你是一位企业经营分析助手。以下是【{report.dept_name}】{report.period}的工作周报数据，"
        "请用专业、简洁的语言生成一段分析摘要（300字以内）。\n\n"
        "要求：\n"
        "1. 先给出一句整体评价\n"
        "2. 重点说明指标异常（环比下降超过10%需特别指出）\n"
        "3. 风险问题如有则必须提及\n"
        "4. 语气客观，不要过度夸奖\n\n"
        f"数据：\n{_fmt_report(report)}"
    )
    logger.debug("单部门 prompt 已构造，调用 DeepSeek")
    return _call(prompt, config)


def analyze_summary(reports: list, config: dict) -> str:
    all_data = "\n\n".join(_fmt_report(r) for r in reports)
    prompt = (
        "你是一位企业经营分析助手。以下是本周各部门汇报数据的汇总，"
        "请生成一份给管理层的周报摘要（500字以内）。\n\n"
        "要求：\n"
        "1. 开头给出本周整体判断（一句话）\n"
        "2. 列出表现突出的部门和需要关注的部门，各不超过2个，说明理由\n"
        "3. 提炼2-3条全公司层面的共性洞察\n"
        "4. 结尾给出下周重点关注事项\n\n"
        f"数据：\n{all_data}"
    )
    logger.debug("汇总 prompt 已构造，调用 DeepSeek")
    return _call(prompt, config)
