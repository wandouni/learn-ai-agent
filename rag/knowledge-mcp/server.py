import os
import sys

# 确保同目录下的模块可以被正确导入（无论从哪里启动 server）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

import chromadb
from mcp.server.fastmcp import FastMCP

from indexer import get_or_create_collection, index_document
from retriever import list_documents as _list_documents
from retriever import search as _search

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "documents"
CHROMA_DIR = BASE_DIR / "chroma_db"

mcp = FastMCP("文档知识库")

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = get_or_create_collection(_client)


def _auto_index() -> None:
    """启动时自动索引 documents/ 目录下尚未入库的文档。"""
    DOCS_DIR.mkdir(exist_ok=True)

    existing_meta = _collection.get(include=["metadatas"])["metadatas"] or []
    indexed = {m["source"] for m in existing_meta}

    supported = {".pdf", ".txt"}
    for path in sorted(DOCS_DIR.iterdir()):
        if path.suffix.lower() in supported and path.name not in indexed:
            print(f"[知识库] 正在索引：{path.name} …", flush=True)
            n = index_document(_collection, str(path))
            print(f"[知识库] 完成：{path.name}（{n} 块）", flush=True)


@mcp.tool()
def list_documents() -> str:
    """列出知识库中已索引的所有文档，包括文件名、切块数量和索引时间。"""
    return _list_documents(_collection)


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """在知识库中检索与查询语句最相关的文本段落。

    Args:
        query: 查询语句（支持中英文）
        top_k: 返回段落数量，默认 3，最大 5
    """
    return _search(_collection, query, top_k)


@mcp.tool()
def add_document(file_path: str) -> str:
    """将新文档实时添加到知识库，无需重启服务。

    Args:
        file_path: 文档的完整路径（支持 .pdf 和 .txt）
    """
    if not os.path.isfile(file_path):
        return f"错误：文件不存在：{file_path}"
    try:
        n = index_document(_collection, file_path)
        name = Path(file_path).name
        return f"成功：已将《{name}》索引为 {n} 个切块，现在可以立即查询。"
    except ValueError as e:
        return f"错误：{e}"
    except Exception as e:
        return f"索引失败：{e}"


if __name__ == "__main__":
    _auto_index()
    mcp.run(transport="stdio")
