from datetime import datetime


def list_documents(collection) -> str:
    """返回知识库中所有已索引文档的摘要信息。"""
    result = collection.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []

    if not metadatas:
        return "知识库为空，尚未索引任何文档。"

    docs: dict[str, dict] = {}
    for m in metadatas:
        src = m["source"]
        if src not in docs:
            docs[src] = {"count": 0, "indexed_at": m.get("indexed_at", "0")}
        docs[src]["count"] += 1

    lines = ["知识库已索引文档：\n"]
    for name, info in sorted(docs.items()):
        dt = datetime.fromtimestamp(int(info["indexed_at"])).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        lines.append(f"- {name}（{info['count']} 块，索引时间：{dt}）")
    return "\n".join(lines)


def search(collection, query: str, top_k: int = 3) -> str:
    """在知识库中检索最相关的文本段落。"""
    top_k = max(1, min(top_k, 5))

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    if not docs:
        return "知识库中未找到相关内容。"

    lines = [f"共找到 {len(docs)} 个相关段落：\n"]
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
        # cosine distance ∈ [0,1]: 0 = identical → similarity = 1 - dist
        similarity = max(0.0, 1.0 - dist)
        lines += [
            f"【段落 {i + 1}】",
            f"来源文件：{meta['source']}  第 {meta['chunk_index']} 块",
            f"相似度：{similarity:.4f}",
            f"内容：{doc}",
            "",
        ]
    return "\n".join(lines)
