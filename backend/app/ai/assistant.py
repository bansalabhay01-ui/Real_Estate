"""The property assistant's building blocks: qualifying questions, reply templates and the messages sent to the LLM.

ai/agent.py runs each conversation turn with these. Replies come from the LLM when a key is set and from the templates
here otherwise (English, Hinglish, Hindi and Marathi), and any LLM failure falls back to a template, so the demo never
breaks. Buyer details are saved on the visitor as JSON (visitor.profile) for the dashboard and for scoring.
"""

import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..listings import filter_listings, format_price, format_rupees
from ..models import ChatMessage
from ..schemas import ChatAction, ChatMessageOut, EmiOut, Listing, VisitOut
from .brochures import Passage
from .privacy import mask_pii
from .rag import SearchResult, find_listings

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "assistant_system.md").read_text(encoding="utf-8")
HISTORY_MESSAGES = 8  # earlier messages sent to the LLM for context
SEARCH_KEYS = ("city", "locality", "bhk", "budget_min", "budget_max")

# Qualifying questions, asked one at a time, in this order, for whatever is still unknown.
QUESTION_ORDER = ("city", "bhk", "budget", "timeline", "loan", "purpose")
QUESTIONS = {
    "en": {
        "city": "Which city are you looking in? We have homes in Pune, Bengaluru, Hyderabad, Mumbai and Noida.",
        "bhk": "How many bedrooms do you need: 1, 2, 3 or 4 BHK?",
        "budget": "What budget do you have in mind? For example, under ₹90 L or up to ₹1.5 Cr.",
        "timeline": "When are you planning to move in: right away, within 6 months, or later?",
        "loan": "Will you need a home loan? Each property page has an EMI calculator.",
        "purpose": "Is the home for you to live in, or an investment?",
    },
    "hinglish": {
        "city": "Aap kis city mein ghar dekh rahe hain? Hamare paas Pune, Bengaluru, Hyderabad, Mumbai aur Noida mein ghar hain.",
        "bhk": "Kitne bedroom chahiye: 1, 2, 3 ya 4 BHK?",
        "budget": "Aapka budget kitna hai? Jaise ₹90 L tak ya ₹1.5 Cr tak.",
        "timeline": "Aap kab tak shift karna chahte hain: turant, 6 mahine mein, ya baad mein?",
        "loan": "Kya aapko home loan chahiye? Har property page par EMI calculator hai.",
        "purpose": "Ghar khud rehne ke liye hai ya investment ke liye?",
    },
    "hi": {
        "city": "आप किस शहर में घर देख रहे हैं? हमारे पास पुणे, बेंगलुरु, हैदराबाद, मुंबई और नोएडा में घर हैं।",
        "bhk": "कितने बेडरूम चाहिए: 1, 2, 3 या 4 BHK?",
        "budget": "आपका बजट कितना है? जैसे ₹90 L तक या ₹1.5 Cr तक।",
        "timeline": "आप कब तक शिफ्ट होना चाहते हैं: तुरंत, 6 महीने में या बाद में?",
        "loan": "क्या आपको होम लोन चाहिए? हर प्रॉपर्टी पेज पर EMI कैलकुलेटर है।",
        "purpose": "घर खुद रहने के लिए है या निवेश के लिए?",
    },
    "mr": {
        "city": "तुम्ही कोणत्या शहरात घर पाहत आहात? आमच्याकडे पुणे, बेंगळुरू, हैदराबाद, मुंबई आणि नोएडामध्ये घरे आहेत.",
        "bhk": "किती बेडरूम हवे आहेत: 1, 2, 3 की 4 BHK?",
        "budget": "तुमचे बजेट किती आहे? उदा. ₹90 L पर्यंत किंवा ₹1.5 Cr पर्यंत.",
        "timeline": "तुम्हाला कधी राहायला जायचे आहे: लगेच, 6 महिन्यांत की नंतर?",
        "loan": "तुम्हाला गृहकर्ज हवे आहे का? प्रत्येक घराच्या पानावर EMI कॅल्क्युलेटर आहे.",
        "purpose": "घर स्वतः राहण्यासाठी आहे की गुंतवणुकीसाठी?",
    },
}

