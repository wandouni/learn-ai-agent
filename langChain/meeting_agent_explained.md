# meeting_agent.py 代码讲解

本文解释 `meeting_agent.py` 的代码结构、执行流程和关键函数，帮助理解这个会议纪要整理 Agent 是如何工作的。

## 1. 程序目标

`meeting_agent.py` 接收一段会议记录文本，输出结构化会议纪要：

| 输出项 | 说明 |
|--------|------|
| 会议主题 | 本次会议讨论的核心主题 |
| 参会人 | 参会人员或从任务负责人中推断出的人员 |
| 关键结论 | 会议中形成的结论、风险、未确定事项 |
| 待办事项 | 每个任务的负责人、任务内容、截止时间 |
| 需要追问 | 信息不完整时，需要继续问用户的问题 |

程序有两种解析方式：

1. 优先使用 LangChain + DeepSeek 做结构化抽取。
2. 如果依赖缺失、没有 API Key 或模型调用失败，则自动回退到本地规则解析。

## 2. 整体执行流程

```text
命令行输入 / 文件输入 / 管道输入
        ↓
read_input()
        ↓
analyze_meeting()
        ↓
优先 analyze_with_langchain()
        ↓ 失败时回退
analyze_with_local_rules()
        ↓
MeetingExtraction 结构化结果
        ↓
format_report() 或 JSON 输出
```

入口函数是 `main()`。它负责解析命令行参数、读取输入、调用分析函数，并决定最终输出普通文本还是 JSON。

## 3. 数据结构

### TodoItem

```python
@dataclass
class TodoItem:
    owner: str = ""
    content: str = ""
    deadline: str = ""
```

`TodoItem` 表示一条待办事项：

| 字段 | 含义 |
|------|------|
| `owner` | 负责人 |
| `content` | 任务内容 |
| `deadline` | 截止时间 |

例如：

```python
TodoItem(owner="张三", content="整理页面指标", deadline="周五")
```

### MeetingExtraction

```python
@dataclass
class MeetingExtraction:
    topic: str = ""
    participants: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)
    todos: list[TodoItem] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    source: str = "local-rules"
```

`MeetingExtraction` 是最终的结构化结果。

| 字段 | 含义 |
|------|------|
| `topic` | 会议主题 |
| `participants` | 参会人列表 |
| `conclusions` | 关键结论列表 |
| `todos` | 待办事项列表 |
| `follow_up_questions` | 需要追问的问题 |
| `source` | 结果来源，可能是 `langchain-deepseek` 或 `local-rules` |

## 4. 文本预处理

### normalize_text()

```python
def normalize_text(text: str) -> str:
```

作用是清洗输入文本。

它主要做几件事：

1. 把 HTML 转义字符还原，例如 `&lt;` 变成 `<`。
2. 把 `<br>` 标签换成换行。
3. 删除其他 HTML 标签。
4. 合并多余空格和多余换行。
5. 去掉首尾空白。

这个函数是为了兼容用户直接从网页、聊天窗口或代码块里复制会议记录的情况。

### split_sentences()

```python
def split_sentences(text: str) -> list[str]:
```

作用是把会议记录拆成句子。

它根据中文和英文标点拆分：

```text
。 ！ ？ ; ；
```

拆句后，后面的主题抽取、待办抽取、结论抽取都会更简单。

## 5. 本地规则解析

本地规则解析由 `analyze_with_local_rules()` 统一调度。

```python
def analyze_with_local_rules(text: str) -> MeetingExtraction:
```

执行顺序是：

```text
normalize_text()
        ↓
split_sentences()
        ↓
extract_todos()
        ↓
extract_topic()
extract_participants()
extract_conclusions()
        ↓
build_follow_up_questions()
```

### extract_topic()

```python
def extract_topic(text: str, sentences: list[str]) -> str:
```

作用是抽取会议主题。

它会匹配几类常见表达：

```text
会议主题是……
主题为……
今天讨论了……
围绕……展开讨论
关于……进行讨论
```

示例：

```text
今天讨论了低碳调度系统的首页改版。
```

会提取为：

```text
低碳调度系统首页改版
```

如果没有匹配到明确主题，函数会使用第一句话的前 40 个字符作为兜底结果。

### clean_topic()

```python
def clean_topic(topic: str) -> str:
```

作用是清理主题里的标点和部分不自然表达。

例如：

```text
低碳调度系统的首页改版
```

会被整理成：

