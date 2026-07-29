# 3. 실제 판단 로직 (현재 핵심)

import re, math
from typing import Dict, Tuple, List

_whitespace = re.compile(r"\s+")

BAD_WORDS: Dict[str, float] = {
    "ㅅㅂ": 1.2, "시발": 1.3, "씨발": 1.3, "병신": 1.3,
    "꺼져": 1.1, "죽어": 1.2, "좆": 1.3,
    "존나": 0.18, "개새": 1.2, "새끼": 1.0, "애미": 1.2,
    "ㄴㅇㅁ": 1.2, "장애인": 1.2,
    "ㅄ": 1.2, "ㅂㅅ": 1.2,  # 병신의 초성 축약형
}

# 우회(공백/기호 삽입) 방어용 구분자. 숫자는 넣지 않는다 —
# 날짜/번호 등 정상 텍스트와의 충돌(예: "23시 발표")이 너무 잦다.
_EVASION_SEP = r"[\s.\-_*]{0,1}"

# 욕설 뒤에 자연스럽게 붙는 조사/어미/결합어. 이런 글자가 바로 뒤에 와도
# (예: "병신아", "새끼놈") 여전히 같은 단어로 취급한다.
_TRAILING_ALLOWED = set("아야이가은는을를도만요다냐네니고며들러려서용거놈년")


def _is_hangul_syllable(ch: str) -> bool:
    return "가" <= ch <= "힣"


def _ew(word: str) -> str:
    """Evasion-tolerant regex fragment for a literal keyword (unescaped, for composing patterns)."""
    return _EVASION_SEP.join(re.escape(c) for c in word)


def _build_evasion_pattern(word: str) -> "re.Pattern[str]":
    return re.compile(_ew(word))


BAD_WORD_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    w: _build_evasion_pattern(w) for w in BAD_WORDS
}


def _count_bad_word_hits(word: str, pattern: "re.Pattern[str]", text: str) -> int:
    """Count matches of `word`, tolerating a single space/./-/_/* between letters.

    A contiguous match (no separator used) is always counted — identical to the
    previous plain substring behavior, so this never removes an existing hit.
    A separated match (e.g. "시 발", "병.신") is only counted when it is not
    clearly a fragment of an unrelated word (e.g. "택시 발레파킹", "신경써줘서").
    """
    count = 0
    word_len = len(word)
    for m in pattern.finditer(text):
        if (m.end() - m.start()) == word_len:
            count += 1
            continue
        start, end = m.start(), m.end()
        if start > 0 and _is_hangul_syllable(text[start - 1]):
            continue
        if end < len(text):
            nxt = text[end]
            if _is_hangul_syllable(nxt) and nxt not in _TRAILING_ALLOWED:
                continue
        count += 1
    return count


TOXIC_PATTERNS: List[Tuple[str, float]] = [
    (r"미친" + _EVASION_SEP + r"(놈|년|새끼|새키)", 1.2),
    (r"미쳤냐", 1.0),
    (r"돌았냐", 0.9),
    (r"(꺼져|닥쳐)\s*(라|라니까|좀)?", 1.1),
    # 손가락 욕 이모지 대용으로 쓰이는 고립된/반복된 'ㅗ' (예: "ㅗㅗㅗ", 단독 "ㅗ")
    (r"(?:^|\s)ㅗ{1,}(?:\s|$)", 1.0),
]

SPAM_PATTERNS: List[Tuple[str, float]] = [
    # 각 키워드 내부에 공백/기호가 끼어드는 우회("카.톡", "무료체 험")를 막기 위해
    # 키워드 하나하나를 evasion-tolerant 조각으로 구성한다. 키워드 사이는
    # 기존처럼 '.*'로 넓게 허용한다.
    (rf"{_ew('무료')}.*({_ew('링크')}|{_ew('상담')}|{_ew('체험')})", 1.1),
    (rf"({_ew('카톡')}|{_ew('카카오톡')}).*({_ew('문의')}|{_ew('상담')}|{_ew('오픈채팅')}|{_ew('링크')})", 1.2),
    (rf"({_ew('돈')}|{_ew('수익')}).*({_ew('벌')}|{_ew('버는')}|{_ew('벌기')})", 1.0),
    (rf"({_ew('구독')}|{_ew('좋아요')}).*({_ew('이벤트')}|{_ew('추첨')}|{_ew('지급')})", 0.9),
]

