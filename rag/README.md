# ATLAS RAG Module (Member 1)

This module lets ATLAS answer academic questions using uploaded PDFs.

## How it works

PDF -> text extraction (PyMuPDF) -> cleaning -> chunking -> embeddings
(all-MiniLM-L6-v2) -> FAISS index -> semantic retrieval

- Chunk size: 500 words, overlap: 80 words (chunks never cross page boundaries)
- Top-k: 5 chunks
- Similarity threshold: 0.40 (tuned on test questions; 0.35 let in a wrong match)

## Files

- `ingestion.py` - reads PDFs in `rag/data/documents/` and builds the index
- `retriever.py` - searches the index (this is what Member 2 uses)
- `index/faiss.index` and `index/metadata.json` - the saved index
- `data/sample_tasks.json` - 50 sample student tasks
- `data/synthetic_generator.py` - generates 500 synthetic student tasks
- `data/process_ednet.py` - extracts a 1,000-student EdNet sample

## Data note

Only the academic PDFs go into FAISS. EdNet, Riiid, and synthetic task data
are structured data and are NOT part of the RAG index.

## How to use (for Member 2)

```python
from rag.retriever import retrieve

result = retrieve("What is PCA?")
# optional: retrieve("What is PCA?", document_id="ML_notes.pdf")
```

Returned format:

```python
{
    "in_scope": True,
    "answer_context": "...retrieved text...",
    "sources": [{"document": "ML_notes.pdf", "page": 173}],
    "top_score": 0.456
}
```

If nothing is relevant enough:

```python
{"in_scope": False, "answer_context": "", "sources": []}
```

Member 2 should tell the user the question is outside the uploaded documents
when `in_scope` is False, instead of letting the LLM guess.

## Rebuilding the index

Only needed if PDFs are added or changed:

```
python rag/ingestion.py
```

## Running the tests

```
pytest tests/test_rag.py -v
```

## Known limitations

- Works best with text-based PDFs (scanned PDFs are not supported).
- The current PDFs do not cover CNN max pooling, so that question is
  correctly treated as out of scope.
- The threshold was tuned on a small set of questions and may need retuning
  if new documents are added.