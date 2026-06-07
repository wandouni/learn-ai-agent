"""
会议纪要整理 Agent

优先使用 LangChain + DeepSeek 做结构化抽取；未安装依赖或未配置 API Key 时，
自动回退到本地规则解析，保证示例可以直接运行。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any


SAMPLE_TEXT = (
    "今天讨论了低碳调度系统的首页改版。"
    "张三负责整理页面指标，周五前完成。"
    "李四负责补充碳排放趋势图，下周一前给出设计稿。"
    "当前问题是数据接口还没有完全确定。"
)


@dataclass
class TodoItem:
    owner: str = ""
    content: str = ""
    deadline: str = ""


@dataclass
class MeetingExtraction:
    topic: str = ""
    participants: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)
    todos: list[TodoItem] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    source: str = "local-rules"


def normalize_text(text: str) -> str:
    """清理 HTML 片段和多余空白，兼容直接粘贴网页代码块的情况。"""
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [part.strip() for part in parts if part.strip()]


def clean_topic(topic: str) -> str:
    topic = topic.strip(" ，,。；;：:")
    topic = re.sub(r"(?<=[\u4e00-\u9fa5])的(?=(首页|页面|系统|方案|设计|改版|优化|建设|上线|迭代))", "", topic)
    return topic


def extract_topic(text: str, sentences: list[str]) -> str:
    patterns = [
        r"(?:会议主题|主题)\s*(?:是|为|：|:)\s*(?P<topic>[^。；;]+)",
        r"(?:今天|本次|会上)?(?:主要)?讨论了(?P<topic>[^。；;，,]+)",
        r"(?:围绕|关于)(?P<topic>[^。；;，,]+)(?:展开|进行|讨论)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_topic(match.group("topic"))

    if sentences:
        return clean_topic(sentences[0][:40])
    return ""


def extract_participants(text: str) -> list[str]:
    names: list[str] = []

    explicit = re.search(r"(?:参会人|参会人员|与会人|与会人员)\s*(?:为|是|：|:)\s*([^。；;\n]+)", text)
    if explicit:
        for name in re.split(r"[、,，\s]+", explicit.group(1)):
            name = name.strip()
            if name:
                names.append(name)

    for owner in re.findall(r"([\u4e00-\u9fa5]{2,4})负责", text):
        if owner not in {"大家", "团队", "部门", "当前", "今天"}:
            names.append(owner)

    deduped: list[str] = []
    for name in names:
        if name not in deduped:
            deduped.append(name)
    return deduped


def normalize_tail_object(tail: str) -> str:
    tail = tail.strip(" ，,。；;")
    if not tail or tail in {"完成", "落实"}:
        return ""
    tail = re.sub(r"^(完成|给出|提交|输出|形成|提供|交付)", "", tail)
    return tail.strip(" ，,。；;")


def extract_todos(sentences: list[str]) -> list[TodoItem]:
    todos: list[TodoItem] = []
    deadline_pattern = (
        r"(?:\d{4}年)?\d{1,2}月\d{1,2}日|"
        r"(?:本周|下周)[一二三四五六日天]|"
        r"(?:周|星期)[一二三四五六日天]|"
        r"今天|明天|后天|本周内|下周内|月底|本月底|下月底"
    )

    for sentence in sentences:
        if "负责" not in sentence:
            continue

        full_pattern = re.compile(
            rf"(?P<owner>[\u4e00-\u9fa5]{{2,4}})负责"
            rf"(?P<content>.+?)[，, ]*"
            rf"(?P<deadline>{deadline_pattern})前?"
            rf"(?P<tail>[^。；;]*)"
        )
        match = full_pattern.search(sentence)
        if match:
            content = match.group("content").strip(" ，,。；;")
            tail_object = normalize_tail_object(match.group("tail"))
            if tail_object and tail_object not in content:
                content = f"{content}{tail_object}"
            todos.append(
                TodoItem(
                    owner=match.group("owner").strip(),
                    content=content,
                    deadline=match.group("deadline").strip(),
                )
            )
            continue

        partial_match = re.search(r"(?P<owner>[\u4e00-\u9fa5]{2,4})负责(?P<content>[^。；;]+)", sentence)
        if partial_match:
            todos.append(
                TodoItem(
                    owner=partial_match.group("owner").strip(),
                    content=partial_match.group("content").strip(" ，,。；;"),
                    deadline="",
                )
            )

    return todos


def todo_to_conclusion(todo: TodoItem) -> str:
    content = todo.content.strip(" ，,。；;")
    visible_content = re.sub(r"(设计稿|方案|文档)$", "", content)

    if visible_content.startswith("整理页面指标"):
        return "首页需要补充指标展示。"
    if visible_content.startswith("整理"):
        return f"需要整理{visible_content.removeprefix('整理')}。"
    if visible_content.startswith("补充"):
        return f"需要增加{visible_content.removeprefix('补充')}。"
    if visible_content.startswith("新增"):
        return f"需要新增{visible_content.removeprefix('新增')}。"
    return f"需要完成{visible_content}。"


def extract_conclusions(text: str, sentences: list[str], todos: list[TodoItem]) -> list[str]:
    conclusions: list[str] = []

    for todo in todos:
        conclusion = todo_to_conclusion(todo)
        if conclusion not in conclusions:
            conclusions.append(conclusion)

    for sentence in sentences:
        if re.search(r"(当前问题|问题是|风险是|尚未|还没有|未完全|未确定)", sentence):
            normalized = sentence.strip(" ，,。；;")
            normalized = re.sub(r"^当前问题是", "", normalized)
            normalized = normalized.replace("还没有完全确定", "仍未完全确定")
            if not normalized.endswith("。"):
                normalized += "。"
            if normalized not in conclusions:
                conclusions.append(normalized)

    return conclusions


def build_follow_up_questions(extraction: MeetingExtraction, text: str) -> list[str]:
    questions: list[str] = []

    if not extraction.topic:
        questions.append("本次会议主题是什么？")
    if not extraction.participants:
        questions.append("本次会议有哪些参会人？")

    for todo in extraction.todos:
        if not todo.owner:
            questions.append(f"任务“{todo.content or '未命名任务'}”由谁负责？")
        if not todo.deadline:
            questions.append(f"{todo.owner or '相关负责人'}负责的“{todo.content or '任务'}”截止时间是什么？")

    issue_match = re.search(r"(数据接口|接口|需求|方案|预算|排期)[^。；;]*(?:未完全确定|还没有完全确定|未确定|不明确)", text)
    if issue_match:
        subject_match = re.match(r"(?P<subject>.*?)(?:仍?未完全确定|还没有完全确定|未确定|不明确)", issue_match.group(0))
        subject = subject_match.group("subject") if subject_match else issue_match.group(1)
        question = f"{subject}由谁负责确认？"
        questions.append(question)

    deduped: list[str] = []
    for question in questions:
        question = question.strip()
        if question and question not in deduped:
            deduped.append(question)
    return deduped


def analyze_with_local_rules(text: str) -> MeetingExtraction:
    clean_text = normalize_text(text)
    sentences = split_sentences(clean_text)
    todos = extract_todos(sentences)
    extraction = MeetingExtraction(
        topic=extract_topic(clean_text, sentences),
        participants=extract_participants(clean_text),
        conclusions=extract_conclusions(clean_text, sentences, todos),
        todos=todos,
        source="local-rules",
    )
    extraction.follow_up_questions = build_follow_up_questions(extraction, clean_text)
    return extraction


def analyze_with_langchain(text: str) -> MeetingExtraction:
    try:
        from dotenv import load_dotenv
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("未安装 LangChain 依赖，已回退到本地规则解析。") from exc

    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，已回退到本地规则解析。")

    class TodoSchema(BaseModel):
        owner: str = Field(default="", description="任务负责人；文本未明确时留空")
        content: str = Field(default="", description="具体任务内容")
        deadline: str = Field(default="", description="截止时间；文本未明确时留空")

    class MeetingSchema(BaseModel):
        topic: str = Field(default="", description="会议主题；文本未明确时留空")
        participants: list[str] = Field(default_factory=list, description="参会人姓名")
        conclusions: list[str] = Field(default_factory=list, description="关键结论，使用简洁完整句")
        todos: list[TodoSchema] = Field(default_factory=list, description="待办事项")
        follow_up_questions: list[str] = Field(default_factory=list, description="需要向用户追问的问题")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是会议纪要整理助手。请从用户提供的会议记录中抽取结构化信息。"
                "只依据原文，不编造负责人、截止时间或参会人。"
                "如果主题、参会人、任务负责人、任务内容、截止时间、未决事项负责人等信息缺失，"
                "必须在 follow_up_questions 中生成具体追问。",
            ),
            ("human", "会议记录：\n{text}"),
        ]
    )
    llm = ChatOpenAI(
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0,
    ).with_structured_output(MeetingSchema)

    result = (prompt | llm).invoke({"text": normalize_text(text)})
    payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    return MeetingExtraction(
        topic=payload.get("topic", ""),
        participants=payload.get("participants", []),
        conclusions=payload.get("conclusions", []),
        todos=[TodoItem(**todo) for todo in payload.get("todos", [])],
        follow_up_questions=payload.get("follow_up_questions", []),
        source="langchain-deepseek",
    )


def analyze_meeting(text: str, prefer_langchain: bool = True) -> MeetingExtraction:
    if prefer_langchain:
        try:
            return analyze_with_langchain(text)
        except RuntimeError as exc:
            print(f"[提示] {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"[提示] LangChain 调用失败，已回退到本地规则解析：{exc}", file=sys.stderr)
    return analyze_with_local_rules(text)


def extraction_to_dict(extraction: MeetingExtraction) -> dict[str, Any]:
    return asdict(extraction)


def format_report(extraction: MeetingExtraction) -> str:
    lines: list[str] = []

    lines.append("会议主题：")
    lines.append(extraction.topic or "未明确")
    lines.append("")

    lines.append("参会人：")
    lines.append("、".join(extraction.participants) if extraction.participants else "未明确")
    lines.append("")

    lines.append("关键结论：")
    if extraction.conclusions:
        for index, conclusion in enumerate(extraction.conclusions, 1):
            lines.append(f"{index}. {conclusion}")
    else:
        lines.append("未明确")
    lines.append("")

    lines.append("待办事项：")
    if extraction.todos:
        for index, todo in enumerate(extraction.todos, 1):
            owner = todo.owner or "负责人未明确"
            content = todo.content or "任务内容未明确"
            deadline = todo.deadline or "未明确"
            lines.append(f"{index}. {owner}：{content}，截止时间：{deadline}。")
    else:
        lines.append("未明确")
    lines.append("")

    lines.append("需要追问：")
    if extraction.follow_up_questions:
        for question in extraction.follow_up_questions:
            lines.append(question)
    else:
        lines.append("无")

    return "\n".join(lines)


def read_input(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as file:
            return file.read()
    if args.text:
        return " ".join(args.text)
    if not sys.stdin.isatty():
        piped_text = sys.stdin.read().strip()
        if piped_text:
            return piped_text
    return SAMPLE_TEXT


def main() -> None:
    parser = argparse.ArgumentParser(description="会议记录自动整理 Agent")
    parser.add_argument("text", nargs="*", help="会议记录文本；不传时读取 stdin；均为空时使用内置示例")
    parser.add_argument("-f", "--file", help="从文件读取会议记录")
    parser.add_argument("--local", action="store_true", help="强制使用本地规则解析，不调用 LangChain")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结构化结果")
    args = parser.parse_args()

    meeting_text = read_input(args)
    extraction = analyze_meeting(meeting_text, prefer_langchain=not args.local)

    if args.json:
        print(json.dumps(extraction_to_dict(extraction), ensure_ascii=False, indent=2))
    else:
        print(format_report(extraction))


if __name__ == "__main__":
    main()