TEXT = {
    "en": {
        "about": "About this home: {line}.",
        "similar": "Similar homes nearby:",
        "found_one": "Here is 1 home{criteria}:",
        "found_many": "Here are {count} homes{criteria}:",
        "closest": "I couldn't find an exact match{criteria}, so here are the closest options (I loosened the {relaxed}):",
        "nothing": "I couldn't find a home{criteria} yet.",
        "hello": "Hi! I can help you find a home in Pune, Bengaluru, Hyderabad, Mumbai or Noida.",
        "offer_visit": "Would you like a site visit? Tell me which day suits you and I'll set it up.",
        "emi": "For {project} at {price}: with {down}% down, the loan is {loan}. At {rate}% over {years} years, the EMI comes to about {emi} a month. It's an estimate; your bank decides the final EMI.",
        "brochure": "From the {project} brochure ({section}): {text}",
        "brochure_none": "The {project} brochure doesn't cover that, so the sales team will confirm it for you.",
        "which_home": "Which home do you mean? Tell me the project name, or open its page and ask me there.",
        "visit_form": "Happy to set up a visit to {project}. Pick a day and share your details below, and the sales team will confirm.",
        "visit_pick": "Which day suits you for a visit to {project}? Pick one below.",
        "visit_booked": "Done: I've asked the sales team for a site visit to {project} on {day}, {slot}. They'll confirm on your number.",
        "call_form": "Sure. Share your name and mobile number below and the sales team will call you.",
        "call_known": "Sure. The sales team will call you on the number you shared.",
    },
    "hinglish": {
        "about": "Is ghar ke baare mein: {line}.",
        "similar": "Aas-paas ke milte-julte ghar:",
        "found_one": "Ye 1 ghar mila{criteria}:",
        "found_many": "Ye {count} ghar mile{criteria}:",
        "closest": "Bilkul waisa ghar nahi mila{criteria}, ye sabse kareeb options hain:",
        "nothing": "Abhi aisa koi ghar nahi mila{criteria}.",
        "hello": "Namaste! Main Pune, Bengaluru, Hyderabad, Mumbai ya Noida mein ghar dhoondhne mein aapki madad kar sakta hoon.",
        "offer_visit": "Kya aap site visit karna chahenge? Bataiye kaunsa din theek rahega.",
        "emi": "{project} ({price}) ke liye: {down}% down payment par loan {loan} hoga. {rate}% par {years} saal ke liye EMI lagbhag {emi} mahina aayegi. Ye estimate hai; final EMI bank tay karega.",
        "brochure": "{project} ki brochure ke hisaab se ({section}): {text}",
        "brochure_none": "{project} ki brochure mein ye jaankari nahi hai, sales team aapko confirm kar degi.",
        "which_home": "Aap kaunse ghar ki baat kar rahe hain? Project ka naam bataiye, ya uska page khol kar poochhiye.",
        "visit_form": "{project} ki site visit set kar dete hain. Neeche din chuniye aur apni details dijiye, sales team confirm karegi.",
        "visit_pick": "{project} ke liye kaunsa din theek rahega? Neeche chuniye.",
        "visit_booked": "Ho gaya: {project} ki site visit {day}, {slot} ke liye request kar di hai. Sales team aapke number par confirm karegi.",
        "call_form": "Zaroor. Neeche apna naam aur mobile number dijiye, sales team aapko call karegi.",
        "call_known": "Zaroor. Sales team aapke diye hue number par call karegi.",
    },
    "hi": {
        "about": "इस घर के बारे में: {line}।",
        "similar": "आसपास के मिलते-जुलते घर:",
        "found_one": "आपके लिए 1 घर मिला{criteria}:",
        "found_many": "आपके लिए {count} घर मिले{criteria}:",
        "closest": "बिल्कुल वैसा घर नहीं मिला{criteria}, ये सबसे करीबी विकल्प हैं:",
        "nothing": "अभी ऐसा कोई घर नहीं मिला{criteria}।",
        "hello": "नमस्ते! मैं पुणे, बेंगलुरु, हैदराबाद, मुंबई या नोएडा में घर ढूंढने में आपकी मदद कर सकता हूं।",
        "offer_visit": "क्या आप साइट विज़िट करना चाहेंगे? बताइए कौन सा दिन ठीक रहेगा।",
        "emi": "{project} ({price}) के लिए: {down}% डाउन पेमेंट पर लोन {loan} होगा। {rate}% पर {years} साल के लिए EMI लगभग {emi} महीना आएगी। यह अनुमान है; अंतिम EMI बैंक तय करेगा।",
        "brochure": "{project} की ब्रोशर के अनुसार ({section}): {text}",
        "brochure_none": "{project} की ब्रोशर में यह जानकारी नहीं है, सेल्स टीम आपको पुष्टि कर देगी।",
        "which_home": "आप किस घर की बात कर रहे हैं? प्रोजेक्ट का नाम बताइए, या उसका पेज खोलकर पूछिए।",
        "visit_form": "{project} की साइट विज़िट तय कर देते हैं। नीचे दिन चुनिए और अपनी जानकारी दीजिए, सेल्स टीम पुष्टि करेगी।",
        "visit_pick": "{project} के लिए कौन सा दिन ठीक रहेगा? नीचे चुनिए।",
        "visit_booked": "हो गया: {project} की साइट विज़िट {day}, {slot} के लिए दर्ज कर दी है। सेल्स टीम आपके नंबर पर पुष्टि करेगी।",
        "call_form": "ज़रूर। नीचे अपना नाम और मोबाइल नंबर दीजिए, सेल्स टीम आपको कॉल करेगी।",
        "call_known": "ज़रूर। सेल्स टीम आपके दिए हुए नंबर पर कॉल करेगी।",
    },
    "mr": {
        "about": "या घराबद्दल: {line}.",
        "similar": "जवळपासची अशीच घरे:",
        "found_one": "तुमच्यासाठी 1 घर मिळाले{criteria}:",
        "found_many": "तुमच्यासाठी {count} घरे मिळाली{criteria}:",
        "closest": "अगदी तसे घर मिळाले नाही{criteria}, ही सर्वात जवळची घरे आहेत:",
        "nothing": "सध्या असे घर मिळाले नाही{criteria}.",
        "hello": "नमस्कार! पुणे, बेंगळुरू, हैदराबाद, मुंबई किंवा नोएडामध्ये घर शोधायला मी तुम्हाला मदत करू शकतो.",
        "offer_visit": "तुम्हाला साइट व्हिजिट करायची आहे का? कोणता दिवस सोयीचा आहे ते सांगा.",
        "emi": "{project} ({price}) साठी: {down}% डाउन पेमेंटवर कर्ज {loan} होईल. {rate}% दराने {years} वर्षांसाठी EMI सुमारे {emi} दरमहा येईल. हा अंदाज आहे; अंतिम EMI बँक ठरवेल.",
        "brochure": "{project} च्या माहितीपत्रकानुसार ({section}): {text}",
        "brochure_none": "{project} च्या माहितीपत्रकात ही माहिती नाही, सेल्स टीम तुम्हाला खात्री करून सांगेल.",
        "which_home": "तुम्ही कोणत्या घराबद्दल विचारत आहात? प्रकल्पाचे नाव सांगा, किंवा त्याचे पान उघडून विचारा.",
        "visit_form": "{project} ची साइट व्हिजिट ठरवूया. खाली दिवस निवडा आणि तुमची माहिती द्या, सेल्स टीम खात्री करेल.",
        "visit_pick": "{project} साठी कोणता दिवस सोयीचा आहे? खाली निवडा.",
        "visit_booked": "झाले: {project} ची साइट व्हिजिट {day}, {slot} साठी नोंदवली आहे. सेल्स टीम तुमच्या नंबरवर खात्री करेल.",
        "call_form": "नक्की. खाली तुमचे नाव आणि मोबाइल नंबर द्या, सेल्स टीम तुम्हाला कॉल करेल.",
        "call_known": "नक्की. सेल्स टीम तुम्ही दिलेल्या नंबरवर कॉल करेल.",
    },
}
SLOT_WORDS = {
    "en": {"morning": "morning", "afternoon": "afternoon", "evening": "evening"},
    "hinglish": {"morning": "subah", "afternoon": "dopahar", "evening": "shaam"},
    "hi": {"morning": "सुबह", "afternoon": "दोपहर", "evening": "शाम"},
    "mr": {"morning": "सकाळी", "afternoon": "दुपारी", "evening": "संध्याकाळी"},
}
_BUDGET_WORDS = {
    "hinglish": ("{price} tak", "{price} se upar"),
    "hi": ("{price} तक", "{price} से ऊपर"),
    "mr": ("{price} पर्यंत", "{price} पेक्षा जास्त"),
}


