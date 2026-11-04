"""Hide phone numbers and email addresses before any text is sent to an LLM (DPDP Act 2023)."""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Indian mobile numbers: 10 digits starting 6-9, optionally with +91 / 91 / 0 and a space or dash in the middle.
_PHONE = re.compile(r"(?<!\d)(?:(?:\+?91|0)[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")


def mask_pii(text: str) -> str:
    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", text))
