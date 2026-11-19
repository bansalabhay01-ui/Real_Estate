"""Project brochures: short passages from backend/data/brochures, found with BM25 keyword ranking.

For a handful of brochures with distinctive words ("payment plan", "parking", "RERA") keyword ranking is accurate and
needs no vector database or embedding model. Hindi, Hinglish and Marathi words are mapped to the English words the
brochures use; with an LLM key the agent also writes English search words for the question.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from ..config import BACKEND_DIR

BROCHURE_DIR = BACKEND_DIR / "data" / "brochures"
K1, B = 1.5, 0.75  # the usual BM25 settings
TITLE_BONUS = 2.0  # a question's word in a section's title ("possession", "parking") says a lot about that section

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "be", "to", "of", "in", "on", "at", "for", "and", "or", "it", "its", "this", "that",
    "with", "what", "whats", "which", "how", "much", "many", "do", "does", "did", "can", "will", "there", "any", "me", "my", "i",
    "you", "your", "we", "our", "please", "tell", "about", "have", "has", "get", "give", "kya", "hai", "hain", "ka", "ki", "ke",
    "ko", "se", "mein", "aur", "bhi", "batao", "bataiye", "kitna", "kitni", "kaisa", "kaisi", "क्या", "है", "हैं", "का", "की", "के",
    "में", "और", "कितना", "कितनी", "आहे", "किती", "काय", "आणि", "मध्ये", "सांगा", "बताओ", "बताइए",
}  # fmt: skip

# Words visitors use -> the words in the brochures.
_SYNONYMS = {
    "instalment": ["payment", "plan"], "installment": ["payment", "plan"], "kist": ["payment", "plan"], "booking": ["booking", "payment"],
    "bhugtan": ["payment"], "भुगतान": ["payment"], "पेमेंट": ["payment", "plan"], "किस्त": ["payment", "plan"], "हप्ता": ["payment", "plan"],
    "gaadi": ["parking"], "gadi": ["parking"], "car": ["parking", "car"], "garage": ["parking"], "पार्किंग": ["parking"], "गाड़ी": ["parking"], "गाडी": ["parking"],
    "skool": ["school"], "स्कूल": ["school"], "शाळा": ["school"], "शाळेचे": ["school"], "college": ["school"],
    "aspatal": ["hospital"], "hospital": ["hospital"], "doctor": ["hospital"], "अस्पताल": ["hospital"], "रुग्णालय": ["hospital"], "दवाखाना": ["hospital"],
    "मेट्रो": ["metro"], "station": ["metro"], "airport": ["airport"], "एयरपोर्ट": ["airport"], "विमानतळ": ["airport"], "office": ["offices"], "work": ["offices"],
    "मेंटेनेंस": ["maintenance"], "देखभाल": ["maintenance"], "society": ["maintenance", "society"], "charges": ["maintenance", "charges"],
    "रेरा": ["rera"], "मंजूरी": ["approvals"], "मंजुरी": ["approvals"], "approved": ["approvals"], "approval": ["approvals"], "legal": ["approvals", "rera"],
    "loan": ["loans", "banks"], "bank": ["banks", "loans"], "लोन": ["loans", "banks"], "कर्ज": ["loans", "banks"], "बैंक": ["banks", "loans"], "बँक": ["banks", "loans"],
    "tile": ["flooring"], "tiles": ["flooring"], "floor": ["flooring"], "marble": ["flooring"], "spec": ["specifications"], "specs": ["specifications"],
    "quality": ["specifications"], "construction": ["specifications", "construction"], "bathroom": ["bathrooms"], "toilet": ["bathrooms"], "किचन": ["kitchen"], "रसोई": ["kitchen"], "स्वयंपाकघर": ["kitchen"],
    "pajeshan": ["possession"], "पजेशन": ["possession"], "कब्जा": ["possession"], "ताबा": ["possession"], "delivery": ["possession", "handover"], "ready": ["possession", "handover"],
    "gst": ["gst", "charges"], "stamp": ["stamp", "charges"], "registration": ["registration", "charges"], "रजिस्ट्रेशन": ["registration", "charges"],
    "pool": ["amenities", "pool"], "gym": ["amenities", "gym"], "clubhouse": ["amenities", "clubhouse"], "सुविधा": ["amenities"], "suvidha": ["amenities"], "facilities": ["amenities"],
    "nearby": ["nearby"], "paas": ["nearby"], "पास": ["nearby"], "जवळ": ["nearby"],
}  # fmt: skip


@dataclass(frozen=True)
class Passage:
    listing_id: str
    project: str
    section: str
    text: str


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+|[ऀ-ॿ]+", text.casefold())
    return [word.removesuffix("s") if word.isascii() and len(word) > 3 else word for word in words if word not in _STOPWORDS]


def _query_tokens(query: str) -> list[str]:
    found: list[str] = []
    for word in re.findall(r"[a-z0-9]+|[ऀ-ॿ]+", query.casefold()):
        if word in _STOPWORDS:
            continue
        found += _tokens(" ".join(_SYNONYMS.get(word, [word])))
    return list(dict.fromkeys(found))


@lru_cache(maxsize=1)
def _index() -> tuple[tuple[Passage, ...], tuple[Counter, ...], tuple[int, ...], dict[str, int], float]:
    """Every passage with its word counts (title included) and lengths, and how many passages hold each word."""
    passages: list[Passage] = []
    for path in sorted(BROCHURE_DIR.glob("*.md")):
        project, section, lines = "", None, []

        def close() -> None:
            if section and lines:
                passages.append(Passage(path.stem.upper(), project, section, " ".join(lines)))

        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("# "):
                project = line[2:].split(",")[0].strip()
            elif line.startswith("## "):
                close()
                section, lines = line[3:].strip(), []
            elif line and section:
                lines.append(line)
        close()

    counts = tuple(Counter(_tokens(f"{item.section} {item.text}")) for item in passages)
    lengths = tuple(sum(count.values()) for count in counts)
    document_frequency: Counter = Counter(word for count in counts for word in count)
    average = sum(lengths) / len(lengths) if lengths else 1.0
    return tuple(passages), counts, lengths, dict(document_frequency), average


def search(query: str, *, listing_ids: list[str] | None = None, limit: int = 2) -> list[Passage]:
    """The passages that best answer the query, best first; only these homes' brochures when listing_ids is given."""
    passages, counts, lengths, document_frequency, average = _index()
    words = _query_tokens(query)
    wanted = {item.upper() for item in listing_ids} if listing_ids else None
    total = len(passages)
    scored: list[tuple[float, int]] = []
    for position, passage in enumerate(passages):
        if wanted is not None and passage.listing_id not in wanted:
            continue
        score = 0.0
        title = set(_tokens(passage.section))
        for word in words:
            frequency = counts[position].get(word, 0)
            if frequency:
                rarity = math.log(1 + (total - document_frequency[word] + 0.5) / (document_frequency[word] + 0.5))
                score += rarity * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * lengths[position] / average))
                if word in title:
                    score += rarity * TITLE_BONUS
        if score > 0:
            scored.append((score, position))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [passages[position] for _, position in scored[:limit]]