def say(language: str, key: str, **values) -> str:
    return TEXT.get(language, TEXT["en"])[key].format(**values)


def chat_history(visitor_id: str, limit: int = 50) -> list[ChatMessageOut]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage).where(ChatMessage.visitor_id == visitor_id).order_by(ChatMessage.id.desc()).limit(limit)
        )
        return [ChatMessageOut.model_validate(row) for row in reversed(list(rows))]


def recent_history(db: Session, visitor_id: str) -> list[ChatMessage]:
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.visitor_id == visitor_id).order_by(ChatMessage.id.desc()).limit(HISTORY_MESSAGES)
    )
    return list(reversed(list(rows)))


def missing_details(profile: dict) -> list[str]:
    known = {
        "city": "city" in profile,
        "bhk": "bhk" in profile,
        "budget": "budget_max" in profile or "budget_min" in profile,
        "timeline": "timeline_months" in profile,
        "loan": "loan_needed" in profile,
        "purpose": "purpose" in profile,
    }
    return [key for key in QUESTION_ORDER if not known[key]]


def around(home: Listing) -> SearchResult:
    """A home, then up to two similar homes in the same city."""
    similar = [item for item in filter_listings(city=home.city) if item.id != home.id and abs(item.bhk - home.bhk) <= 1]
    similar.sort(key=lambda item: abs(item.price_inr - home.price_inr))
    return SearchResult([home, *similar[:2]])


