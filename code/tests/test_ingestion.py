from pathlib import Path

from app.ingestion import process_documents


def test_usa_demo_policy_can_be_processed_by_itself():
    documents = process_documents(
        file_name="USA_DEMO_ONLY_TRAVEL_POLICY.txt"
    )

    assert documents
    assert all(document["region"] == "USA" for document in documents)
    assert all(
        document["source_name"] == "USA_DEMO_ONLY_TRAVEL_POLICY.txt"
        for document in documents
    )


def test_usa_demo_policy_is_comprehensive_and_copies_match():
    project_root = Path(__file__).resolve().parent.parent
    active_policy = (
        project_root
        / "data"
        / "documents"
        / "policies"
        / "USA_DEMO_ONLY_TRAVEL_POLICY.txt"
    )
    demo_policy = (
        project_root
        / "data"
        / "demo_policies"
        / "USA_DEMO_ONLY_TRAVEL_POLICY.txt"
    )
    content = active_policy.read_text(encoding="utf-8")

    assert content == demo_policy.read_text(encoding="utf-8")
    assert "not an approved company policy" in content
    assert "USD 250 per room per night" in content
    assert "USD 75 per traveler per day" in content
    assert "manager approval" in content
    assert "supporting documentation" in content


def test_vendor_master_policy_markdown_region_is_extracted_as_india():
    documents = process_documents(
        file_name="vendor_master_data_policy.txt"
    )

    assert documents
    assert all(document["region"] == "INDIA" for document in documents)


def test_usa_vendor_demo_policy_is_labeled_and_processed_as_usa():
    project_root = Path(__file__).resolve().parent.parent
    active_policy = (
        project_root
        / "data"
        / "documents"
        / "policies"
        / "USA_DEMO_ONLY_VENDOR_ONBOARDING_POLICY.txt"
    )
    demo_policy = (
        project_root
        / "data"
        / "demo_policies"
        / "USA_DEMO_ONLY_VENDOR_ONBOARDING_POLICY.txt"
    )
    content = active_policy.read_text(encoding="utf-8")
    documents = process_documents(
        file_name="USA_DEMO_ONLY_VENDOR_ONBOARDING_POLICY.txt"
    )

    assert content == demo_policy.read_text(encoding="utf-8")
    assert "not an approved company policy" in content
    assert documents
    assert all(document["region"] == "USA" for document in documents)
