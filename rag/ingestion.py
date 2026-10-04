import fitz
import glob
import os
import re

DOCS_FOLDER = "rag/data/documents"


def clean_text(text):
    # Replace many spaces/newlines with a single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pages(pdf_path):
    pages = []
    doc = fitz.open(pdf_path)
    document_name = os.path.basename(pdf_path)
    for i, page in enumerate(doc):
        text = clean_text(page.get_text())
        if text:
            pages.append({
                "document": document_name,
                "page": i + 1,
                "text": text,
            })
    doc.close()
    return pages


CHUNK_SIZE = 500   # words per chunk
OVERLAP = 80       # words shared between neighbouring chunks


def chunk_page(page):
    words = page["text"].split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + CHUNK_SIZE
        chunk_text = " ".join(words[start:end])
        chunks.append({
            "document": page["document"],
            "page": page["page"],
            "text": chunk_text,
        })
        if end >= len(words):
            break
        start = end - OVERLAP
    return chunks


def build_chunks():
    all_chunks = []
    for pdf in glob.glob(DOCS_FOLDER + "/*.pdf"):
        for page in extract_pages(pdf):
            all_chunks.extend(chunk_page(page))
    return all_chunks


import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

INDEX_FOLDER = "rag/index"
MODEL_NAME = "all-MiniLM-L6-v2"


def build_index():
    chunks = build_chunks()
    print("Total chunks:", len(chunks))

    print("Loading model...")
    model = SentenceTransformer(MODEL_NAME)

    texts = [c["text"] for c in chunks]
    print("Creating embeddings (this can take a few minutes)...")
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    embeddings = np.array(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    os.makedirs(INDEX_FOLDER, exist_ok=True)
    faiss.write_index(index, INDEX_FOLDER + "/faiss.index")
    with open(INDEX_FOLDER + "/metadata.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print("Saved faiss.index and metadata.json in", INDEX_FOLDER)


if __name__ == "__main__":
    build_index()