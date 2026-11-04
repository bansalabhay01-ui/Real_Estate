"""Property listings, loaded once from data/listings.json and shared by the API and the assistant."""

import json
from functools import lru_cache

from .config import BACKEND_DIR
from .schemas import Listing

LISTINGS_FILE = BACKEND_DIR / "data" / "listings.json"
LAKH = 100_000
CRORE = 10_000_000


@lru_cache(maxsize=1)
def all_listings() -> tuple[Listing, ...]:
    raw = json.loads(LISTINGS_FILE.read_text(encoding="utf-8"))
    return tuple(Listing.model_validate(item) for item in raw)


def get_listing(listing_id: str) -> Listing | None:
    wanted = listing_id.strip().upper()
    return next((item for item in all_listings() if item.id == wanted), None)


def filter_listings(
    *,
    city: str | None = None,
    locality: str | None = None,
    bhk: int | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
) -> list[Listing]:
    """Listings that match every filter given; None means 'any'."""
    city_key = city.casefold() if city else None
    locality_key = locality.casefold() if locality else None
    return [
        item
        for item in all_listings()
        if (city_key is None or item.city.casefold() == city_key)
        and (locality_key is None or item.locality.casefold() == locality_key)
        and (bhk is None or item.bhk == bhk)
        and (min_price is None or item.price_inr >= min_price)
        and (max_price is None or item.price_inr <= max_price)
    ]


def search_text(item: Listing) -> str:
    """Everything a keyword search can match, lower-cased."""
    parts = [item.title, item.project, item.city, item.locality, item.property_type, item.status, item.description]
    return " ".join([*parts, *item.amenities, *item.highlights, *item.tags]).casefold()


def locality_index() -> dict[str, Listing]:
    """Locality name (lower-case) -> a listing in it, so the assistant can find the city of a locality."""
    return {item.locality.casefold(): item for item in all_listings()}


def format_price(inr: int) -> str:
    """Indian style: 8600000 -> '₹86 L', 14500000 -> '₹1.45 Cr'."""
    if inr >= CRORE:
        value, unit = inr / CRORE, "Cr"
    else:
        value, unit = inr / LAKH, "L"
    return f"₹{value:.2f}".rstrip("0").rstrip(".") + f" {unit}"