```text
低碳调度系统首页改版
```

### extract_participants()

```python
def extract_participants(text: str) -> list[str]:
```

作用是提取参会人。

它支持两种来源：

1. 显式参会人列表，例如 `参会人：张三、李四`。
2. 从任务负责人中推断，例如 `张三负责……`、`李四负责……`。

函数最后会去重，避免同一个人重复出现。

### extract_todos()

```python
def extract_todos(sentences: list[str]) -> list[TodoItem]:
```

作用是提取待办事项。

它重点识别这种句式：

```text
负责人 + 负责 + 任务内容 + 截止时间 + 前 + 后续动作
```

示例：

```text
李四负责补充碳排放趋势图，下周一前给出设计稿。
```

会抽取为：

```text
负责人：李四
任务内容：补充碳排放趋势图设计稿
截止时间：下周一
```

代码里的 `deadline_pattern` 用来识别常见截止时间：

```text
2026年6月7日
6月7日
本周五
下周一
周五
星期三
今天
明天
后天
月底
```

如果没有识别到截止时间，也会保留任务，但 `deadline` 为空，后面会生成追问。

### normalize_tail_object()

```python
def normalize_tail_object(tail: str) -> str:
```

这个函数处理截止时间后面的任务补充信息。

例如：

```text
下周一前给出设计稿
```

其中 `给出设计稿` 是任务内容的一部分。函数会去掉动作词 `给出`，保留 `设计稿`，最终拼回任务内容：

```text
补充碳排放趋势图设计稿
```

### extract_conclusions()

```python
def extract_conclusions(text: str, sentences: list[str], todos: list[TodoItem]) -> list[str]:
```

作用是生成关键结论。

它有两个来源：

1. 根据待办事项总结结论。
2. 从原文里识别风险、问题、未确定事项。

例如待办：

```text
张三负责整理页面指标
```

会总结为：

```text
首页需要补充指标展示。
```

例如问题：

```text
当前问题是数据接口还没有完全确定。
```

会整理为：

```text
数据接口仍未完全确定。
```

### todo_to_conclusion()

```python
def todo_to_conclusion(todo: TodoItem) -> str:
```

作用是把一条待办转换成一条会议结论。

例如：

| 待办内容 | 结论 |
|----------|------|
| 整理页面指标 | 首页需要补充指标展示。 |
| 补充碳排放趋势图设计稿 | 需要增加碳排放趋势图。 |
| 新增审批流程 | 需要新增审批流程。 |

这是一个规则化总结函数，用来让本地模式输出更接近会议纪要表达。

### build_follow_up_questions()

```python
def build_follow_up_questions(extraction: MeetingExtraction, text: str) -> list[str]:
```

作用是根据缺失信息生成追问。

它会检查：

1. 是否缺少会议主题。
2. 是否缺少参会人。
3. 每个待办是否缺少负责人。
4. 每个待办是否缺少截止时间。
5. 是否存在未确定事项但没有明确负责人。

示例：

```text
预算方案还没有完全确定。
```

会生成：

```text
预算方案由谁负责确认？
```

## 6. LangChain 解析

### analyze_with_langchain()

```python
def analyze_with_langchain(text: str) -> MeetingExtraction:
```

作用是使用 LangChain 调用 DeepSeek，让模型直接返回结构化结果。

它包含几个关键步骤。

### 第一步：延迟导入依赖

```python
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
```

这些依赖放在函数内部导入，而不是文件顶部导入。

原因是：即使用户没有安装 LangChain，程序仍然可以使用本地规则模式运行。

### 第二步：读取 API Key

```python
load_dotenv()
api_key = os.environ.get("DEEPSEEK_API_KEY")
```

程序会从 `.env` 或系统环境变量中读取 `DEEPSEEK_API_KEY`。

如果没有配置，就抛出 `RuntimeError`，交给外层回退到本地规则解析。

### 第三步：定义 Pydantic Schema

```python
class TodoSchema(BaseModel):
    owner: str
    content: str
    deadline: str

class MeetingSchema(BaseModel):
    topic: str
    participants: list[str]
    conclusions: list[str]
    todos: list[TodoSchema]
    follow_up_questions: list[str]
```

Schema 的作用是告诉模型必须输出什么字段。

这比让模型直接输出自由文本更稳定，也方便程序后续处理。

### 第四步：构造 Prompt

```python
prompt = ChatPromptTemplate.from_messages(...)
```

