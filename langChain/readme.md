# 会议纪要整理 Agent

基于 LangChain + DeepSeek 的会议记录整理示例。输入一段会议文本，自动抽取会议主题、参会人、关键结论、待办事项，并对缺失信息生成追问。

## 功能

| 功能 | 说明 |
|------|------|
| 会议主题抽取 | 识别本次会议讨论的核心主题 |
| 参会人抽取 | 从显式参会人列表或任务负责人中识别人名 |
| 关键结论整理 | 汇总需要补充、确认、未确定的关键信息 |
| 待办拆分 | 抽取负责人、任务内容、截止时间 |
| 自动追问 | 对缺失负责人、截止时间、未决事项负责人等信息生成问题 |

## 快速开始

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2. 配置 DeepSeek API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY
```

未配置 API Key 时，程序会自动回退到本地规则解析，示例仍可运行。

### 3. 运行示例

```bash
python3 meeting_agent.py
```

### 4. 输入自定义会议记录

```bash
python3 meeting_agent.py "今天讨论了低碳调度系统的首页改版。张三负责整理页面指标，周五前完成。李四负责补充碳排放趋势图，下周一前给出设计稿。当前问题是数据接口还没有完全确定。"
```

也可以通过管道或文件输入：

```bash
cat meeting.txt | python3 meeting_agent.py
python3 meeting_agent.py --file meeting.txt
```

## 输出示例

```text
会议主题：
低碳调度系统首页改版

参会人：
张三、李四

关键结论：
1. 首页需要补充指标展示。
2. 需要增加碳排放趋势图。
3. 数据接口仍未完全确定。

待办事项：
1. 张三：整理页面指标，截止时间：周五。
2. 李四：补充碳排放趋势图设计稿，截止时间：下周一。

需要追问：
数据接口由谁负责确认？
```

## JSON 输出

如果要接入 Web 页面或后端接口，可以使用结构化输出：

```bash
python3 meeting_agent.py --json --local
```

输出字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `topic` | string | 会议主题 |
| `participants` | string[] | 参会人 |
| `conclusions` | string[] | 关键结论 |
| `todos` | object[] | 待办事项列表 |
| `follow_up_questions` | string[] | 需要追问的问题 |
| `source` | string | 解析来源：`langchain-deepseek` 或 `local-rules` |

## 文件说明

```text
langChain/
├── meeting_agent.py   # Agent 主程序
├── requirements.txt   # LangChain 依赖
├── .env.example       # 环境变量示例
├── task.md            # 需求说明
└── readme.md          # 使用说明
```

## 实现说明

程序采用两级策略：

1. 默认优先调用 LangChain，通过 `with_structured_output` 让 DeepSeek 按 Pydantic Schema 返回结构化结果。
2. 如果依赖未安装、未配置 API Key 或模型调用失败，自动使用本地规则解析，保证基础演示可运行。

强制使用本地规则：

```bash
python3 meeting_agent.py --local
```
