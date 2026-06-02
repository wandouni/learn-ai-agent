# indexer.py 逐段解读

> 这个文件只负责一件事：把文档变成可检索的向量存进 ChromaDB。
> 没有查询逻辑，没有工具注册，职责单一。

---

## 执行顺序总览

```
server.py 启动
    │
    ├─→ [模块加载] import indexer  ← 执行第 1~11 行（常量定义）
    │
    ├─→ get_or_create_collection()  ← 第 18 行
    │       └─→ _embedding_fn()     ← 第 14 行，加载 embedding 模型
    │
    └─→ index_document()            ← 第 60 行（有新文档时才调用）
            ├─→ _read()             ← 第 41 行
            │       ├─→ _read_pdf() ← 第 31 行（PDF）
            │       └─→ _read_txt() ← 第 26 行（TXT）
            ├─→ _chunk()            ← 第 50 行
            └─→ collection.upsert() ← 内部自动调用 _embedding_fn() 向量化
```

---

## 第 1~11 行：导入 + 常量

```python
import time
from pathlib import Path

import chromadb
import pdfplumber
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "knowledge_base"
```

**作用：** 模块加载时立即执行，定义全局常量。

| 常量 | 值 | 含义 |
|---|---|---|
| `CHUNK_SIZE` | 500 | 每个切块的最大字符数 |
| `CHUNK_OVERLAP` | 50 | 相邻切块之间重叠的字符数，防止语义在边界被截断 |
| `MODEL_NAME` | paraphrase-multilingual-MiniLM-L12-v2 | 向量化模型名，支持中文 |
| `COLLECTION_NAME` | knowledge_base | ChromaDB 集合名 |

`SentenceTransformerEmbeddingFunction` 是 ChromaDB 提供的包装器，把 sentence-transformers 的模型接入 ChromaDB 的自动向量化机制。

---

## 第 14~15 行：`_embedding_fn()`

```python
def _embedding_fn():
    return SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
```

**作用：** 构造向量化工具实例。

**什么时候执行：** 被 `get_or_create_collection()` 调用，server.py 启动时执行一次。

`SentenceTransformerEmbeddingFunction` 内部做了两件事：
1. 首次调用时下载并加载 `paraphrase-multilingual-MiniLM-L12-v2` 模型（约 270MB，之后缓存本地）
2. 返回一个可调用对象，接受文本列表，输出 384 维浮点向量列表

---

## 第 18~23 行：`get_or_create_collection()`

```python
def get_or_create_collection(client: chromadb.ClientAPI):
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )
```

**作用：** 获取或新建 ChromaDB 集合，把向量化函数绑定到集合上。

**什么时候执行：** server.py 第 23 行 `_collection = get_or_create_collection(_client)` 调用，程序启动时执行一次。

三个参数的意义：

- `name`：集合名称，相当于数据库里的"表名"
- `embedding_function`：绑定向量化工具。之后对这个集合调用 `upsert` 或 `query` 时，ChromaDB 会自动用它把文本转成向量，**你不需要手动调用向量化**
- `metadata={"hnsw:space": "cosine"}`：指定距离度量方式为余弦距离。余弦距离衡量两个向量的方向差异，对语义匹配效果更好；默认是 L2 欧氏距离

`get_or_create_collection` 的行为：
- 集合不存在 → 新建
- 集合已存在 → 直接返回，**不会清空数据**

---

## 第 26~28 行：`_read_txt()`

```python
def _read_txt(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()
```

**作用：** 读取 TXT 文件，返回全部文本内容。

**什么时候执行：** 被 `_read()` 分派调用，仅处理 `.txt` 文件。

`errors="ignore"` 的原因：部分文件可能包含非 UTF-8 字节（如 Windows 下另存的文件），忽略而不是报错，保证程序不中断。

---

## 第 31~38 行：`_read_pdf()`

```python
def _read_pdf(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)
```

**作用：** 用 pdfplumber 逐页提取 PDF 文本，拼接成完整字符串。

