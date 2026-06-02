# learn-ai-agent

AI Agent 实践合集，涵盖 Function Calling、MCP Server、RAG 检索增强和 RPA 自动化四个方向，全部基于 DeepSeek / Claude + Python 实现。

---

## 项目结构

```
learn-ai-agent/
├── aiagent/          # 天气播报 Agent（Function Calling）
├── mcpServer/        # SQLite 查询 MCP Server
├── rag/
│   └── knowledge-mcp/  # 文档知识库 MCP Server（RAG）
└── rpa/
    └── excel-report-agent/  # Excel 报表 AI 分析自动化
```

---

## 各模块简介

### 1. 天气播报 Agent `aiagent/`

用 **DeepSeek Function Calling** 实现多工具协调的对话 Agent：自动调用天气 API + AQI 接口，综合判断"今天适合跑步吗"之类的复合问题。

**技术点：** Function Calling、多轮工具调用、对话状态管理

---

### 2. SQLite 查询 MCP Server `mcpServer/`

将本地 SQLite 数据库的查询能力封装为 **MCP Server**，接入 Claude Desktop 后可用自然语言查数据，写操作（INSERT/UPDATE/DELETE）在工具层拦截。

**暴露工具：** `list_tables` · `describe_table` · `run_query`

---

### 3. 文档知识库 MCP Server `rag/knowledge-mcp/`

**RAG + MCP** 融合实现：Server 启动时自动扫描并向量化本地 PDF/TXT 文档，将检索能力暴露给 Claude Desktop，支持运行时动态追加文档。

**技术栈：** ChromaDB · sentence-transformers（中文 Embedding）· FastMCP  
**暴露工具：** `list_documents` · `search_knowledge_base` · `add_document`

---

### 4. Excel 报表 AI 分析自动化 `rpa/excel-report-agent/`

**RPA × DeepSeek** 工作流：定时扫描部门周报 Excel，提取结构化数据，批量调用 DeepSeek 生成分析摘要，输出 Markdown 报告，可选推送钉钉群或邮件。

**技术点：** 定时任务、Excel 解析、Prompt 工程、钉钉 Webhook / SMTP 推送

---

## 技术栈概览

| 模块 | 核心技术 |
|------|---------|
| aiagent | DeepSeek API · Function Calling |
| mcpServer | MCP (FastMCP) · SQLite |
| knowledge-mcp | ChromaDB · sentence-transformers · MCP |
| excel-report-agent | DeepSeek API · openpyxl · schedule |

---

## 快速上手

每个子模块均有独立 `README.md`，进入对应目录查看详细说明：

```bash
# 以 Excel 报表 Agent 为例
cd rpa/excel-report-agent
pip install -r requirements.txt
python3 create_sample_data.py
python3 main.py --run-now
```
