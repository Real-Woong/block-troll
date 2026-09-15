# -*- coding: utf-8 -*-
"""SPAM 룰 회귀 테스트.

실행:
    .venv/bin/python tests/test_spam_rules.py        # 표로 출력, 실패 시 exit 1
    .venv/bin/python -m pytest tests/                # pytest가 있으면 이것도 동작

케이스는 두 묶음으로 나눠 둔다.
  - BASIC_*  : 룰을 설계하면서 함께 만든 케이스.
  - HARD_*   : 룰을 다 짠 뒤에 별도로 만든 케이스. 오탐을 잡아내는 쪽이 목적이라
               미끼 단어를 포함하지만 정상인 댓글이 대부분이다.

모델(ENABLE_MODEL=true)을 켜면 app.py가 룰 점수를 모델과 병합한다.
이 파일은 룰 자체만 검증하므로 모델 상태와 무관하게 통과해야 한다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blocktroll_agent.rules import rule_scores  # noqa: E402

try:
    from blocktroll_agent.config import TH_SPAM
except Exception:  # config 로딩(.env)에 실패해도 기본값으로 돌아간다
    TH_SPAM = 0.65


BASIC_SPAM = [
    "★무료 이벤트★ 지금 클릭 http://bit.ly/xxx 코인 수익 인증",
    "월수익 500 인증합니다 텔레그램 t.me/abcd 로 문의주세요",
    "◆◆ 재택부업 하실분 ◆◆ 카톡아이디 abc123 상담받으세요",
    "먹튀없는 카지노 추천 https://tototo.com 선착순 이벤트",
    "네이버에 김부장주식 검색하세요 급등주 무료 리딩",
    "고수익 알바 구합니다 010-1234-5678 로 연락주세요",
    "원금보장 수익률 300% 지금 클릭 bit.ly/zzz",
    "무료 상담 받아보세요 카톡 문의 주세요",
]

BASIC_OK = [
    "이 영상 진짜 유익하네요 감사합니다",
    "구독하고 좋아요 눌렀어요!",
    "링크 감사합니다 잘 볼게요",
    "네이버에 검색해보니 저도 나오네요 신기하다",
    "이 노래 원곡 링크 https://www.youtube.com/watch?v=abcd 여기 있어요",
    "코인 얘기 나와서 그런데 저도 작년에 물렸어요 ㅋㅋ",
    "19금 아니고 전체관람가입니다",
    "재택근무 중에 보고 있어요 힐링되네요",
    "다음 영상도 기대할게요 방문해주셔서 감사합니다",
    "【공지】 다음주 휴방입니다",
    "선착순으로 댓글 다신 분들 축하드려요",
    "토토가 세대라 그런지 노래가 좋네요",
]

# 키워드 사이에 공백/기호를 끼워 넣는 우회. rules._ew() 방어가 살아있는지 확인한다.
HARD_SPAM = [
    "코 인 리 딩 무료체 험 링크 드립니다 bit.ly/aaa",
    "무.료 상담 카.톡 문의주세요",
    "★★★ 월 수익 인증 ★★★ 텔레그램 @moneyking 지금 클릭",
]

# 미끼 단어를 포함하지만 정상인 댓글. 콤보 보너스가 과하게 걸리면 여기서 깨진다.
HARD_OK = [
    # 아래 케이스 때문에 콤보 조건에 signal_count >= 2 를 넣었다.
    # 미끼 하나 + 링크만으로 확정하면 경제 채널의 평범한 댓글이 전부 걸린다.
    "수익률 계산하는 방법 영상 감사합니다 https://blog.naver.com/finance 여기도 좋아요",
    "선착순 마감임박이라길래 저도 신청했는데 안 되더라고요",
    "카지노 로얄 영화 진짜 명작이죠",
    "주식 종목 분석 영상 잘 봤습니다",
    "부업으로 유튜브 시작했는데 어렵네요",
    "텔레그램으로 친구랑 얘기하다가 이 영상 알게 됐어요",
    "이 링크 방문하세요 https://www.youtube.com/watch?v=xyz 원본입니다",
    "고수익은 아니지만 만족하며 살고 있습니다",
    "구글에 이 노래 제목 검색하면 원곡 나와요",
]


def spam_score(text: str) -> float:
    scores, _raw, _reasons = rule_scores(text)
    return scores["spam"]


def _check(cases, expect_spam):
    """(실패 케이스 목록, 전체 개수) 반환."""
    failures = []
    for text in cases:
        scores, raw, reasons = rule_scores(text)
        score = scores["spam"]
        if (score >= TH_SPAM) != expect_spam:
            failures.append((text, score, raw["spam"], reasons["spam"]))
    return failures, len(cases)


def test_basic_spam_is_blocked():
    failures, _ = _check(BASIC_SPAM, True)
    assert not failures, f"스팸인데 통과: {[f[0] for f in failures]}"


def test_basic_ok_is_not_blocked():
    failures, _ = _check(BASIC_OK, False)
    assert not failures, f"정상인데 차단: {[f[0] for f in failures]}"


def test_evasive_spam_is_blocked():
    failures, _ = _check(HARD_SPAM, True)
    assert not failures, f"우회 스팸이 통과: {[f[0] for f in failures]}"


def test_bait_words_in_normal_comments_are_not_blocked():
    failures, _ = _check(HARD_OK, False)
    assert not failures, f"미끼 단어 포함 정상 댓글이 차단: {[f[0] for f in failures]}"


def test_single_bait_plus_link_stays_below_threshold():
    """미끼 하나 + 링크만으로는 확정되면 안 된다 (콤보 조건 회귀 방지)."""
    score = spam_score("수익률 계산하는 방법 영상 감사합니다 https://blog.naver.com/finance")
    assert score < TH_SPAM, f"단일 미끼+링크가 SPAM으로 확정됨: {score:.3f}"


def test_url_alone_stays_below_threshold():
    score = spam_score("원곡 링크 https://www.youtube.com/watch?v=abcd 입니다")
    assert score < TH_SPAM, f"URL만으로 SPAM 확정됨: {score:.3f}"


def _main() -> int:
    groups = [
        ("기본 스팸", BASIC_SPAM, True),
        ("기본 정상", BASIC_OK, False),
        ("우회 스팸", HARD_SPAM, True),
        ("미끼 포함 정상", HARD_OK, False),
    ]
    total_failed = 0
    total_cases = 0
    print(f"TH_SPAM = {TH_SPAM}")
    for title, cases, expect_spam in groups:
        failures, count = _check(cases, expect_spam)
        total_failed += len(failures)
        total_cases += count
        print(f"\n===== {title} (기대: {'SPAM' if expect_spam else 'OK'}) =====")
        for text in cases:
            scores, raw, reasons = rule_scores(text)
            score = scores["spam"]
            is_spam = score >= TH_SPAM
            ok = is_spam == expect_spam
            print(
                f"{'  ' if ok else '!!'} spam={score:.3f} raw={raw['spam']:.2f} "
                f"{'SPAM' if is_spam else 'OK  '} | {text[:48]}"
            )
            if not ok:
                print(f"      reasons={reasons['spam']}")

    print(f"\n{total_cases - total_failed}/{total_cases} 통과, 실패 {total_failed}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(_main())
