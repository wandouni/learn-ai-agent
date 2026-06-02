# 文档知识库 MCP Server

用 Python 实现的 MCP Server，将 RAG 问答能力包装成工具，让 Claude Desktop 能直接用自然语言查询本地文档知识库。

## 工作原理

```
Claude Desktop
     ↓  MCP 协议（stdio）
server.py（MCP Server）
     ↓                    ↓
ChromaDB              documents/
（向量索引）          （PDF / TXT）
```

Server 启动时自动扫描 `documents/` 目录并建立向量索引；之后 Claude Desktop 连接后即可直接提问，无需任何手动预处理。

---

## 目录结构

```
knowledge-mcp/
├── server.py          # MCP Server 入口，暴露 3 个工具
├── indexer.py         # 文档读取、切块（500字/50字重叠）、向量化
├── retriever.py       # ChromaDB 检索与结果格式化
├── requirements.txt   # 依赖列表
├── documents/         # 放你的文档（PDF / TXT）
│   ├── 操作手册.txt   # 示例文档
│   └── 管理规定.txt   # 示例文档
└── chroma_db/         # ChromaDB 持久化目录（自动生成）
```

---

## 安装

**Python 版本要求：** 3.10+

```bash
cd knowledge-mcp
pip install -r requirements.txt
```

首次运行时 `sentence-transformers` 会自动下载 `paraphrase-multilingual-MiniLM-L12-v2` 模型（约 270MB），之后缓存在本地，无需重复下载。

---

## 本地测试

```bash
python3 server.py
```

启动日志示例：
```
[知识库] 正在索引：操作手册.txt …
[知识库] 完成：操作手册.txt（8 块）
[知识库] 正在索引：管理规定.txt …
[知识库] 完成：管理规定.txt（9 块）
```

已有索引的文档不会重复处理，直接进入监听状态。

---

## 接入 Claude Desktop

### 1. 修改配置文件

打开 `~/Library/Application Support/Claude/claude_desktop_config.json`，在 `mcpServers` 中添加：

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "python3",
      "args": [
        "/Users/shenni/repository/learn-ai-agent/rag/knowledge-mcp/server.py"
      ]
    }
  }
}
```

### 2. 重启 Claude Desktop

完全退出并重新打开 Claude Desktop，在工具栏看到 `knowledge` 服务器即表示连接成功。

### 3. 配置系统提示词（推荐）

在 Claude Desktop 的 Project 系统提示词中加入：

```
当用户提问涉及具体知识、规范、文档内容时，
优先调用 search_knowledge_base 工具检索后再回答。
如果检索结果中没有相关内容，明确告知用户
"知识库中未找到相关内容"，不要凭空推测。
回答时注明信息来源于哪份文档。
```

---

## 暴露的三个工具

### `list_documents`

列出知识库中已索引的所有文档。

- **入参：** 无
- **出参：** 文件名、切块数量、索引时间

**示例对话：**
> 用户：知识库里有哪些文档？
> → Claude 调用 `list_documents`，返回文件列表

---

### `search_knowledge_base`

在知识库中语义检索最相关的文本段落。

- **入参：**
  - `query`（字符串）：查询语句，支持中英文
  - `top_k`（整数，默认 3，最大 5）：返回段落数
- **出参：** 每段包含原文内容、来源文件名、块序号、相似度分数

**示例对话：**
> 用户：连续登录失败多少次会被锁定？
> → Claude 调用 `search_knowledge_base(query="登录失败锁定")`，找到操作手册相关段落后回答

---

### `add_document`

运行时动态添加新文档，无需重启 Server。

- **入参：**
  - `file_path`（字符串）：文档完整路径，支持 `.pdf` 和 `.txt`
- **出参：** 成功状态和新增切块数量

**示例对话：**
> 用户：帮我把 /Users/shenni/新合规政策.pdf 加进知识库
> → Claude 调用 `add_document`，完成索引后立刻可查询

---

## 添加自己的文档

直接把 PDF 或 TXT 文件放入 `documents/` 目录，下次重启 Server 时自动索引。

运行时添加无需重启，通过 `add_document` 工具指定路径即可。

---

## 技术选型

| 组件 | 选择 | 说明 |
|------|------|------|
| MCP 框架 | `mcp[cli]` (FastMCP) | 官方 SDK，协议兼容有保障 |
| 向量数据库 | ChromaDB | 纯本地持久化，无需部署额外服务 |
| Embedding 模型 | `paraphrase-multilingual-MiniLM-L12-v2` | 支持中文，本地运行，零成本 |
| 文档解析 | pdfplumber（PDF）/ 原生读取（TXT） | 轻量够用 |
| 切块策略 | 500 字，50 字重叠 | 平衡上下文完整性与检索精度 |
| 相似度度量 | 余弦相似度（cosine） | 对语义向量更鲁棒 |

> **注意：** 本项目不调用任何 LLM API，生成回答完全由 Claude Desktop 完成，Server 只负责检索和返回原文段落。

---

## 验收自查

| 场景 | 预期行为 |
|------|---------|
| 问"知识库里有哪些文档？" | Claude 调用 `list_documents`，列出文件名和切块数 |
| 问文档中有答案的具体问题 | Claude 调用 `search_knowledge_base`，回答准确并注明来源 |
| 问知识库完全没有的内容 | Claude 明确回答"知识库中未找到相关内容"，不推测 |
| 说"帮我把这份文档加进知识库" | Claude 调用 `add_document`，之后立刻可查询 |