# UNCERTAIN -> TAUNT (비꼼/조롱)
# 주의: 'ㅋㅋ/ㅎㅎ'는 긍정 반응에서도 매우 흔해서, 단독 신호로는 TAUNT로 확정하지 않도록 보수적으로 둔다.
TAUNT_SIGNALS: List[Tuple[str, float]] = [
    (r"(ㅋ|ㅎ){4,}", 0.22),           # laughter burst (weaker & stricter)
    (r"(진짜|ㄹㅇ|하|참)\b", 0.18),   # mild sarcasm markers
    (r"(뇌절|억까)", 0.30),
    (r"[?]{3,}", 0.20),
    (r"(누가봐도|어휴|ㅋㅋ\s*그래|ㅋㅋ\s*와)", 0.30),  # more explicit taunt phrases
]

# 긍정/응원 신호 (TAUNT 오탐 방지용)
POSITIVE_WORDS: List[str] = [
    "귀엽", "예쁘", "멋지", "잘하", "최고", "짱", "대박", "사랑", "응원", "축하", "고마", "감사",
    "레전드", "쩐다", "좋다", "좋아", "폼", "등장", "퀄", "미쳤다",
]
POSITIVE_EMOJI_RE = re.compile(r"[❤️🧡💛💚💙💜🖤🤍🤎😍🥰😘😊😁😆😄😃👍✨🎉🔥]")
LAUGHTER_ONLY_RE = re.compile(r"^[\sㅋㅎ]+$")

# TAUNT로 덮어쓰기(유지)하면 안 되는 강한 부정 단서
NEGATIVE_CUES: List[str] = [
    "못하", "노답", "역겹", "혐", "꺼져", "죽어", "못생", "망했", "왜저래", "왜 저래", "한심",
]


def has_negative_cues(text: str) -> bool:
    return any(cue in text for cue in NEGATIVE_CUES)

def is_positive_laughter(text: str) -> bool:
    """'ㅋㅋ/ㅎㅎ'가 긍정 반응으로 쓰인 케이스를 최대한 OK로 보내기 위한 가드.
    - 부정 단서가 없고
    - (칭찬 단어 또는 긍정 이모지) 가 있거나
    - 아예 'ㅋㅋㅋ' 같은 웃음만 있는 경우
    """
    if has_negative_cues(text):
        return False
    if any(pw in text for pw in POSITIVE_WORDS):
        return True
    if POSITIVE_EMOJI_RE.search(text):
        return True
    if LAUGHTER_ONLY_RE.match(text) and re.search(r"(ㅋ|ㅎ){2,}", text):
        return True
    return False

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
    has_bad_word = False
    for w, weight in BAD_WORDS.items():
        hits = _count_bad_word_hits(w, BAD_WORD_PATTERNS[w], text)
        if hits:
            has_bad_word = True
            raw += weight * min(hits, 3)
            reasons.append(f"bad_word:{w}*{hits}")

    for pat, weight in TOXIC_PATTERNS:
        if re.search(pat, text):
            has_bad_word = True
            raw += weight
            reasons.append(f"toxic_pat:{pat}")

    # Punctuation burst alone is too noisy for fan comments like "대박!!!" or "예???"
    # so only use it as a booster when the text already looks negative/toxic.
    if (has_bad_word or has_negative_cues(text)) and re.search(r"[!?.]{3,}", text):
        raw += 0.25
        reasons.append("punctuation_burst")

    if is_positive_laughter(text) and raw < 1.0:
        raw = max(0.0, raw - 0.25)
        reasons.append("positive_context_guard")
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
    # 'ㅋㅋ/ㅎㅎ' 단독/긍정 반응 오탐 방지: 이런 케이스는 TAUNT 점수를 크게 낮춘다.
    positive_guard = is_positive_laughter(text)
    for pat, weight in TAUNT_SIGNALS:
        if re.search(pat, text):
            raw += weight
            hit_count += 1
            reasons.append(f"taunt_sig:{pat}")
    if hit_count >= 2:
        raw += 0.20
        reasons.append("taunt_combo_bonus")
    if positive_guard:
        # TAUNT 신호가 있어도(특히 웃음) 긍정으로 보이는 케이스는 TAUNT를 보수적으로 낮춤
        raw = max(0.0, raw - 0.35)
        reasons.append("positive_laughter_guard")
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