**什么时候执行：** 被 `_read()` 分派调用，仅处理 `.pdf` 文件。

逐页处理而不是一次性提取：部分页可能是图片或扫描件，`extract_text()` 返回 `None`，`if text` 过滤掉空页防止报错。

---

## 第 41~47 行：`_read()`

```python
def _read(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".txt":
        return _read_txt(path)
    raise ValueError(f"不支持的文件类型：{ext}（仅支持 .pdf 和 .txt）")
```

**作用：** 根据文件后缀分派到对应的读取函数，是统一入口。

**什么时候执行：** 被 `index_document()` 调用。

`Path(path).suffix.lower()` 先转小写再判断，防止 `.PDF`、`.TXT` 等大写后缀被漏掉。不支持的格式直接抛出 `ValueError`，由 `server.py` 的 `add_document` 工具捕获后返回错误信息。

---

## 第 50~57 行：`_chunk()`

```python
def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks
```

**作用：** 把长文本切成若干 500 字的小段，相邻段重叠 50 字。

**什么时候执行：** 被 `index_document()` 调用，读取文本之后。

切块示意：

```
原文：[...500字...]|[...500字...]|...
                    ↑
             重叠50字，防止一句话被切断后
             在两个块里都找不到完整语义
```

`start += CHUNK_SIZE - CHUNK_OVERLAP` 即每次前进 450 字（500 - 50），而不是 500 字，这样相邻块之间保留了 50 字的公共内容。

`.strip()` 去掉首尾空白；`if chunk` 过滤掉空块（文档末尾可能出现）。

---

## 第 60~77 行：`index_document()`

```python
def index_document(collection, file_path: str) -> int:
    filename = Path(file_path).name
    text = _read(file_path)
    chunks = _chunk(text)
    if not chunks:
        return 0

    timestamp = str(int(time.time()))
    collection.upsert(
        ids=[f"{filename}__{i}" for i in range(len(chunks))],
        documents=chunks,
        metadatas=[
            {"source": filename, "chunk_index": i, "indexed_at": timestamp}
            for i in range(len(chunks))
        ],
    )
    return len(chunks)
```

**作用：** 这是整个 indexer 的主函数，串联所有步骤，完成"读取 → 切块 → 向量化 → 存储"全流程。

**什么时候执行：** 两个地方调用：
1. server.py 启动时的 `_auto_index()`，为每个未索引文档调用一次
2. server.py 的 `add_document` 工具被 Claude 调用时

执行过程逐行：

| 行 | 做什么 |
|---|---|
| `filename = Path(file_path).name` | 只取文件名（去掉目录路径），用作 metadata 中的来源标识 |
| `text = _read(file_path)` | 读取原始文本 |
| `chunks = _chunk(text)` | 切成最多 500 字的段落列表 |
| `if not chunks: return 0` | 文档为空时提前返回，不写入 ChromaDB |
| `timestamp = str(int(time.time()))` | 当前 Unix 时间戳，记录索引时间 |
| `collection.upsert(...)` | 写入 ChromaDB，内部自动向量化 |
| `return len(chunks)` | 返回切块数量，让调用方知道索引了多少段 |

**upsert 的 ID 格式：** `操作手册.txt__0`、`操作手册.txt__1` … 用双下划线分隔文件名和序号，保证唯一性。upsert 语义是"有则覆盖，无则插入"，重复索引同一文件不会报错，会用新数据覆盖旧数据。

---

## 函数依赖关系

```
index_document()       ← 唯一对外公开的写入函数
    ├── _read()
    │     ├── _read_pdf()   pdfplumber
    │     └── _read_txt()   内置 open()
    └── _chunk()

get_or_create_collection()  ← 唯一对外公开的集合初始化函数
    └── _embedding_fn()     SentenceTransformerEmbeddingFunction
```

下划线开头的函数（`_read`、`_chunk` 等）是私有实现细节，只在文件内部使用。
