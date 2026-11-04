"""Property listings for the demo site. The assistant reads the same data."""

from fastapi import APIRouter, HTTPException, Query

from ..listings import filter_listings, get_listing, search_text
from ..schemas import Listing

router = APIRouter(tags=["listings"])


@router.get("/listings", response_model=list[Listing])
def get_listings(
    city: str | None = None,
    bhk: int | None = Query(None, ge=1, le=10),
    min_price: int | None = Query(None, ge=0, description="INR"),
    max_price: int | None = Query(None, ge=0, description="INR"),
    q: str | None = Query(None, max_length=100, description="Keywords, e.g. 'pool metro'"),
) -> list[Listing]:
    items = filter_listings(city=city, bhk=bhk, min_price=min_price, max_price=max_price)
    if q:
        words = q.casefold().split()
        items = [item for item in items if all(word in search_text(item) for word in words)]
    return items


@router.get("/listings/{listing_id}", response_model=Listing)
def get_one_listing(listing_id: str) -> Listing:
    item = get_listing(listing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return item
