
## 项目定义

**名称：** 文档知识库 MCP Server

**一句话目标：** 用 Python 实现一个 MCP Server，把 RAG 问答能力包装成工具，让 Claude Desktop 能直接用自然语言查询你的本地文档知识库。

---

## 背景：为什么要融合

单独的 RAG 系统需要用户主动去跑脚本提问，而 MCP Server 让 Claude Desktop 成为交互入口——用户在 Claude Desktop 里聊天，Claude 自动判断什么时候需要查知识库、查什么、怎么整合结果回答。两者融合之后，RAG 从一个独立脚本变成了 Claude 的一项能力。

---

## 系统边界

```
Claude Desktop
     ↓  MCP 协议（stdio）
MCP Server（你写的 Python 程序）
     ↓                    ↓
ChromaDB              本地文档目录
（向量索引）          （PDF / TXT）
```

文档索引在 Server 启动时自动完成，Claude Desktop 连上来之后直接可以提问，无需手动跑任何预处理脚本。

---

## 两个阶段

### 阶段一：Server 启动时自动索引

Server 启动时检查 ChromaDB 是否已有索引：

* 有：直接加载，跳过索引
* 没有：扫描指定文档目录，自动完成以下流程

```
读取文档 → 按500字切块（50字重叠）→ embedding向量化 → 存入ChromaDB
```

每个存储单元包含：向量、原文内容、来源文件名、块序号。

索引完成后 Server 进入监听状态，等待 Claude Desktop 调用工具。

### 阶段二：Claude Desktop 发起查询

用户在 Claude Desktop 提问 → Claude 判断需要查知识库 → 调用 MCP 工具 → Server 执行检索 → 返回结果 → Claude 整合生成回答。

---

## 对外暴露的工具（Tools）

MCP Server 暴露 3 个工具：

**工具一：list_documents**

* 入参：无
* 出参：当前知识库中已索引的文档列表（文件名、切块数量、索引时间）
* 用途：让 Claude 先了解知识库里有哪些文档，避免查不到时瞎猜

**工具二：search_knowledge_base**

* 入参：`query`（查询语句，字符串）、`top_k`（返回段落数，默认3，最大5）
* 出参：最相关的若干文本块，每块包含原文内容、来源文件名、段落序号、相似度分数
* 用途：核心检索工具，Claude 拿到结果后自己整合成回答

**工具三：add_document**

* 入参：`file_path`（文档路径，字符串）
* 出参：成功/失败状态、新增的切块数量
* 用途：运行时动态添加新文档，不需要重启 Server

---

## Prompt 约定

这部分不在 MCP Server 里实现，而是写在 Claude Desktop 的系统提示词里：

```
当用户提问涉及具体知识、规范、文档内容时，
优先调用 search_knowledge_base 工具检索后再回答。
如果检索结果中没有相关内容，明确告知用户
"知识库中未找到相关内容"，不要凭空推测。
回答时注明信息来源于哪份文档。
```

---

## 技术选型

| 组件           | 选择                                             | 理由                       |
| -------------- | ------------------------------------------------ | -------------------------- |
| MCP 框架       | mcp-python-sdk                                   | 官方 SDK，协议兼容有保障   |
| 向量数据库     | ChromaDB                                         | 纯本地，无需部署额外服务   |
| Embedding 模型 | sentence-transformers（paraphrase-multilingual） | 支持中文，本地运行，零成本 |
| 文档解析       | pdfplumber（PDF）/ 原生读取（TXT）               | 轻量够用                   |
| MCP 客户端     | Claude Desktop                                   | 唯一要求，免费下载         |

注意：这个项目 **不调用 DeepSeek** ，生成回答是 Claude Desktop 自己做的，你的 Server 只负责检索和返回原文段落。

---

## 目录结构

```
knowledge-mcp/
├── server.py          # MCP Server 主程序，入口
├── indexer.py         # 文档读取、切块、向量化逻辑
├── retriever.py       # ChromaDB 检索逻辑
├── documents/         # 放你的文档（PDF / TXT）
│   ├── 操作手册.pdf
│   └── 管理规定.txt
└── chroma_db/         # ChromaDB 自动生成，不需要手动创建
```

---

## 验收标准

**基础验收：**

> 在 Claude Desktop 问"知识库里有哪些文档？"
> → Claude 调用 list_documents，列出文件名和切块数

**核心验收：**

> 问一个只在某份文档里有答案的问题
> → Claude 调用 search_knowledge_base，检索到正确段落，回答准确并注明来源

**边界验收：**

> 问一个所有文档都没有的内容
> → Claude 明确回答"知识库中未找到相关内容"，不瞎编

**动态更新验收：**

> 在对话中说"帮我把这份新文档加进知识库"并提供路径
> → Claude 调用 add_document，Server 完成索引，之后立刻可以查询新文档内容

---

## 不做的事

* 不做 Web UI 和 HTTP 接口
* 不做用户权限管理
* 不做文档删除功能
* 不做关键词+向量的混合检索
* 不保存对话历史

---

## 后续可延伸的方向

这个项目跑通后，把 `documents/` 目录换成你们公司实际的文档，把 ChromaDB 换成支持持久化的生产级向量库（比如 Qdrant），就是一个可以真正落地的企业知识库系统。也可以再加一个工具接入 SQLite，把项目②的数据查询能力一并合并进来，Claude Desktop 就同时具备了"查文档"和"查数据"两种能力。

要开始写代码了吗？
