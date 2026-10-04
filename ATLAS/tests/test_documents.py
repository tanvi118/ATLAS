import pytest

from app.config import settings
from app.services import llm_service, rag_service

PDF = b"%PDF-1.4 minimal"


@pytest.fixture()
def uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    return tmp_path


def upload(client, name="notes.pdf", data=PDF):
    return client.post("/documents/upload", files={"file": (name, data, "application/pdf")})


def test_upload_validation(client, uploads):
    assert upload(client, "notes.txt", b"hello").status_code == 400
    assert upload(client, "fake.pdf", b"not a pdf").status_code == 400
    assert upload(client, "big.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024 + 1)).status_code == 413
    assert list(uploads.iterdir()) == []  # nothing was saved


def test_upload_when_rag_unavailable_saves_file_but_is_not_indexed(client, uploads):
    r = upload(client, "../../evil.pdf")
    assert r.status_code == 201
    body = r.json()
    assert body["indexed"] is False and body["chunks"] is None and "NOT indexed" in body["message"]
    assert body["filename"] == "evil.pdf"                      # path stripped
    assert [p.name for p in uploads.iterdir()] == [f"{body['document_id']}.pdf"]  # our name, inside upload dir


def test_query_when_rag_unavailable_returns_message_and_no_sources(client):
    r = client.post("/documents/query", json={"question": "What is TF-IDF?", "session_id": "demo-session"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] == [] and "not connected" in body["reply"]
    assert set(body) == {"reply", "intent", "sources", "session_id"} and body["intent"] == "document_qa"


def test_query_unknown_document_is_404(client, uploads):
    assert client.post("/documents/query", json={"question": "x", "document_id": "a" * 32}).status_code == 404
    assert client.post("/documents/query", json={"question": "x", "document_id": "../../etc/passwd"}).status_code == 404
    assert client.post("/documents/query", json={"question": ""}).status_code == 422


def test_upload_index_and_query_with_mocked_rag(client, uploads, monkeypatch):
    monkeypatch.setattr(rag_service, "ingest_document", lambda path, document_id, filename: 7)
    up = upload(client, "NLP Notes.pdf").json()
    assert up["indexed"] is True and up["chunks"] == 7

    monkeypatch.setattr(rag_service, "retrieve_context", lambda q, document_id=None: {
        "context": "TF-IDF text", "sources": [{"document": "NLP Notes.pdf", "page": 4}]})
    monkeypatch.setattr(llm_service, "generate_response", lambda m, s=None: "Answer from the PDF.")
    q = client.post("/documents/query", json={"question": "What is TF-IDF?", "document_id": up["document_id"], "session_id": "demo-session"})
    assert q.json() == {"reply": "Answer from the PDF.", "intent": "document_qa",
                        "sources": [{"document": "NLP Notes.pdf", "page": 4}], "session_id": "demo-session"}


def test_query_with_no_relevant_context_has_no_sources(client, monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_context", lambda q, document_id=None: {"context": "", "sources": []})
    body = client.post("/documents/query", json={"question": "Unrelated?"}).json()
    assert body["sources"] == [] and "couldn't find" in body["reply"]


def test_rag_adapter_unavailable_when_rag_folder_empty():
    with pytest.raises(rag_service.RAGUnavailableError):
        rag_service.retrieve_context("anything")
    with pytest.raises(rag_service.RAGUnavailableError):
        rag_service.ingest_document(__file__, "x", "x.pdf")


def test_rag_adapter_normalizes_chunk_lists(monkeypatch):
    chunks = [{"text": "A", "metadata": {"source": "n.pdf", "page_number": 2}}, {"text": "B", "source": "n.pdf", "page": 2}]
    monkeypatch.setattr(rag_service, "_load", lambda *a: (lambda question, document_id=None: chunks))
    assert rag_service.retrieve_context("q", "d1") == {"context": "A\n\nB", "sources": [{"document": "n.pdf", "page": 2}]}


def test_rag_adapter_normalizes_dict_result(monkeypatch):
    raw = {"answer_context": "ctx", "sources": [{"document": "NLP_Notes.pdf", "page": 4}]}
    monkeypatch.setattr(rag_service, "_load", lambda *a: (lambda question: raw))  # function without document_id param
    assert rag_service.retrieve_context("q", "d1") == {"context": "ctx", "sources": [{"document": "NLP_Notes.pdf", "page": 4}]}
