import pytest

from app.agent_router import (
    build_policy_answer,
    has_relevant_policy_evidence,
    route_finance_request
)
from app.finance_knowledge import (
    format_evidence_citations,
    retrieve_finance_knowledge_fallback
)
from app.verifier import verify_evidence


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def execute(self, query, parameters):
        self.query = query
        self.parameters = parameters

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_lexical_fallback_does_not_claim_semantic_similarity():
    cursor = FakeCursor([(
        "usa-policy-1",
        "POLICY",
        "USA_DEMO_ONLY_TRAVEL_POLICY.txt",
        "TRAVEL_EXPENSE",
        "USA",
        "2026-11-01",
        "INTERNAL",
        "Eligible hotel accommodation is reimbursable up to USD 250 per night."
    )])
    connection = FakeConnection()

    results = retrieve_finance_knowledge_fallback(
        cursor=cursor,
        connection=connection,
        question="What is the USA hotel reimbursement limit?",
        region="USA"
    )

    assert results[0]["similarity_score"] == 0.0
    assert results[0]["retrieval_method"] == "LEXICAL"
    assert cursor.closed
    assert connection.closed


def test_weak_hotel_excerpt_does_not_support_a_limit():
    question = "What is the hotel reimbursement limit?"
    chunks = [{
        "chunk_text": "Hotel accommodations are available for business trips.",
        "similarity_score": 0.75
    }]

    verification = verify_evidence(
        chunks,
        min_similarity=0.70,
        min_keyword_relevance=0.35,
        question=question
    )

    assert verification["verified"] is False
    assert has_relevant_policy_evidence(question, chunks) is False


def test_policy_route_refuses_hotel_text_without_a_limit(monkeypatch):
    chunk = {
        "chunk_text": "Hotel accommodations are available for business trips.",
        "similarity_score": 0.75
    }
    monkeypatch.setattr(
        "app.agent_router.retrieve_finance_knowledge",
        lambda **kwargs: ([chunk], False)
    )
    monkeypatch.setattr(
        "app.agent_router.generate_grounded_policy_answer",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("Gemini must not receive unsupported evidence.")
        )
    )

    result = route_finance_request(
        question="What is the hotel reimbursement limit?"
    )

    assert result["evidence_available"] is False
    assert "could not find sufficient verified evidence" in result["answer"]


@pytest.mark.parametrize(
    "original_question",
    [
        "What is the average cost of hotel in India?",
        "What is the average amount of hotel in India?"
    ]
)
def test_average_hotel_question_retrieves_cap_but_keeps_original_question(
    monkeypatch,
    original_question
):
    observed = {}
    chunk = {
        "chunk_id": "india-hotel-limit",
        "source_name": "business_travel_policy.txt",
        "effective_date": "2026-11-01",
        "chunk_text": (
            "India hotel expenses must not exceed INR 5,000 per night."
        ),
        "similarity_score": 0.85
    }

    def retrieve(**kwargs):
        observed["retrieval_question"] = kwargs["question"]
        return [chunk], True

    def generate(question, verified_chunks):
        observed["answer_question"] = question
        return (
            "The average is not stated. The policy cap is INR 5,000 per "
            "night, not an average."
        )

    monkeypatch.setattr(
        "app.agent_router.retrieve_finance_knowledge",
        retrieve
    )
    monkeypatch.setattr(
        "app.agent_router.generate_grounded_policy_answer",
        generate
    )

    result = route_finance_request(question=original_question)

    assert observed["retrieval_question"] == (
        "What is the hotel reimbursement limit in India?"
    )
    assert observed["answer_question"] == original_question
    assert result["evidence_available"] is True
    assert "INR 5,000 per night" in result["answer"]


def test_average_hotel_fallback_distinguishes_average_from_policy_cap():
    answer = build_policy_answer(
        "What is the average cost of hotel in India?",
        [{
            "chunk_text": (
                "India hotel expenses must not exceed INR 5,000 per night."
            )
        }]
    )

    assert "does not state an average market hotel cost" in answer
    assert "INR 5,000 per night" in answer
    assert "not an average" in answer


def test_lexical_evidence_can_cover_multi_part_usa_policy_question():
    question = (
        "According to our USA travel policy, what are the hotel "
        "reimbursement limit, approval requirements, and receipt requirements?"
    )
    chunks = [
        {
            "chunk_text": (
                "The USA demo hotel reimbursement limit is USD 250 per room "
                "per night. Rates above USD 250 require manager approval "
                "and written business justification."
            ),
            "similarity_score": 0.0,
            "retrieval_method": "LEXICAL"
        },
        {
            "chunk_text": (
                "Hotel invoice documentation must show dates and nights. "
                "Travel claims must include supporting receipts and proof "
                "of payment."
            ),
            "similarity_score": 0.0,
            "retrieval_method": "LEXICAL"
        }
    ]

    verification = verify_evidence(
        chunks,
        min_similarity=0.70,
        min_keyword_relevance=0.10,
        question=question
    )

    assert verification["verified"] is True
    assert has_relevant_policy_evidence(question, verification["evidence"])


def test_usd_limit_is_supported_by_fallback_and_citation_is_labeled():
    question = "What is the USA hotel reimbursement limit?"
    chunk = {
        "chunk_id": "usa-policy-1",
        "source_name": "USA_DEMO_ONLY_TRAVEL_POLICY.txt",
        "effective_date": "2026-11-01",
        "chunk_text": (
            "Eligible hotel accommodation is reimbursable up to "
            "USD 250 per room per night."
        ),
        "similarity_score": 0.0,
        "retrieval_method": "LEXICAL",
        "keyword_relevance": 0.75
    }

    assert has_relevant_policy_evidence(question, [chunk]) is True
    assert "USD 250" in build_policy_answer(question, [chunk])

    citation = format_evidence_citations([chunk])[0]
    assert citation["retrieval_method"] == "keyword fallback"
    assert citation["keyword_relevance"] == 0.75
    assert "similarity_score" not in citation
