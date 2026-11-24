import pytest

from app.evaluation_runner import get_region


@pytest.mark.parametrize(
    ("question", "expected_region"),
    [
        ("What is the USA hotel limit?", "USA"),
        ("What is the U.S. travel approval process?", "USA"),
        ("What is the hotel limit in the United States?", "USA"),
        ("What is the international hotel limit in Japan?", "Japan"),
        ("What is the hotel expense limit in India?", "India")
    ]
)
def test_evaluation_region_is_selected_from_country(question, expected_region):
    assert get_region(question) == expected_region
