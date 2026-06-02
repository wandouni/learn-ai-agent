import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def notify_dingtalk(webhook_url: str, summary: str, report_path: str) -> bool:
    """Push executive summary to a DingTalk group via custom robot webhook."""
    excerpt = summary[:450] + "…" if len(summary) > 450 else summary
    text = f"📊 周报分析摘要\n\n{excerpt}\n\n📄 完整报告：{Path(report_path).name}"
    payload = {"msgtype": "text", "text": {"content": text}}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("errcode", -1) == 0:
            logger.info("钉钉推送成功")
            return True
        logger.error(f"钉钉推送被拒: {result}")
        return False
    except Exception as exc:
        logger.error(f"钉钉推送异常: {exc}")
        return False


def notify_email(config: dict, report_path: str, dept_count: int, period: str) -> bool:
    """Send the full Markdown report via SMTP."""
    cfg = config["notify"]
    smtp_host = cfg["smtp_host"]
    smtp_port = int(cfg.get("smtp_port", 465))
    smtp_user = cfg["smtp_user"]
    smtp_password = cfg["smtp_password"]
    email_from = cfg.get("email_from") or smtp_user
    email_to: list = cfg["email_to"]

    subject = f"【周报分析】{period} — 共 {dept_count} 个部门"

    with open(report_path, encoding="utf-8") as f:
        body = f.read()

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(email_from, email_to, msg.as_string())
        logger.info(f"邮件已发送至 {email_to}")
        return True
    except Exception as exc:
        logger.error(f"邮件发送失败: {exc}")
        return False
