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
