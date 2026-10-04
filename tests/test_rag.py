import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))

from retriever import retrieve


# ---------- In-scope questions (answerable from the PDFs) ----------

def test_pca_is_found():
    result = retrieve("What is PCA?")
    assert result["in_scope"] is True
    assert result["answer_context"] != ""
    assert any(s["document"] == "ML_notes.pdf" for s in result["sources"])


def test_tokenization_is_found():
    result = retrieve("What is tokenization?")
    assert result["in_scope"] is True
    assert any(s["document"] == "NLP_Notes.pdf" for s in result["sources"])


def test_gradient_descent_is_found():
    result = retrieve("What is gradient descent?")
    assert result["in_scope"] is True
    assert result["answer_context"] != ""


# ---------- Source metadata ----------

def test_sources_have_document_and_page():
    result = retrieve("What is overfitting?")
    assert result["in_scope"] is True
    for source in result["sources"]:
        assert "document" in source
        assert isinstance(source["page"], int)
        assert source["page"] >= 1


# ---------- Out-of-scope questions ----------

def test_fifa_is_out_of_scope():
    result = retrieve("Who won the FIFA World Cup?")
    assert result["in_scope"] is False
    assert result["sources"] == []


def test_bitcoin_is_out_of_scope():
    result = retrieve("What is the current Bitcoin price?")
    assert result["in_scope"] is False
    assert result["answer_context"] == ""