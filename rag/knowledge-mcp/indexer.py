import time
from pathlib import Path

import chromadb
import pdfplumber
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "knowledge_base"


def _embedding_fn():
    return SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)


def get_or_create_collection(client: chromadb.ClientAPI):
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def _read_txt(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _read(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".txt":
        return _read_txt(path)
    raise ValueError(f"不支持的文件类型：{ext}（仅支持 .pdf 和 .txt）")


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def index_document(collection, file_path: str) -> int:
    """读取文档、切块、向量化并存入 ChromaDB，返回切块数量。"""
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
