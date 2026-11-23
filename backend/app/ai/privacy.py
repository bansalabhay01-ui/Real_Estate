"""Hide phone numbers and email addresses before any text is sent to an LLM (DPDP Act 2023)."""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Phone numbers however they are written: 10 to 15 digits (Devanagari digits too), with an optional + and up to two
# spaces, dashes, dots or brackets between digits: "+91 98220 12345", "987-654-3210", "(022) 2345 6789".
# Budgets stay readable: "90 lakh" and "85,00,000" have too few digits or use commas.
_PHONE = re.compile(r"(?<![\d+])\+?\d(?:[ \t().-]{0,2}\d){9,14}(?!\d)")


def mask_pii(text: str) -> str:
    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", text))
