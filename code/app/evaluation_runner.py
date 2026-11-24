
import json
import re
from pathlib import Path

from app.agent import route_finance_request


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_FILE = PROJECT_ROOT / "eval" / "evaluation_questions.json"
REPORT_FILE = PROJECT_ROOT / "eval" / "evaluation_report.latest.json"


KEYWORD_ALIASES = {
    "purchase order": [
        "purchase order",
        "purchase-order",
        "purchase_order",
        "missing po",
        "missing_po"
    ]
}


def load_questions():
    with DATASET_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_region(question):
    normalized_question = question.lower()

    if re.search(
        r"(?<!\w)(?:usa|u\.s\.a?\.?|united states)(?!\w)",
        normalized_question
    ):
        return "USA"

    if "japan" in normalized_question:
        return "Japan"

    return "India"


def normalize_text(text):
    """
    Normalize text for evaluation:
    - Ignore capitalization.
    - Treat 5,000 and 5000 as equivalent.
    - Treat underscores and hyphens as spaces.
    - Normalize repeated whitespace.
    """

    text = str(text).lower()

    # Remove thousands separators in numbers.
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)

    # Normalize underscores and hyphens.
    text = re.sub(r"[_-]", " ", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def keyword_is_present(response_text, expected_keyword):
    """
    Check the expected keyword using normalized text
    and explicitly defined equivalent terms.
    """

    expected = normalize_text(expected_keyword)
    response = normalize_text(response_text)

    if not expected:
        return True

    # Direct normalized match.
    if expected in response:
        return True

    # Check explicitly defined equivalent expressions.
    aliases = KEYWORD_ALIASES.get(expected, [])

    for alias in aliases:
        if normalize_text(alias) in response:
            return True

    return False


def evaluate_questions():
    questions = load_questions()
    results = []

    correct_intents = 0
    correct_evidence_predictions = 0
    keyword_matches = 0
    correct_citation_predictions = 0

    for item in questions:
        question = item["question"]

        print(f"\nTesting {item['id']}: {question}")

        try:
            result = route_finance_request(
                question=question,
                region=get_region(question),
                user_access_level="INTERNAL"
            )

            actual_intent = result.get("intent", "UNKNOWN")
            expected_intent = item["expected_intent"]

            intent_correct = actual_intent == expected_intent

            if intent_correct:
                correct_intents += 1

            data = result.get("data")
            citations = result.get("citations", [])

            actual_evidence = result.get(
                "evidence_available",
                bool(data) or bool(citations)
            )

            expected_evidence = item["expected_evidence"]
            expected_citations = item.get(
                "expected_citations",
                expected_intent == "POLICY_QUERY" and expected_evidence
            )
            actual_citations = bool(citations)
            citations_correct = actual_citations == expected_citations

            evidence_correct = (
                actual_evidence == expected_evidence
            )

            if evidence_correct:
                correct_evidence_predictions += 1

            response_text = json.dumps(
                result,
                ensure_ascii=False,
                default=str
            )
            if item["id"] == "Q021":
                print("\n===== Q021 DEBUG =====")
                print("ANSWER:", result.get("answer"))
                print("KEYWORD PRESENT:", "5000" in response_text)
                print("RESULT:", response_text)
                print("======================\n")

            expected_keyword = item.get(
                "expected_keyword", ""
            ).strip()

            keyword_match = keyword_is_present(
                response_text,
                expected_keyword
            )

            if keyword_match:
                keyword_matches += 1
            if citations_correct:
                correct_citation_predictions += 1

            passed = (
                intent_correct
                and evidence_correct
                and keyword_match
                and citations_correct
            )

            evaluation = {
                "id": item["id"],
                "question": question,
                "expected_intent": expected_intent,
                "actual_intent": actual_intent,
                "intent_correct": intent_correct,
                "expected_evidence": expected_evidence,
                "actual_evidence": actual_evidence,
                "evidence_prediction_correct": evidence_correct,
                "expected_keyword": expected_keyword,
                "keyword_match": keyword_match,
                "expected_citations": expected_citations,
                "actual_citations": actual_citations,
                "citation_presence_correct": citations_correct,
                "status": "PASSED" if passed else "FAILED"
            }

        except Exception as error:
            evaluation = {
                "id": item["id"],
                "question": question,
                "status": "ERROR",
                "error": str(error)
            }

        results.append(evaluation)

        print("Intent:", evaluation.get("actual_intent", "ERROR"))
        print("Status:", evaluation["status"])

    total = len(questions)

    completed = sum(
        1 for item in results
        if item["status"] != "ERROR"
    )

    errors = total - completed

    def calculate_accuracy(correct):
        return round(correct / completed * 100, 2) if completed else 0

    passed = sum(
        1 for item in results
        if item["status"] == "PASSED"
    )

    failed = sum(
        1 for item in results
        if item["status"] == "FAILED"
    )

    report = {
        "total_questions": total,
        "completed_questions": completed,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "intent_accuracy_percent": calculate_accuracy(correct_intents),
        "evidence_prediction_accuracy_percent": calculate_accuracy(
            correct_evidence_predictions
        ),
        "keyword_match_percent": calculate_accuracy(keyword_matches),
        "citation_presence_accuracy_percent": calculate_accuracy(
            correct_citation_predictions
        ),
        "results": results
    }

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with REPORT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\n" + "=" * 45)
    print("FINSAGE EVALUATION SUMMARY")
    print("=" * 45)
    print("Total questions:", total)
    print("Completed:", completed)
    print("Passed:", passed)
    print("Failed:", failed)
    print("Errors:", errors)
    print("Intent accuracy:", report["intent_accuracy_percent"], "%")
    print(
        "Evidence accuracy:",
        report["evidence_prediction_accuracy_percent"],
        "%"
    )
    print("Keyword match:", report["keyword_match_percent"], "%")
    print(
        "Citation presence accuracy:",
        report["citation_presence_accuracy_percent"],
        "%"
    )
    print("Report saved to:", REPORT_FILE)


if __name__ == "__main__":
    evaluate_questions()
