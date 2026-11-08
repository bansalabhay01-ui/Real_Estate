"""Buyer details from chat messages: English, Hinglish and Hindi."""

import pytest

from app.ai.extract import extract_details

LAKH, CRORE = 100_000, 10_000_000


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("3BHK under 90L in Pune?", {"city": "Pune", "bhk": 3, "budget_max": 90 * LAKH, "language": "en"}),
        ("Pune mein 90 lakh tak 3BHK chahiye", {"city": "Pune", "bhk": 3, "budget_max": 90 * LAKH, "language": "hinglish"}),
        ("मुझे पुणे में 90 लाख तक 3BHK चाहिए", {"city": "Pune", "bhk": 3, "budget_max": 90 * LAKH, "language": "hi"}),
        ("2 bhk in bangalore between 60 and 80 lakh", {"city": "Bengaluru", "bhk": 2, "budget_min": 60 * LAKH, "budget_max": 80 * LAKH}),
        ("Looking at Wagholi, 80-90L", {"locality": "Wagholi", "city": "Pune", "budget_min": 80 * LAKH, "budget_max": 90 * LAKH}),
        ("anything in thane above 1 crore?", {"locality": "Thane West", "city": "Mumbai", "budget_min": CRORE}),
        ("budget 1.2 cr, need a home loan, moving in 3 months", {"budget_max": 120 * LAKH, "loan_needed": True, "timeline_months": 3}),
        ("No loan needed, full cash. teen bhk chahiye", {"loan_needed": False, "bhk": 3}),
        ("sec 150 noida 3 bedroom", {"locality": "Sector 150", "city": "Noida", "bhk": 3}),
        ("Budget is ₹85,00,000", {"budget_max": 85 * LAKH}),
        ("hyd mein 2bhk, 1 crore se kam", {"city": "Hyderabad", "bhk": 2, "budget_max": CRORE}),
        ("Need to shift immediately", {"timeline_months": 1}),
    ],
)  # fmt: skip
def test_extract_details(message, expected):
    found = extract_details(message)
    for key, value in expected.items():
        assert found.get(key) == value, f"{key!r} wrong in {found}"


def test_a_phone_number_is_not_a_budget():
    found = extract_details("call me on 9876543210 for a 2bhk")
    assert "budget_max" not in found and "budget_min" not in found
    assert found["bhk"] == 2


def test_loan_tenure_is_not_a_move_in_timeline():
    found = extract_details("what is the EMI for 20 years?")
    assert "timeline_months" not in found
    assert found["loan_needed"] is True


def test_nothing_found_in_small_talk():
    assert extract_details("hello, how are you?") == {"language": "en"}


# ---------------------------------------------------------------- purpose and LLM extraction

from app.ai import extract as extract_module  # noqa: E402
from app.ai.extract import clean_details, smart_extract  # noqa: E402
from app.ai.llm_client import LLMError  # noqa: E402


@pytest.mark.parametrize(
    ("message", "purpose"),
    [
        ("Buying as an investment, what rental yield?", "investment"),
        ("I want to buy and rent it out", "investment"),
        ("A home to live in with my family", "own_use"),
        ("Khud ke liye ghar chahiye", "own_use"),
        ("3BHK in Pune", None),
    ],
)
def test_purpose(message, purpose):
    assert extract_details(message).get("purpose") == purpose


def test_llm_values_are_checked():
    raw = {"city": "Delhi", "locality": "Wagholi", "bhk": 9, "budget_min": 9_500_000, "budget_max": 8_000_000,
           "timeline_months": 3.0, "loan_needed": "yes", "purpose": "renting", "language": "hinglish"}
    assert clean_details(raw) == {"locality": "Wagholi", "city": "Pune", "budget_min": 8_000_000,
                                  "budget_max": 9_500_000, "timeline_months": 3, "language": "hinglish"}
    assert clean_details({"bhk": True, "budget_max": float("nan"), "city": "bangalore"}) == {"city": "Bengaluru"}


class FakeLLM:
    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.calls = answer, error, []

    def available(self):
        return True

    def generate_json(self, system, messages, schema, **kwargs):
        self.calls.append(messages[0]["content"])
        if self.error:
            raise self.error
        return self.answer


def test_smart_extract_merges_the_llm_with_the_patterns(monkeypatch):
    fake = FakeLLM({"city": "Bengaluru", "locality": None, "bhk": None, "budget_min": None, "budget_max": None,
                    "timeline_months": None, "loan_needed": None, "purpose": None, "language": "en"})
    monkeypatch.setattr(extract_module, "llm", fake)
    found = smart_extract("same budget but in Bangalore, call 9822012345", ["3BHK under 90L in Pune"])
    assert found["city"] == "Bengaluru"
    assert "[phone]" in fake.calls[0] and "9822012345" not in fake.calls[0]  # masked before it reaches the LLM
    assert "<earlier_messages>" in fake.calls[0]


def test_smart_extract_keeps_one_budget_pair(monkeypatch):
    fake = FakeLLM({"city": None, "locality": None, "bhk": None, "budget_min": 8_000_000, "budget_max": 8_500_000,
                    "timeline_months": None, "loan_needed": None, "purpose": None, "language": "hinglish"})
    monkeypatch.setattr(extract_module, "llm", fake)
    found = smart_extract("80-85 lakh ke beech, under 1 cr nahi")
    assert (found["budget_min"], found["budget_max"]) == (8_000_000, 8_500_000)


def test_smart_extract_falls_back_to_the_patterns(monkeypatch):
    monkeypatch.setattr(extract_module, "llm", FakeLLM(error=LLMError("timeout")))
    assert smart_extract("3BHK under 90L in Pune")["budget_max"] == 9_000_000
