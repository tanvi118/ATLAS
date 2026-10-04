import json
import os
import faiss
from sentence_transformers import SentenceTransformer

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
INDEX_FOLDER = os.path.join(BASE_FOLDER, "index")
MODEL_NAME = "all-MiniLM-L6-v2"

TOP_K = 5
THRESHOLD = 0.40

_model = None
_index = None
_metadata = None


def _load():
    global _model, _index, _metadata
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
        _index = faiss.read_index(os.path.join(INDEX_FOLDER, "faiss.index"))
        with open(os.path.join(INDEX_FOLDER, "metadata.json"), encoding="utf-8") as f:
            _metadata = json.load(f)


def retrieve(question, document_id=None):
    _load()

    query = _model.encode([question], normalize_embeddings=True)
    query = query.astype("float32")

    # If filtering by one document, search everything, then filter
    k = len(_metadata) if document_id else TOP_K
    scores, ids = _index.search(query, k)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        chunk = _metadata[idx]
        if document_id and chunk["document"] != document_id:
            continue
        if score < THRESHOLD:
            continue
        results.append((float(score), chunk))
        if len(results) == TOP_K:
            break

    if not results:
        return {
            "in_scope": False,
            "answer_context": "",
            "sources": [],
        }

    context = "\n\n".join(chunk["text"] for _, chunk in results)

    sources = []
    for score, chunk in results:
        source = {"document": chunk["document"], "page": chunk["page"]}
        if source not in sources:
            sources.append(source)

    return {
        "in_scope": True,
        "answer_context": context,
        "sources": sources,
        "top_score": round(results[0][0], 3),
    }


if __name__ == "__main__":
    for q in ["What is PCA?", "Who won the FIFA World Cup?"]:
        result = retrieve(q)
        print("QUESTION:", q)
        print("In scope:", result["in_scope"])
        print("Sources:", result["sources"])
        print("Top score:", result.get("top_score"))
        print("Context preview:", result["answer_context"][:200])
        print("-" * 40)