系统提示词强调了几个约束：

1. 只依据原文。
2. 不编造负责人、截止时间或参会人。
3. 信息缺失时必须生成追问。

这些约束是为了减少模型幻觉。

### 第五步：调用 DeepSeek

```python
llm = ChatOpenAI(
    model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=api_key,
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    temperature=0,
).with_structured_output(MeetingSchema)
```

这里使用 `ChatOpenAI` 是因为 DeepSeek API 兼容 OpenAI 风格接口。

`temperature=0` 表示降低随机性，让输出更稳定。

`with_structured_output(MeetingSchema)` 表示要求模型按照 `MeetingSchema` 返回结构化数据。

### 第六步：转换为统一数据结构

```python
return MeetingExtraction(...)
```

LangChain 返回的是 Pydantic 对象，代码会把它转换成 `MeetingExtraction`。

这样无论结果来自 LangChain 还是本地规则，后面的输出逻辑都可以共用。

## 7. 回退机制

### analyze_meeting()

```python
def analyze_meeting(text: str, prefer_langchain: bool = True) -> MeetingExtraction:
```

这是统一入口。

默认情况下：

```text
先尝试 LangChain
失败后打印提示
再使用本地规则解析
```

如果命令行传入 `--local`，则不调用 LangChain，直接使用本地规则。

这种设计的好处是：

1. 有 API Key 时，可以使用大模型获得更强的理解能力。
2. 没有 API Key 时，课堂演示和基础测试仍然能跑。
3. 输出结构始终一致，方便后续接 Web、接口或测试。

## 8. 输出格式

### format_report()

```python
def format_report(extraction: MeetingExtraction) -> str:
```

作用是把结构化对象转成用户可读的会议纪要文本。

输出格式类似：

```text
会议主题：
低碳调度系统首页改版

参会人：
张三、李四

关键结论：
1. 首页需要补充指标展示。

待办事项：
1. 张三：整理页面指标，截止时间：周五。

需要追问：
数据接口由谁负责确认？
```

### extraction_to_dict()

```python
def extraction_to_dict(extraction: MeetingExtraction) -> dict[str, Any]:
```

作用是把 dataclass 对象转换为字典。

这个函数主要服务于 `--json` 输出。

## 9. 输入处理

### read_input()

```python
def read_input(args: argparse.Namespace) -> str:
```

支持三种输入方式：

| 输入方式 | 示例 |
|----------|------|
| 命令行参数 | `python3 meeting_agent.py "会议文本"` |
| 文件输入 | `python3 meeting_agent.py --file meeting.txt` |
| 管道输入 | `cat meeting.txt | python3 meeting_agent.py` |

如果没有任何输入，会使用代码里的 `SAMPLE_TEXT` 示例文本。

## 10. 命令行入口

### main()

```python
def main() -> None:
```

`main()` 做四件事：

1. 定义命令行参数。
2. 读取会议记录文本。
3. 调用 `analyze_meeting()`。
4. 根据参数输出普通文本或 JSON。

支持的参数：

| 参数 | 说明 |
|------|------|
| `text` | 直接传入会议记录文本 |
| `-f, --file` | 从文件读取会议记录 |
| `--local` | 强制使用本地规则，不调用 LangChain |
| `--json` | 输出 JSON |

## 11. 示例运行

### 使用本地规则运行

```bash
python3 meeting_agent.py --local
```

### 使用 LangChain + DeepSeek

```bash
cp .env.example .env
pip3 install -r requirements.txt
python3 meeting_agent.py
```

### 输出 JSON

```bash
python3 meeting_agent.py --local --json
```

## 12. 代码设计重点

这个文件的核心设计不是只调用大模型，而是做了一个稳定的双路径方案：

1. `LangChain 路径` 负责更强的语义理解。
2. `本地规则路径` 负责无依赖、可演示、可兜底。
3. 两条路径最终都返回 `MeetingExtraction`，保证输出层不用关心数据来源。

这种结构适合教学项目，也适合继续扩展成 Web 服务或 API。

## 13. 可扩展方向

后续可以继续扩展：

1. 增加单元测试，固定典型会议记录的输出。
2. 支持更多时间表达，例如 `下周三下午`、`6月中旬`。
3. 把 `MeetingExtraction` 暴露为 FastAPI 接口。
4. 把追问问题接入多轮对话，让用户补全缺失信息。
5. 增加 Markdown、Excel 或飞书文档导出。
