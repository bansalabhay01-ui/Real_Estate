"""Find listings for a chat message: structured filters first, then keyword overlap to rank.

For questions like "3BHK under 90L in Pune" this is more accurate than vector search and needs no extra
install. Member C adds ChromaDB over the brochures (PDFs) in Week 2.
"""

import re
from dataclasses import dataclass, field

from ..listings import all_listings, filter_listings, search_text
from ..schemas import Listing

BUDGET_STRETCH = 0.15  # when nothing fits, show homes up to 15% outside the budget

_STOPWORDS = {
    "the", "and", "for", "with", "show", "want", "need", "looking", "look", "find", "have", "any", "some",
    "please", "under", "below", "upto", "within", "budget", "lakh", "lakhs", "lac", "lacs", "crore", "crores",
    "bhk", "bedroom", "bedrooms", "home", "homes", "house", "property", "properties", "buy", "flat", "flats",
    "near", "what", "which", "where", "there", "this", "that", "you", "your", "are", "can", "get", "like",
    "price", "cost", "rate", "good", "best", "area", "location", "mein", "chahiye", "tak", "hai", "kya",
    "koi", "wala", "wali", "ghar", "aur", "bhi", "dikhao", "batao", "mujhe",
}  # fmt: skip


@dataclass
class SearchResult:
    listings: list[Listing]
    relaxed: list[str] = field(default_factory=list)  # filters loosened to find something, e.g. ["budget"]

    @property
    def exact(self) -> bool:
        return not self.relaxed


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z]{3,}", text.casefold())
    return {word.removesuffix("s") if len(word) > 4 else word for word in words if word not in _STOPWORDS}


def _keyword_score(item: Listing, keywords: set[str]) -> int:
    haystack = search_text(item)
    return sum(1 for word in keywords if word in haystack)


def _rank(items: list[Listing], keywords: set[str], budget_max: int | None) -> list[Listing]:
    """Keyword matches first; then the home closest to the budget (or the cheapest when there's no budget)."""

    def key(item: Listing) -> tuple[int, int]:
        gap = abs(budget_max - item.price_inr) if budget_max else item.price_inr
        return (-_keyword_score(item, keywords), gap)

    return sorted(items, key=key)


def find_listings(criteria: dict, message: str, limit: int = 3) -> SearchResult:
    """Best listings for what the buyer told us. The city is never relaxed: someone asking for Pune
    doesn't want Mumbai. Locality, budget and BHK are loosened one at a time when nothing matches."""
    keywords = _keywords(message)
    city, locality, bhk = criteria.get("city"), criteria.get("locality"), criteria.get("bhk")
    budget_min, budget_max = criteria.get("budget_min"), criteria.get("budget_max")

    if not any((city, locality, bhk, budget_min, budget_max)):
        # Nothing known yet: answer only if the message names something listings have ("pool", "villa").
        matches = [item for item in all_listings() if _keyword_score(item, keywords) > 0]
        return SearchResult(_rank(matches, keywords, None)[:limit])

    has_budget = bool(budget_min or budget_max)
    steps: list[tuple[str, dict]] = []  # applied in order, each on top of the previous ones
    if locality:
        steps.append(("locality", {"locality": None}))
    if has_budget:
        steps.append(
            (
                "budget",
                {
                    "min_price": round(budget_min * (1 - BUDGET_STRETCH)) if budget_min else None,
                    "max_price": round(budget_max * (1 + BUDGET_STRETCH)) if budget_max else None,
                },
            )
        )
    if bhk:
        steps.append(("bhk", {"bhk": None}))
    if has_budget:
        steps.append(("budget", {"min_price": None, "max_price": None}))  # last resort: closest homes in the city

    filters = {"city": city, "locality": locality, "bhk": bhk, "min_price": budget_min, "max_price": budget_max}
    relaxed: list[str] = []
    matches = filter_listings(**filters)
    for name, change in steps:
        if matches:
            break
        filters.update(change)
        if name not in relaxed:
            relaxed.append(name)
        matches = filter_listings(**filters)
    return SearchResult(_rank(matches, keywords, budget_max)[:limit], relaxed)
