"""WhatsApp reservation conversation flow (Arabic + English).

Pure logic, no I/O: `handle_message()` takes the customer's current state
plus their new message and returns the replies to send, the new state, and
(once the customer confirms) a reservation to save. The webhook route does
the database and WhatsApp API work around it.

Flow:
    new/menu ──"book"──▶ ask_name ─▶ ask_date ─▶ ask_time ─▶ ask_guests ─▶ confirm
                                                                         │
                         reservation saved as "pending" ◀──── "yes" ─────┘
    menu ──"info"──▶ hours + location
    menu ──"staff"─▶ handoff (bot stays quiet so a human can reply)

At any point: "menu" / "القائمة" goes back to the menu, "cancel" / "إلغاء"
drops the booking in progress.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

MAX_DAYS_AHEAD = 60
HANDOFF_HOURS = 12

# Button ids (stable, language independent).
BTN_BOOK = "book"
BTN_INFO = "info"
BTN_STAFF = "staff"
BTN_TODAY = "date_today"
BTN_TOMORROW = "date_tomorrow"
BTN_YES = "confirm_yes"
BTN_EDIT = "confirm_edit"
BTN_CANCEL = "confirm_cancel"


@dataclass
class BotSettings:
    business_name: str = "Khayal"
    opening_hours: str = ""
    location: str = ""
    max_party_size: int = 20


@dataclass
class Reply:
    text: str
    buttons: list[tuple[str, str]] | None = None


@dataclass
class Result:
    state: str
    data: dict
    lang: str
    replies: list[Reply] = field(default_factory=list)
    reservation: dict | None = None
    handoff_requested: bool = False


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

T = {
    "welcome": {
        "ar": "أهلاً وسهلاً في {name} 🌙\nكيف نقدر نخدمك؟",
        "en": "Welcome to {name} 🌙\nHow can we help you?",
    },
    "btn_book": {"ar": "حجز طاولة", "en": "Book a table"},
    "btn_info": {"ar": "المواعيد والموقع", "en": "Hours & location"},
    "btn_staff": {"ar": "التحدث مع موظف", "en": "Talk to staff"},
    "menu_hint": {
        "ar": "اكتب *حجز* للحجز، *معلومات* للمواعيد والموقع، أو *موظف* للتحدث معنا.",
        "en": "Type *book* to reserve, *info* for hours & location, or *staff* to talk to us.",
    },
    "ask_name": {"ar": "ممتاز! على أي اسم الحجز؟", "en": "Great! What name should the booking be under?"},
    "bad_name": {"ar": "من فضلك اكتب الاسم (حرفين على الأقل).", "en": "Please send the name (at least 2 letters)."},
    "ask_date": {
        "ar": "شكراً {customer} 🙏\nأي يوم تحب تحجز؟\nاختر أو اكتب التاريخ (مثلاً 15/11).",
        "en": "Thanks {customer} 🙏\nWhich day would you like?\nPick one or type a date (e.g. 15/11).",
    },
    "btn_today": {"ar": "اليوم", "en": "Today"},
    "btn_tomorrow": {"ar": "بكرة", "en": "Tomorrow"},
    "bad_date": {
        "ar": "ما قدرت أفهم التاريخ 🤔 اكتبه هكذا: 15/11 أو \"بكرة\" أو \"الجمعة\".",
        "en": "I couldn't read that date 🤔 Try 15/11, \"tomorrow\" or \"Friday\".",
    },
    "past_date": {"ar": "هذا التاريخ مضى. اختر يوماً قادماً من فضلك.", "en": "That date has passed. Please pick an upcoming day."},
    "far_date": {
        "ar": "نستقبل الحجوزات حتى {days} يوماً مقدماً فقط. اختر تاريخاً أقرب.",
        "en": "We take bookings up to {days} days ahead. Please pick an earlier date.",
    },
    "ask_time": {
        "ar": "{date} 👍\nكم الساعة؟ (مثلاً 8:30 م)",
        "en": "{date} 👍\nWhat time? (e.g. 8:30 pm)",
    },
    "bad_time": {"ar": "اكتب الوقت هكذا: 9 م أو 21:00", "en": "Please send a time like 9 pm or 21:00"},
    "past_time": {"ar": "هذا الوقت مضى اليوم. اختر وقتاً لاحقاً.", "en": "That time has already passed today. Please pick a later time."},
    "ask_guests": {"ar": "كم عدد الأشخاص؟", "en": "How many guests?"},
    "bad_guests": {
        "ar": "اكتب عدد الأشخاص كرقم من 1 إلى {max}.",
        "en": "Please send the number of guests (1 to {max}).",
    },
    "too_many_guests": {
        "ar": "للمجموعات أكثر من {max} أشخاص، اكتب *موظف* وسيتواصل معك فريقنا.",
        "en": "For groups larger than {max}, type *staff* and our team will help you.",
    },
    "summary": {
        "ar": "تأكيد الحجز 📋\n👤 الاسم: {customer}\n📅 التاريخ: {date}\n🕘 الوقت: {time}\n👥 العدد: {guests}\n\nهل البيانات صحيحة؟",
        "en": "Booking summary 📋\n👤 Name: {customer}\n📅 Date: {date}\n🕘 Time: {time}\n👥 Guests: {guests}\n\nIs everything correct?",
    },
    "btn_yes": {"ar": "تأكيد ✅", "en": "Confirm ✅"},
    "btn_edit": {"ar": "تعديل ✏️", "en": "Edit ✏️"},
    "btn_cancel": {"ar": "إلغاء", "en": "Cancel"},
    "confirm_hint": {"ar": "اضغط *تأكيد* أو *تعديل* أو *إلغاء*.", "en": "Tap *Confirm*, *Edit* or *Cancel*."},
    "received": {
        "ar": "تم استلام طلب الحجز ✅\nسنرسل لك تأكيداً قريباً. شكراً لاختيارك {name}!",
        "en": "Your booking request is in ✅\nWe'll send you a confirmation shortly. Thank you for choosing {name}!",
    },
    "cancelled": {"ar": "تم إلغاء الحجز. نحن بالخدمة متى ما احتجت 🌙", "en": "Booking cancelled. We're here whenever you need us 🌙"},
    "info": {
        "ar": "🕘 المواعيد:\n{hours}\n\n📍 الموقع:\n{location}",
        "en": "🕘 Opening hours:\n{hours}\n\n📍 Location:\n{location}",
    },
    "info_missing": {"ar": "سيتم إضافتها قريباً", "en": "Coming soon"},
    "handoff": {
        "ar": "تمام، سيرد عليك أحد أفراد فريقنا قريباً 🙏\n(اكتب *القائمة* للعودة للحجز الآلي)",
        "en": "Sure, a team member will reply to you shortly 🙏\n(Type *menu* to go back to automatic booking)",
    },
    "status_confirmed": {
        "ar": "تم تأكيد حجزك في {name} ✅\n📅 {date} — 🕘 {time}\n👥 {guests} أشخاص\nبانتظارك!",
        "en": "Your booking at {name} is confirmed ✅\n📅 {date} — 🕘 {time}\n👥 {guests} guests\nSee you soon!",
    },
    "status_declined": {
        "ar": "نعتذر، لا يتوفر مكان في {date} الساعة {time} 🙏\nاكتب *حجز* لاختيار موعد آخر.",
        "en": "Sorry, we're fully booked on {date} at {time} 🙏\nType *book* to choose another time.",
    },
}

AR_WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
EN_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def t(key: str, lang: str, **kwargs) -> str:
    return T[key][lang].format(**kwargs)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_LETTER = re.compile(r"[؀-ۿ]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def normalize(text: str) -> str:
    """Lowercase, Western digits, unify alef/ya/ta-marbuta variants, trim."""

    text = (text or "").translate(_DIGITS).strip().lower()
    text = re.sub("[إأآ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub("[ً-ْ]", "", text)  # tashkeel
    return text


def detect_lang(text: str, fallback: str) -> str:
    if _ARABIC_LETTER.search(text or ""):
        return "ar"
    if _LATIN_LETTER.search(text or ""):
        return "en"
    return fallback


def _has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


BOOK_WORDS = ["book", "reserv", "table", "حجز", "احجز", "طاوله", "طاولة"]
INFO_WORDS = ["info", "hour", "open", "location", "address", "where", "معلومات", "موقع", "عنوان", "مواعيد", "دوام", "وين", "متي"]
STAFF_WORDS = ["staff", "human", "agent", "person", "موظف", "شخص حقيقي", "خدمه العملاء"]
MENU_WORDS = ["menu", "start", "القائمه", "قائمه", "البدايه"]
CANCEL_WORDS = ["cancel", "stop", "الغاء", "الغ", "وقف"]
YES_WORDS = ["yes", "yep", "ok", "okay", "confirm", "correct", "نعم", "اي", "ايوه", "تمام", "اكيد", "صح", "تاكيد", "موافق"]
EDIT_WORDS = ["edit", "change", "no", "تعديل", "عدل", "غير", "لا"]

TODAY_WORDS = ["today", "tonight", "اليوم", "الليله"]
TOMORROW_WORDS = ["tomorrow", "tmrw", "بكره", "بكرا", "بكرة", "غدا", "باكر", "بعد بكره"]

_EN_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_AR_DAYS = ["اثنين", "ثلاثاء", "اربعاء", "خميس", "جمعه", "سبت", "احد"]


def parse_date(text: str, today: date) -> date | None:
    text = normalize(text)
    if not text:
        return None

    if "بعد بكره" in text or "بعد بكرا" in text or "day after tomorrow" in text:
        return today + timedelta(days=2)
    if _has_any(text, TOMORROW_WORDS):
        return today + timedelta(days=1)
    if _has_any(text, TODAY_WORDS):
        return today

    for weekday, (en, ar) in enumerate(zip(_EN_DAYS, _AR_DAYS)):
        if en in text or en[:3] == text[:3] and len(text) <= 4 or ar in text:
            return today + timedelta(days=(weekday - today.weekday()) % 7)

    match = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        return _safe_date(year, month, day)

    # Day first (15/11, 15-11-2026, 15.11.26) — the common format in the region.
    match = re.search(r"\b(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2,4}))?\b", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        if match.group(3):
            year = int(match.group(3))
            year = year + 2000 if year < 100 else year
            return _safe_date(year, month, day)
        candidate = _safe_date(today.year, month, day)
        if candidate and candidate < today:
            candidate = _safe_date(today.year + 1, month, day)
        return candidate

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


_PM_WORDS = ["pm", "p.m", "م", "مساء", "مسا", "بالليل", "ليلا", "العصر", "الظهر", "بليل"]
_AM_WORDS = ["am", "a.m", "ص", "صباحا", "الصبح", "صباح", "الفجر"]


def parse_time(text: str) -> str | None:
    """Return "HH:MM" (24h). Without am/pm, 1–11 is read as evening — the
    summary shows the result so the customer can correct it."""

    text = normalize(text)
    match = re.search(r"(\d{1,2})(?:\s*[:.]\s*(\d{2}))?", text)
    if not match:
        if _has_any(text, ["noon", "الظهر"]):
            return "12:00"
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    rest = " " + text[match.end():] + " "
    is_pm = _has_any(rest, [f" {w}" for w in _PM_WORDS]) or re.search(r"\d\s*(pm|م)\b", text)
    is_am = _has_any(rest, [f" {w}" for w in _AM_WORDS]) or re.search(r"\d\s*(am|ص)\b", text)

    if minute > 59 or hour > 23:
        return None
    if hour <= 12:
        if is_am:
            hour = 0 if hour == 12 else hour
        elif is_pm or (1 <= hour <= 11):
            hour = hour if hour == 12 else hour + 12
    return f"{hour:02d}:{minute:02d}"


_GUEST_WORDS = {
    "واحد": 1, "شخص": 1, "لحالي": 1, "one": 1, "just me": 1,
    "شخصين": 2, "اثنين": 2, "اثنان": 2, "ثنين": 2, "two": 2, "couple": 2,
    "ثلاثه": 3, "three": 3, "اربعه": 4, "four": 4, "خمسه": 5, "five": 5,
    "سته": 6, "six": 6, "سبعه": 7, "seven": 7, "ثمانيه": 8, "eight": 8,
    "تسعه": 9, "nine": 9, "عشره": 10, "ten": 10,
}


def parse_guests(text: str) -> int | None:
    text = normalize(text)
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    # Longest phrase first so "شخصين" wins over "شخص".
    for word in sorted(_GUEST_WORDS, key=len, reverse=True):
        if word in text:
            return _GUEST_WORDS[word]
    return None


def format_date(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso)
    weekday = (AR_WEEKDAYS if lang == "ar" else EN_WEEKDAYS)[d.weekday()]
    return f"{weekday} {d.day:02d}/{d.month:02d}/{d.year}"


def format_time(hhmm: str, lang: str) -> str:
    hour, minute = (int(x) for x in hhmm.split(":"))
    suffix = ("ص" if hour < 12 else "م") if lang == "ar" else ("AM" if hour < 12 else "PM")
    return f"{(hour % 12) or 12}:{minute:02d} {suffix}"


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


def menu_reply(lang: str, settings: BotSettings) -> Reply:
    return Reply(
        t("welcome", lang, name=settings.business_name) + "\n\n" + t("menu_hint", lang),
        [(BTN_BOOK, t("btn_book", lang)), (BTN_INFO, t("btn_info", lang)), (BTN_STAFF, t("btn_staff", lang))],
    )


def info_reply(lang: str, settings: BotSettings) -> Reply:
    missing = t("info_missing", lang)
    return Reply(t("info", lang, hours=settings.opening_hours or missing, location=settings.location or missing))


def _date_question(lang: str, customer: str) -> Reply:
    return Reply(
        t("ask_date", lang, customer=customer),
        [(BTN_TODAY, t("btn_today", lang)), (BTN_TOMORROW, t("btn_tomorrow", lang))],
    )


def _summary(lang: str, data: dict) -> Reply:
    return Reply(
        t(
            "summary",
            lang,
            customer=data["name"],
            date=format_date(data["date"], lang),
            time=format_time(data["time"], lang),
            guests=data["guests"],
        ),
        [(BTN_YES, t("btn_yes", lang)), (BTN_EDIT, t("btn_edit", lang)), (BTN_CANCEL, t("btn_cancel", lang))],
    )


def status_message(status: str, reservation: dict, business_name: str) -> str | None:
    """Text sent to the customer when staff confirm/decline in the dashboard."""

    if status not in ("confirmed", "declined"):
        return None
    lang = reservation.get("lang") or "ar"
    return t(
        f"status_{status}",
        lang,
        name=business_name,
        date=format_date(reservation["date"], lang),
        time=format_time(reservation["time"], lang),
        guests=reservation["guests"],
    )


def handle_message(
    state: str,
    data: dict,
    lang: str,
    text: str,
    button_id: str | None,
    now: datetime,
    settings: BotSettings,
) -> Result:
    data = dict(data or {})
    norm = normalize(text)
    button = button_id or ""

    # Language follows the customer, except mid-booking where a name or a
    # bare number shouldn't flip it.
    if state in ("new", "menu", "handoff") and not button:
        lang = detect_lang(text, lang or "ar")
    lang = lang if lang in ("ar", "en") else "ar"

    def result(new_state: str, *replies: Reply, **extra) -> Result:
        return Result(state=new_state, data=data, lang=lang, replies=list(replies), **extra)

    # --- global commands -------------------------------------------------
    if norm in MENU_WORDS or norm == "0":
        data.clear()
        return result("menu", menu_reply(lang, settings))

    if state.startswith("ask_") or state == "confirm":
        if button == BTN_CANCEL or norm in CANCEL_WORDS:
            data.clear()
            return result("menu", Reply(t("cancelled", lang)))

    # --- human handoff: stay quiet so staff can answer --------------------
    if state == "handoff":
        since = data.get("handoff_at")
        if since and now - datetime.fromisoformat(since) < timedelta(hours=HANDOFF_HOURS):
            return result("handoff")
        data.clear()
        state = "menu"

    # --- booking steps ---------------------------------------------------
    if state == "ask_name":
        name = " ".join(text.split())
        if len(name) < 2 or len(name) > 60 or name.isdigit():
            return result("ask_name", Reply(t("bad_name", lang)))
        data["name"] = name
        return result("ask_date", _date_question(lang, name))

    if state == "ask_date":
        today = now.date()
        if button == BTN_TODAY:
            chosen = today
        elif button == BTN_TOMORROW:
            chosen = today + timedelta(days=1)
        else:
            chosen = parse_date(text, today)
        if chosen is None:
            return result("ask_date", Reply(t("bad_date", lang)))
        if chosen < today:
            return result("ask_date", Reply(t("past_date", lang)))
        if chosen > today + timedelta(days=MAX_DAYS_AHEAD):
            return result("ask_date", Reply(t("far_date", lang, days=MAX_DAYS_AHEAD)))
        data["date"] = chosen.isoformat()
        return result("ask_time", Reply(t("ask_time", lang, date=format_date(data["date"], lang))))

    if state == "ask_time":
        hhmm = parse_time(text)
        if hhmm is None:
            return result("ask_time", Reply(t("bad_time", lang)))
        if data.get("date") == now.date().isoformat() and hhmm <= now.strftime("%H:%M"):
            return result("ask_time", Reply(t("past_time", lang)))
        data["time"] = hhmm
        return result("ask_guests", Reply(t("ask_guests", lang)))

    if state == "ask_guests":
        guests = parse_guests(text)
        if guests is None or guests < 1:
            return result("ask_guests", Reply(t("bad_guests", lang, max=settings.max_party_size)))
        if guests > settings.max_party_size:
            return result("ask_guests", Reply(t("too_many_guests", lang, max=settings.max_party_size)))
        data["guests"] = guests
        return result("confirm", _summary(lang, data))

    if state == "confirm":
        if button == BTN_YES or norm in YES_WORDS:
            reservation = {
                "name": data["name"],
                "date": data["date"],
                "time": data["time"],
                "guests": data["guests"],
                "lang": lang,
            }
            data.clear()
            return result("menu", Reply(t("received", lang, name=settings.business_name)), reservation=reservation)
        if button == BTN_EDIT or norm in EDIT_WORDS:
            data.clear()
            return result("ask_name", Reply(t("ask_name", lang)))
        return result("confirm", Reply(t("confirm_hint", lang)), _summary(lang, data))

    # --- menu ------------------------------------------------------------
    if button == BTN_BOOK or norm == "1" or _has_any(norm, BOOK_WORDS):
        data.clear()
        return result("ask_name", Reply(t("ask_name", lang)))

    if button == BTN_INFO or norm == "2" or _has_any(norm, INFO_WORDS):
        return result("menu", info_reply(lang, settings), menu_reply(lang, settings))

    if button == BTN_STAFF or norm == "3" or _has_any(norm, STAFF_WORDS):
        data.clear()
        data["handoff_at"] = now.isoformat()
        return result("handoff", Reply(t("handoff", lang)), handoff_requested=True)

    return result("menu", menu_reply(lang, settings))