def search_homes(profile: dict, found: dict, message: str, current: Listing | None) -> SearchResult:
    if current and not any(key in found for key in SEARCH_KEYS):
        return around(current)  # a question on a property page is about that property
    return find_listings(profile, message)


# ---------------------------------------------------------------- LLM mode


def _listing_facts(item: Listing) -> dict:
    return {
        "id": item.id,
        "project": item.project,
        "locality": item.locality,
        "city": item.city,
        "bhk": item.bhk,
        "type": item.property_type,
        "area_sqft": item.area_sqft,
        "price": format_price(item.price_inr),
        "status": item.status,
        "possession": item.possession,
        "amenities": item.amenities,
        "highlights": item.highlights,
    }


def _search_note(result: SearchResult) -> str:
    if not result.listings:
        return "No listings match. Say so and ask what they could change (budget, area or BHK)."
    if result.exact:
        return "These match everything the visitor asked for."
    return "No exact match. Loosened: " + ", ".join(result.relaxed) + "."


def llm_messages(message: str, history: list[ChatMessage], profile: dict, result: SearchResult, current: Listing | None,
                 extras: dict) -> list[dict[str, str]]:
    messages = [{"role": row.role, "content": mask_pii(row.text)} for row in history]
    while messages and messages[0]["role"] != "user":  # a conversation must start with the visitor
        messages.pop(0)
    context = {
        "listings": [_listing_facts(item) for item in result.listings],
        "search_note": _search_note(result),
        "known_details": {key: value for key, value in profile.items() if key != "language"},
        "still_unknown": missing_details(profile),
        "current_page_listing": current.id if current else None,
        **extras,
    }
    content = (
        f"<context>\n{json.dumps(context, ensure_ascii=False, indent=1)}\n</context>\n\n"
        f"<visitor_message>\n{mask_pii(message)}\n</visitor_message>"
    )
    messages.append({"role": "user", "content": content})
    return messages


# ---------------------------------------------------------------- template mode (no key, or the LLM failed)


