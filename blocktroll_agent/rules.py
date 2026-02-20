import re, math
from typing import Dict, Tuple, List

_whitespace = re.compile(r"\s+")

BAD_WORDS: Dict[str, float] = {
    "ㅅㅂ": 1.2, "시발": 1.3, "씨발": 1.3, "병신": 1.3,
    "미친": 0.8, "꺼져": 1.1, "죽어": 1.2, "좆": 1.3,
    "존나": 0.6, "개새": 1.2, "새끼": 1.0, "애미": 1.2,
    "ㄴㅇㅁ": 1.2, "장애인": 1.2
}

SPAM_PATTERNS: List[Tuple[str, float]] = [
    (r"무료.*(링크|상담|체험)", 1.1),
    (r"(카톡|카카오톡).*(문의|상담|오픈채팅|링크)", 1.2),
    (r"(돈|수익).*(벌|버는|벌기)", 1.0),
    (r"(구독|좋아요).*(이벤트|추첨|지급)", 0.9),
]

# UNCERTAIN -> TAUNT (비꼼/조롱)
TAUNT_SIGNALS: List[Tuple[str, float]] = [
    (r"(ㅋ|ㅎ){3,}", 0.35),
    (r"(진짜|ㄹㅇ|하|참)", 0.20),
    (r"(뇌절|억까)", 0.30),
    (r"[?]{3,}", 0.20),
]

def normalize(t: str) -> str:
    t = (t or "").lower()
    t = _whitespace.sub(" ", t).strip()
    return t

def saturate(raw: float) -> float:
    if raw <= 0:
        return 0.0
    return 1.0 - math.exp(-raw)

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x

def count_substring_hits(text: str, needle: str) -> int:
    return text.count(needle) if needle else 0

def has_url(text: str) -> bool:
    return bool(re.search(r"https?://|www\.|\.(com|net|org|kr)\b", text))

def score_toxic(text: str):
    raw = 0.0
    reasons = []
    for w, weight in BAD_WORDS.items():
        hits = count_substring_hits(text, w)
        if hits:
            raw += weight * min(hits, 3)
            reasons.append(f"bad_word:{w}*{hits}")
    if re.search(r"[!?.]{3,}", text):
        raw += 0.25
        reasons.append("punctuation_burst")
    return saturate(raw), raw, reasons

def score_spam(text: str):
    raw = 0.0
    reasons = []
    for pat, weight in SPAM_PATTERNS:
        if re.search(pat, text):
            raw += weight
            reasons.append(f"spam_pat:{pat}")
    if has_url(text):
        raw += 0.25
        reasons.append("url_present")
    return saturate(raw), raw, reasons

def score_taunt(text: str):
    raw = 0.0
    reasons = []
    hit_count = 0
    for pat, weight in TAUNT_SIGNALS:
        if re.search(pat, text):
            raw += weight
            hit_count += 1
            reasons.append(f"taunt_sig:{pat}")
    if hit_count >= 2:
        raw += 0.20
        reasons.append("taunt_combo_bonus")
    return saturate(raw), raw, reasons

def rule_scores(text: str):
    text = normalize(text)
    toxic_s, toxic_raw, toxic_r = score_toxic(text)
    spam_s,  spam_raw,  spam_r  = score_spam(text)
    taunt_s, taunt_raw, taunt_r = score_taunt(text)

    scores = {"toxic": clamp01(toxic_s), "spam": clamp01(spam_s), "taunt": clamp01(taunt_s)}
    raw = {"toxic": toxic_raw, "spam": spam_raw, "taunt": taunt_raw}
    reasons = {"toxic": toxic_r, "spam": spam_r, "taunt": taunt_r}
    return scores, raw, reasons