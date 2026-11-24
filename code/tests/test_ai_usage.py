import pytest
from types import SimpleNamespace

from app import agent_router


def test_grounded_policy_generation_sends_verified_evidence_to_gemini(
    monkeypatch
):
    call = {}

    def generate_content(**kwargs):
        call.update(kwargs)
        return SimpleNamespace(text="Gemini-grounded answer.")

    monkeypatch.setattr(
        agent_router.client.models,
        "generate_content",
        generate_content
    )

    answer = agent_router.generate_grounded_policy_answer(
        "What is the average hotel cost in India?",
        [{
            "source_name": "hotel_policy.txt",
            "effective_date": "2026-11-20",
            "chunk_text": "The accommodation limit is INR 5,000 per night."
        }]
    )

    assert answer == "Gemini-grounded answer."
    assert call["model"] == agent_router.GENERATION_MODEL
    assert "average is not provided" in call["contents"]
    assert "INR 5,000 per night" in call["contents"]


@pytest.mark.parametrize("gemini_used_for_retrieval", [True, False])
def test_policy_answer_reports_gemini_embedding_usage(
    monkeypatch,
    gemini_used_for_retrieval
):
    chunk = {
        "chunk_id": "policy-1",
        "chunk_text": "Hotel accommodation must follow company policy."
    }
    monkeypatch.setattr(
        agent_router,
        "retrieve_finance_knowledge",
        lambda **kwargs: ([chunk], gemini_used_for_retrieval)
    )
    monkeypatch.setattr(
        agent_router,
        "verify_evidence",
        lambda *args, **kwargs: {
            "verified": True,
            "reason": "Evidence verified.",
            "evidence": [chunk]
        }
    )
    monkeypatch.setattr(
        agent_router,
        "has_relevant_policy_evidence",
        lambda *args: True
    )
    monkeypatch.setattr(
        agent_router,
        "format_evidence_citations",
        lambda chunks: []
    )
    monkeypatch.setattr(
        agent_router,
        "generate_grounded_policy_answer",
        lambda question, chunks: "Gemini policy answer."
    )

    result = agent_router.route_finance_request(
        question="What is the hotel expense policy?"
    )

    assert result["answer"] == "Gemini policy answer."
    assert result["ai_usage"]["gemini_used_for_answer"] is True
    assert (
        result["ai_usage"]["gemini_used_for_retrieval"]
        is gemini_used_for_retrieval
    )
    assert result["ai_usage"]["answer_generation"] == (
        "Gemini generated an answer from verified policy text"
    )
    assert result["ai_usage"]["gemini_generation_status"] == "COMPLETED"


def test_policy_query_passes_selected_region_to_retrieval(monkeypatch):
    observed = {}
    chunk = {
        "chunk_id": "usa-policy-1",
        "chunk_text": "The hotel limit is USD 250 per night."
    }

    def retrieve(**kwargs):
        observed.update(kwargs)
        return [chunk], True

    monkeypatch.setattr(agent_router, "retrieve_finance_knowledge", retrieve)
    monkeypatch.setattr(
        agent_router,
        "verify_evidence",
        lambda *args, **kwargs: {
            "verified": True,
            "reason": "Evidence verified.",
            "evidence": [chunk]
        }
    )
    monkeypatch.setattr(
        agent_router,
        "has_relevant_policy_evidence",
        lambda *args: True
    )
    monkeypatch.setattr(agent_router, "format_evidence_citations", lambda chunks: [])
    monkeypatch.setattr(
        agent_router,
        "generate_grounded_policy_answer",
        lambda question, chunks: "USA policy answer."
    )

    result = agent_router.route_finance_request(
        question="What is the USA hotel limit?",
        region="USA"
    )

    assert result["answer"] == "USA policy answer."
    assert observed["region"] == "USA"


def test_policy_answer_reports_fallback_when_gemini_generation_fails(
    monkeypatch
):
    chunk = {
        "chunk_id": "policy-1",
        "chunk_text": "Hotel accommodation must follow company policy."
    }
    monkeypatch.setattr(
        agent_router,
        "retrieve_finance_knowledge",
        lambda **kwargs: ([chunk], True)
    )
    monkeypatch.setattr(
        agent_router,
        "verify_evidence",
        lambda *args, **kwargs: {
            "verified": True,
            "reason": "Evidence verified.",
            "evidence": [chunk]
        }
    )
    monkeypatch.setattr(
        agent_router,
        "has_relevant_policy_evidence",
        lambda *args: True
    )
    monkeypatch.setattr(
        agent_router,
        "format_evidence_citations",
        lambda chunks: []
    )

    def fail_generation(question, chunks):
        raise ValueError("Gemini returned no text")

    monkeypatch.setattr(
        agent_router,
        "generate_grounded_policy_answer",
        fail_generation
    )
    monkeypatch.setattr(
        agent_router,
        "build_policy_answer",
        lambda question, chunks: "Verified policy fallback."
    )

    result = agent_router.route_finance_request(
        question="What is the hotel expense policy?"
    )

    assert result["answer"] == "Verified policy fallback."
    assert result["ai_usage"]["gemini_used_for_answer"] is False
    assert result["ai_usage"]["gemini_used_for_retrieval"] is True
    assert result["ai_usage"]["gemini_generation_status"] == "FAILED"


def test_structured_invoice_answer_is_not_generated_by_gemini(monkeypatch):
    monkeypatch.setattr(
        agent_router,
        "summarize_invoices",
        lambda: [{"payment_status": "PAID", "invoice_count": 1}]
    )

    result = agent_router.route_finance_request(
        question="Show invoice payment summary."
    )

    assert result["ai_usage"]["gemini_used_for_answer"] is False
    assert result["ai_usage"]["gemini_used_for_retrieval"] is False


def test_empty_duplicate_query_is_still_a_successful_evidence_result(
    monkeypatch
):
    monkeypatch.setattr(
        agent_router,
        "check_duplicate_invoices",
        lambda: []
    )

    result = agent_router.route_finance_request(
        question="Find duplicate invoices."
    )

    assert result["data"] == []
    assert result["evidence_available"] is True
    assert "No duplicate invoices" in result["answer"]