def _criteria_phrase(profile: dict, language: str = "en") -> str:
    place = ", ".join(value for value in (profile.get("locality"), profile.get("city")) if value)
    low, high = profile.get("budget_min"), profile.get("budget_max")
    if language not in _BUDGET_WORDS:
        parts = [f"in {place}"] if place else []
        if profile.get("bhk"):
            parts.append(f"{profile['bhk']} BHK")
        if low and high:
            parts.append(f"{format_price(low)} to {format_price(high)}")
        elif high:
            parts.append(f"under {format_price(high)}")
        elif low:
            parts.append(f"above {format_price(low)}")
        return (" " + ", ".join(parts)) if parts else ""
    parts = [place] if place else []
    if profile.get("bhk"):
        parts.append(f"{profile['bhk']} BHK")
    upto, above = _BUDGET_WORDS[language]
    if low and high:
        parts.append(f"{format_price(low)} - {format_price(high)}")
    elif high:
        parts.append(upto.format(price=format_price(high)))
    elif low:
        parts.append(above.format(price=format_price(low)))
    return f" ({', '.join(parts)})" if parts else ""


def _listing_line(item: Listing) -> str:
    status = item.status.lower() if item.status != "Under construction" else f"possession {item.possession}"
    return (
        f"{item.project}, {item.locality}: {item.bhk} BHK {item.property_type.lower()}, "
        f"{item.area_sqft:,} sq ft, {format_price(item.price_inr)} ({status})"
    )


def template_reply(profile: dict, result: SearchResult, current: Listing | None, language: str = "en") -> str:
    lines: list[str] = []
    homes = result.listings
    criteria = _criteria_phrase(profile, language)
    if homes and current and homes[0].id == current.id:
        lines.append(say(language, "about", line=_listing_line(current)))
        if len(homes) > 1:
            lines.append(say(language, "similar"))
            lines += [f"{number}. {_listing_line(item)}" for number, item in enumerate(homes[1:], start=1)]
    elif homes:
        if result.exact:
            lines.append(say(language, "found_one" if len(homes) == 1 else "found_many", count=len(homes), criteria=criteria))
        else:
            lines.append(say(language, "closest", criteria=criteria, relaxed=" and ".join(result.relaxed)))
        lines += [f"{number}. {_listing_line(item)}" for number, item in enumerate(homes, start=1)]
    elif any(key in profile for key in SEARCH_KEYS):
        lines.append(say(language, "nothing", criteria=criteria))
    else:
        lines.append(say(language, "hello"))

    missing = missing_details(profile)
    table = QUESTIONS.get(language, QUESTIONS["en"])
    lines.append(table[missing[0]] if missing else say(language, "offer_visit"))
    return "\n".join(lines)


def _short(text: str, limit: int = 340) -> str:
    """The first sentences of a passage, up to about `limit` characters."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sentence in sentences:
        if kept and sum(len(item) + 1 for item in kept) + len(sentence) > limit:
            break
        kept.append(sentence)
    return " ".join(kept)


def emi_sentence(language: str, emi: EmiOut) -> str:
    down = f"{emi.down_payment_pct:g}"
    return say(language, "emi", project=emi.project, price=format_price(emi.price_inr), down=down, loan=format_price(emi.loan_inr),
               rate=f"{emi.rate_pct:g}", years=emi.years, emi=format_rupees(emi.emi_inr))  # fmt: skip


def visit_confirmation(language: str | None, visit: VisitOut) -> str:
    language = language if language in TEXT else "en"
    slot = SLOT_WORDS[language].get(visit.slot, visit.slot)
    return say(language, "visit_booked", project=visit.project, day=visit.day_text, slot=slot)


def template_turn(goal: str, language: str, *, profile: dict, result: SearchResult, current: Listing | None, home: Listing | None,
                  emi: EmiOut | None, passages: list[Passage], action: ChatAction | None) -> str:
    """The reply for this turn when there's no LLM: what the tool found, or the usual homes and next question."""
    if goal == "emi":
        return emi_sentence(language, emi) if emi else say(language, "which_home")
    if goal == "brochure":
        if home is None:
            return say(language, "which_home")
        if passages:
            top = passages[0]
            return say(language, "brochure", project=top.project, section=top.section, text=_short(top.text))
        return say(language, "brochure_none", project=home.project)
    if goal == "site_visit":
        if action is None:
            return say(language, "which_home")
        if action.type == "visit_booked" and action.visit:
            return visit_confirmation(language, action.visit)
        return say(language, "visit_form" if action.need_contact else "visit_pick", project=action.project)
    if goal == "call_me":
        return say(language, "call_form" if action else "call_known")
    return template_reply(profile, result, current, language)
