# -*- coding: utf-8 -*-
"""공개 데이터 → 10주제 × 5문항.

**모든 숫자는 raw/ 의 원본에서 계산합니다.** 지어낸 값이 하나도 없어야 합니다.
결과는 앱이 읽는 topics/*.json 과, 사람이 읽는 tools/정답지.md 로 나갑니다.

정답지와 이 스크립트는 .vercelignore 에 들어 있어 **배포되지 않습니다.**
공개 URL 에 정답지가 올라가면 게임이 성립하지 않습니다.

실행 (저장소 최상위에서):
    python tools/build_topics.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import datetime as dt
from collections import Counter
from pathlib import Path
from statistics import mean

# 윈도우 콘솔(cp949)은 이모지 · 기호를 못 찍고 멈춘다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent                                # 저장소 최상위 = 배포되는 곳
RAW = APP / "data" / "raw"
OUT = APP / "topics"

TOPICS: list[dict] = []


def load_json(name):
    return json.load(io.open(RAW / name, encoding="utf-8"))


def load_csv(name):
    return list(csv.DictReader(io.open(RAW / name, encoding="utf-8")))


# World Bank·OWID 응답에는 '유럽연합' '고소득국' 같은 **집계치**가 섞여 있다.
# 그대로 순위를 매기면 나라와 대륙을 한 줄에 놓고 세는 셈이 된다.
REAL = {x["id"] for x in load_json("wb_countries.json")[1]
        if x["region"]["id"] != "NA"}


def wb_countries(rows, year):
    """그 해의 실제 국가 값만 남긴다 (집계치 제외)."""
    return {r["country"]["value"]: r["value"] for r in rows
            if int(r["date"]) == year and r["countryiso3code"] in REAL}


def owid_countries(rows, year, col):
    """OWID 도 마찬가지. code 가 비었거나 OWID_ 로 시작하면 집계치다."""
    return {r["entity"]: float(r[col]) for r in rows
            if int(r["year"]) == year and r["code"]
            and not r["code"].startswith("OWID")}


def topic(tid, emoji, title, blurb, source, source_url, questions, caveat=""):
    """caveat = 이 데이터를 믿을 때의 한계. 앱 화면에도 그대로 나간다.

    출처가 다르면 같은 '서울 기온'도 값이 다르다. 그 사실을 감추지 않는다.
    """
    TOPICS.append({"id": tid, "emoji": emoji, "title": title, "blurb": blurb,
                   "source": source, "source_url": source_url,
                   "caveat": caveat, "questions": questions})


def slider(qid, text, answer, unit, lo, hi, step, basis, why, limit=""):
    q = {"id": qid, "type": "slider", "text": text, "unit": unit,
         "min": lo, "max": hi, "step": step,
         "answer": round(float(answer), 1), "basis": basis, "why": why}
    return {**q, "limit": limit} if limit else q


def choice(qid, text, options, answer, basis, why, limit=""):
    """limit = 이 문항의 정답이 흔들릴 수 있는 이유. 앱의 «근거 보기» 안에 나온다."""
    assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
    q = {"id": qid, "type": "choice", "text": text, "options": options,
         "answer": answer, "basis": basis, "why": why}
    return {**q, "limit": limit} if limit else q


# ════════════════════════════════════════════════════════════════
# 노동법 · 4대 보험 — 13주제
# ════════════════════════════════════════════════════════════════
# 원본은 국가법령정보센터에서 받은 법령을 tools/law_to_json.py 로 바꾼 data/raw/<법>.json.
# **정답은 현행 조문에서 정규식으로 뽑는다.** 코드에는 «몇 조 몇 항에서 무엇을 찾는가»만 적는다.
# 시행 예정본이 있는 조문은 거기서도 같은 값이 나오는지 확인하고, 다르면 멈춘다.
#
# 국민연금의 «60세부터 지급» · «보험료 1천분의 130» 은 본문 숫자지만 부칙의 출생연도별 ·
# 연도별 경과 규정이 실제 값을 바꾼다. 부칙은 담지 않았으므로 그런 숫자는 문항으로 쓰지 않는다.
#
# 이 블록만 계산한다:  python tools/build_topics.py
# 예전 11주제까지 다시 계산하려면:  python tools/build_topics.py --legacy
import re

LAWS: dict = {}
HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
USED: list = []     # (법, 조) — 주제가 쓴 조문. 한계 문장에 시행일 · 예정 개정을 적는 데 쓴다


def law(name):
    if name not in LAWS:
        LAWS[name] = load_json(f"{name}.json")
    return LAWS[name]


def jo(name, no, status="현행"):
    found = [a for a in law(name)["articles"]
             if a["no"] == no and a["status"] == status]
    assert len(found) <= 1, f"{name} {no}: {status} 조문이 둘 이상입니다"
    return found[0]["text"] if found else None


def hang(text, n):
    """①… 항 하나만 남긴다. 항 표시가 없는 조문은 통째로 1항이다."""
    out, cur = [], 1
    for ln in text.splitlines():
        if ln[:1] in HANG:
            cur = HANG.index(ln[0]) + 1
        if cur == n:
            out.append(ln)
    return "\n".join(out)


def won(s):
    """«1천만원» · «500만원» · «10억원» → 만 원 단위"""
    unit = {"억": 10000, "천만": 1000, "백만": 100, "만": 1, "": 1}
    return sum(int(d) * unit[u] for d, u in re.findall(r"(\d+)(억|천만|백만|만)?", s))


def pick(name, no, pattern, n=None, conv=int):
    """현행 조문(n 이 있으면 그 항)에서 pattern 의 첫 묶음을 뽑는다."""
    USED.append((name, no))
    vals = []
    for status in ("현행", "예정"):
        text = jo(name, no, status)
        if text is None:
            continue
        part = hang(text, n) if n else text
        m = re.search(pattern, part)
        if m is None and status == "예정":
            m = re.search(pattern, text)       # 예정본은 항이 끼어들어 번호가 밀리기도 한다
        assert m, f"{name} {no} {n or ''}항 ({status}): «{pattern}» 이 없습니다"
        vals.append(conv(m[1]))
    assert len(set(vals)) == 1, f"{name} {no}: 현행 {vals[0]} ≠ 시행 예정본 {vals[1]}"
    return vals[0]


def has(name, no, phrase, n=None):
    USED.append((name, no))
    text = jo(name, no)
    return phrase in (hang(text, n) if n else text)


def cite(name, no, n=None):
    L = law(name)
    y, m, d = L["enforced"].split("-")
    return f"{L['short']}({int(y)}. {int(m)}. {int(d)}. 시행) {no}" + (f"제{n}항" if n else "")


def dotted(iso):
    y, m, d = iso.split("-")
    return f"{int(y)}. {int(m)}. {int(d)}."


def as_of():
    """이 주제가 쓴 조문의 시행일과 시행 예정 개정으로 «언제 기준인가» 한 문장을 만든다.

    예정본은 pick() 이 이미 같은 값인지 확인했으므로 «정답을 바꾸지 않는다»고 적는다.
    """
    used = list(dict.fromkeys(USED))
    USED.clear()
    laws = list(dict.fromkeys(n for n, _ in used))
    base = ", ".join(f"{law(n)['short']} {dotted(law(n)['enforced'])} 시행" for n in laws)
    soon = sorted({(a["effective"], law(n)["short"], no) for n, no in used
                   for a in law(n)["articles"]
                   if a["no"] == no and a["status"] == "예정" and a["effective"]})
    head = f"2026년 11월 기준 최신 개정 법령({base})을 기준으로 한 것으로, "
    if not soon:
        return head + "이후 법 개정에 따라 답이 변경될 수 있습니다."
    planned = ", ".join(f"{s} {no}({dotted(eff)})" for eff, s, no in soon)
    return head + (f"{planned} 시행 예정 개정은 이 주제의 정답을 바꾸지 않지만 그 밖의 "
                   f"이후 법 개정에 따라 답이 변경될 수 있습니다.")


def law_topic(tid, emoji, title, blurb, names, questions, caveat=""):
    main_law = names[0]
    src = " · ".join(law(x)["short"] for x in names)
    topic(tid, emoji, title, blurb, f"국가법령정보센터 {src}",
          f"https://www.law.go.kr/법령/{law(main_law)['law']}", questions,
          caveat=(caveat + " " if caveat else "") + as_of() +
          " 법률 자문이 아닙니다. 회사 규정 · 단체협약이 더 유리하면 그쪽이 적용됩니다.")


KLS, RET, FIX, GEN = "근로기준법", "근로자퇴직급여 보장법", \
    "기간제 및 단시간근로자 보호 등에 관한 법률", "남녀고용평등법"
MW, SAFE = "최저임금법", "중대재해 처벌 등에 관한 법률"
EI, NP, NHI = "고용보험법", "국민연금법", "국민건강보험법"
SMALL = "근로기준법은 상시 5명 이상 사업장에 적용되고, 4명 이하 사업장은 일부만 적용됩니다."

# 2027년 최저임금 — 법률이 아니라 고시라서 최저임금위원회 «연도별 최저임금 결정현황» 표에서 뽑는다
_mw = re.sub(r"<[^>]+>", " ", io.open(RAW / "minimum_wage.html", encoding="utf-8").read())
_mw = " ".join(_mw.split())


def min_wage(yy):
    m = re.search(rf"'{yy}\.01\.01 ~'{yy}\.12\.31 ([\d,]+) [\d,]+ [\d,]+ ([\d.]+) "
                  rf"\(([\d,]+)\) [\d.]+ ([\d.]+)", _mw)
    assert m, f"최저임금 결정현황에서 20{yy}년 행을 찾지 못했습니다"
    return {"hour": int(m[1].replace(",", "")), "rise": m[2], "up": m[3], "notice": m[4]}


def build_labor():
    # ── 1. 연차 ─────────────────────────────────────────────────────
    a_base = pick(KLS, "제60조", r"(\d+)일의 유급휴가", 1)
    a_every = pick(KLS, "제60조", r"계속 근로 연수 매 (\d+)년에 대하여", 4)
    a_add = pick(KLS, "제60조", r"매 \d+년에 대하여 (\d+)일을 가산", 4)
    a_cap = pick(KLS, "제60조", r"총 휴가 일수는 (\d+)일을 한도", 4)
    a_gone = pick(KLS, "제60조", r"휴가는 (\d+)년간", 7)

    def leave(years):                      # years 년을 꽉 채운 사람의 연차
        return min(a_cap, a_base + (years - 1) // a_every * a_add) if years >= 1 else 0

    a10 = leave(10)
    a_full = next(y for y in range(1, 100) if leave(y) >= a_cap)
    law_topic(
        "labor-leave", "🏖️", "연차유급휴가의 모든 것",
        "며칠 생기고, 언제 늘고, 언제 사라지나", [KLS], [
            slider("lv1", "1년간 80% 이상 출근한 사람에게 생기는 연차는 며칠일까요?",
                   a_base, "일", 0, 30, 1,
                   f"{cite(KLS, '제60조', 1)}에서 «○일의 유급휴가»를 뽑으면 {a_base}일",
                   "주 5일 근무로 치면 3주에 해당합니다. 생각보다 많다고 느끼는 사람이 많습니다."),
            slider("lv2", "연차는 최대 며칠까지 늘어날 수 있을까요?",
                   a_cap, "일", 0, 40, 1,
                   f"{cite(KLS, '제60조', 4)}에서 «총 휴가 일수는 ○일을 한도»를 뽑으면 {a_cap}일",
                   "오래 다니면 끝없이 늘 것 같지만 상한이 있습니다."),
            slider("lv3", "10년을 꽉 채운(11년차) 직원의 연차는 며칠일까요?",
                   a10, "일", 0, 40, 1,
                   f"{cite(KLS, '제60조')}의 기본 {a_base}일에 «최초 1년을 초과하는 계속 근로 연수 "
                   f"매 {a_every}년에 {a_add}일 가산»을 적용해 (10−1)÷{a_every}의 몫만큼 더하면 {a10}일",
                   "1년마다 하루씩 는다고 생각하기 쉽지만, 2년에 하루씩 늘어납니다."),
            slider("lv4", "몇 년을 꽉 채워 일하면 연차가 처음으로 최대치가 될까요?",
                   a_full, "년", 0, 40, 1,
                   f"lv3 과 같은 계산을 1년부터 한 해씩 늘려 «한도 {a_cap}일»에 처음 닿는 해를 찾으면 "
                   f"{a_full}년",
                   "2년에 하루씩이라 최대치까지는 20년이 넘게 걸립니다.",
                   limit=f"«꽉 채운 햇수»로 셌습니다. «입사 ○년째 해»로 세면 "
                         f"{next(y for y in range(1, 100) if leave(y - 1) >= a_cap)}년째부터입니다."),
            slider("lv5", "쓰지 않은 연차는 몇 년이 지나면 사라질까요?",
                   a_gone, "년", 0, 5, 1,
                   f"{cite(KLS, '제60조', 7)}에서 «휴가는 ○년간 행사하지 아니하면 소멸»을 뽑으면 "
                   f"{a_gone}년 (회사 탓으로 못 쓴 경우는 예외)",
                   "모아 두면 쌓인다고 생각하기 쉽지만, 기본은 1년 안에 쓰는 것입니다.",
                   limit="휴가를 쓸 권리는 사라져도, 회사가 제61조의 사용 촉진 절차를 밟지 않았다면 "
                         "못 쓴 연차를 수당으로 받을 수 있습니다."),
        ], caveat=SMALL + " 연차 조항은 4명 이하 사업장에는 적용되지 않습니다.")

    # ── 2. 퇴직금 ───────────────────────────────────────────────────
    r_year = pick(RET, "제4조", r"계속근로기간이 (\d+)년 미만", 1)
    r_hour = pick(RET, "제4조", r"1주간의 소정근로시간이 (\d+)시간 미만", 1)
    r_days = pick(RET, "제8조", r"(\d+)일분 이상의 평균임금", 1)
    r_pay = pick(RET, "제9조", r"(\d+)일 이내에 퇴직금", 1)
    r_exp = pick(RET, "제10조", r"(\d+)년간 행사하지")
    law_topic(
        "labor-retire", "💼", "퇴직과 퇴직금 제대로 알기",
        "누가, 얼마를, 언제까지 받나", [RET], [
            slider("rt1", "퇴직금을 받으려면 최소 몇 년을 일해야 할까요?",
                   r_year, "년", 0, 5, 1,
                   f"{cite(RET, '제4조', 1)}에서 «계속근로기간이 ○년 미만인 근로자»는 제외되므로 "
                   f"{r_year}년",
                   "11개월 29일을 일하고 그만두면 퇴직금이 없습니다. 하루 차이가 큽니다."),
            slider("rt2", "1주에 최소 몇 시간을 일해야 퇴직금 대상이 될까요?",
                   r_hour, "시간", 0, 40, 1,
                   f"{cite(RET, '제4조', 1)}에서 «4주간 평균 1주 소정근로시간이 ○시간 미만»은 "
                   f"제외되므로 {r_hour}시간",
                   "아르바이트도 이 기준을 넘으면 퇴직금 대상입니다."),
            slider("rt3", "1년 일할 때마다 평균임금 며칠분을 퇴직금으로 받을까요?",
                   r_days, "일분", 0, 90, 1,
                   f"{cite(RET, '제8조', 1)}에서 «계속근로기간 1년에 대하여 ○일분 이상의 "
                   f"평균임금»을 뽑으면 {r_days}일분",
                   "대략 «1년에 한 달 치»입니다. 기준은 기본급이 아니라 평균임금입니다.",
                   limit="원문은 «○일분 이상»으로 법이 정한 최소 기준입니다. 회사 규정이 더 많이 "
                         "주도록 정했다면 그쪽이 적용됩니다."),
            slider("rt4", "퇴직하면 며칠 안에 퇴직금을 받아야 할까요?",
                   r_pay, "일", 0, 60, 1,
                   f"{cite(RET, '제9조', 1)}에서 «지급사유가 발생한 날부터 ○일 이내»를 뽑으면 "
                   f"{r_pay}일 (당사자 합의로 연장 가능)",
                   "«다음 월급날에 주겠다»는 말이 법의 기한보다 늦을 수 있습니다."),
            slider("rt5", "받지 못한 퇴직금은 몇 년 안에 청구해야 할까요?",
                   r_exp, "년", 0, 10, 1,
                   f"{cite(RET, '제10조')}에서 «○년간 행사하지 아니하면 시효로 소멸»을 뽑으면 "
                   f"{r_exp}년",
                   "언제든 받을 수 있을 것 같지만, 시효가 지나면 권리가 사라집니다."),
        ])

    # ── 3. 근로시간 ─────────────────────────────────────────────────
    h_week = pick(KLS, "제50조", r"(\d+)시간을 초과할 수 없다", 1)
    h_ot = pick(KLS, "제53조", r"1주 간에 (\d+)시간을 한도", 1)
    h_rest = pick(KLS, "제54조", r"8시간인 경우에는 (\d+)시간 이상", 1)
    h_rest4 = pick(KLS, "제54조", r"4시간인 경우에는 (\d+)분 이상", 1)
    h_night = pick(KLS, "제56조", r"오후 (\d+)시부터", 3)
    h_teen = pick(KLS, "제69조", r"1주에 (\d+)시간을 초과하지")
    NIGHT = ["오후 8시", "오후 9시", "오후 10시", "자정"]
    law_topic(
        "labor-hours", "⏱️", "근로시간과 휴게시간의 비밀",
        "주 몇 시간, 쉬는 시간은 얼마나", [KLS], [
            slider("hr1", "법정 근로시간은 1주 몇 시간일까요?",
                   h_week, "시간", 0, 70, 1,
                   f"{cite(KLS, '제50조', 1)}에서 «1주 간의 근로시간은 휴게시간을 제외하고 ○시간»을 "
                   f"뽑으면 {h_week}시간",
                   "흔히 말하는 «주 52시간»은 법정 근로시간이 아니라 연장근로를 더한 상한입니다."),
            slider("hr2", "연장근로까지 합치면 1주 최대 몇 시간 일할 수 있을까요?",
                   h_week + h_ot, "시간", 0, 80, 1,
                   f"{cite(KLS, '제50조', 1)}의 {h_week}시간에 {cite(KLS, '제53조', 1)}의 연장 한도 "
                   f"{h_ot}시간을 더하면 {h_week + h_ot}시간",
                   "숫자 52는 익숙해도, 40과 12가 합쳐진 값이라는 건 잘 모릅니다.",
                   limit="일반적인 상한입니다. 고용노동부 인가를 받은 특별연장근로(제53조제4항) 같은 "
                         "예외가 있습니다."),
            slider("hr3", "8시간 일하면 휴게시간은 최소 몇 분이어야 할까요?",
                   h_rest * 60, "분", 0, 120, 5,
                   f"{cite(KLS, '제54조', 1)}에서 «8시간인 경우에는 ○시간 이상»을 뽑아 분으로 바꾸면 "
                   f"{h_rest * 60}분 (4시간이면 {h_rest4}분)",
                   "휴게시간은 일을 시작하기 전이나 끝난 뒤가 아니라 «근로시간 도중»에 줘야 합니다."),
            choice("hr4", "가산수당이 붙는 «야간근로»는 몇 시부터일까요?",
                   NIGHT, f"오후 {h_night}시",
                   f"{cite(KLS, '제56조', 3)}에서 «오후 ○시부터 다음 날 오전 6시»를 뽑으면 오후 "
                   f"{h_night}시",
                   "«밤»의 기준은 사람마다 다르지만 법의 기준은 하나입니다."),
            slider("hr5", "15세 이상 18세 미만은 1주 최대 몇 시간 일할 수 있을까요? (연장 제외)",
                   h_teen, "시간", 0, 60, 1,
                   f"{cite(KLS, '제69조')}에서 «1주에 ○시간을 초과하지 못한다»를 뽑으면 {h_teen}시간",
                   "청소년 아르바이트에는 어른과 다른 상한이 있습니다."),
        ], caveat=SMALL)

    # ── 4. 임금 · 수당 ──────────────────────────────────────────────
    w_ot = pick(KLS, "제56조", r"100분의 (\d+) 이상을 가산", 1)
    w_hol = pick(KLS, "제56조", r"8시간을 초과한 휴일근로: 통상임금의 100분의 (\d+)", 2)
    w_idle = pick(KLS, "제46조", r"평균임금의 100분의 (\d+) 이상의 수당", 1)
    w_exp = pick(KLS, "제49조", r"(\d+)년간 행사하지")
    mw27, mw26 = min_wage(27), min_wage(26)
    law_topic(
        "labor-wage", "💰", "임금과 수당, 제대로 알고 받기",
        "더 받는 시간, 쉬어도 받는 돈", [KLS, MW], [
            slider("wg1", "연장근로를 하면 통상임금에 몇 %를 더 받을까요?",
                   w_ot, "%", 0, 200, 5,
                   f"{cite(KLS, '제56조', 1)}에서 «통상임금의 100분의 ○ 이상을 가산»을 뽑으면 "
                   f"{w_ot}%",
                   "«1.5배»라고 들어도 그게 몇 % 더인지 헷갈립니다.",
                   limit="원문은 «○ 이상을 가산»으로 법이 정한 최소 가산율입니다. 회사가 더 주는 것은 "
                         "괜찮습니다."),
            slider("wg2", "휴일에 8시간을 넘겨 일하면, 넘긴 시간에는 통상임금에 몇 %를 더 받을까요?",
                   w_hol, "%", 0, 200, 5,
                   f"{cite(KLS, '제56조', 2)} 2호에서 «8시간을 초과한 휴일근로: 통상임금의 100분의 ○»를 "
                   f"뽑으면 {w_hol}%",
                   "휴일근로는 8시간까지와 그 뒤의 가산율이 다릅니다.",
                   limit=f"법이 정한 최소 가산율이며, 8시간까지의 휴일근로는 "
                         f"{pick(KLS, '제56조', r'8시간 이내의 휴일근로: 통상임금의 100분의 (\d+)', 2)}%"
                         f"입니다."),
            slider("wg3", "회사 사정으로 쉬게 되면 평균임금의 몇 % 이상을 받을까요?",
                   w_idle, "%", 0, 100, 5,
                   f"{cite(KLS, '제46조', 1)}에서 «평균임금의 100분의 ○ 이상의 수당»을 뽑으면 "
                   f"{w_idle}%",
                   "«일을 안 했으니 무급»이라고 생각하기 쉽지만, 회사 탓이면 휴업수당이 있습니다."),
            slider("wg4", "받지 못한 임금은 몇 년 안에 청구해야 할까요?",
                   w_exp, "년", 0, 10, 1,
                   f"{cite(KLS, '제49조')}에서 «임금채권은 ○년간 행사하지 아니하면 시효로 소멸»을 "
                   f"뽑으면 {w_exp}년",
                   "밀린 임금도 시간이 지나면 청구할 권리가 사라집니다."),
            slider("wg5", "2027년 최저임금은 시간당 얼마일까요?",
                   mw27["hour"], "원", 9000, 12000, 10,
                   f"최저임금위원회 «연도별 최저임금 결정현황» 표에서 '27.01.01~'27.12.31 행의 "
                   f"시간급을 뽑으면 {mw27['hour']:,}원 (20{mw27['notice'][:2]}. "
                   f"{int(mw27['notice'][3:5])}. {int(mw27['notice'][6:8])}. 고시, 2026년 "
                   f"{mw26['hour']:,}원보다 {mw27['up']}원 · {mw27['rise']}% 인상)",
                   "올해 금액에 익숙해서 내년 금액은 뉴스를 봐도 잘 기억나지 않습니다.",
                   limit="2027년 1월 1일부터 적용되는 금액입니다. 고시 원문이 아니라 최저임금위원회 "
                         "웹페이지의 결정현황 표에서 가져왔습니다."),
        ], caveat=SMALL + " 2027년 최저임금은 법률이 아니라 고용노동부 고시 값입니다.")

    # ── 5. 직장 내 괴롭힘 ───────────────────────────────────────────
    assert has(KLS, "제116조", "제76조의2를 위반하여 직장 내 괴롭힘", 1)
    assert has(KLS, "제116조", "제76조의3제2항", 2)
    assert has(KLS, "제109조", "제76조의3제6항", 1)
    b_boss = pick(KLS, "제116조", r"(\d+천만원|\d+백만원|\d+만원) 이하의 과태료", 1, won)
    b_noinq = pick(KLS, "제116조", r"(\d+천만원|\d+백만원|\d+만원) 이하의 과태료", 2, won)
    b_jail = pick(KLS, "제109조", r"(\d+)년 이하의 징역", 1)
    b_fine = pick(KLS, "제109조", r"징역 또는 (\d+천만원|\d+백만원|\d+만원) 이하의 벌금", 1, won)
    # 116조①의 괴롭힘 과태료 대상은 «사용자»뿐 — 동료 근로자를 정한 곳이 있는지 본다
    peer_line = next(ln for ln in hang(jo(KLS, "제116조"), 1).splitlines()
                     if "제76조의2" in ln)
    PEER = ["과태료 대상은 아님", f"{b_boss:,}만 원 이하", f"{b_noinq:,}만 원 이하", "징역형"]
    peer_ans = PEER[0] if peer_line.split(". ", 1)[1].startswith("사용자") else PEER[1]
    law_topic(
        "labor-bully", "🚫", "직장 내 괴롭힘, 어디까지가 괴롭힘일까?",
        "누가 처벌받고, 회사는 무엇을 해야 하나", [KLS], [
            slider("bl1", "사장(사용자)이 직접 직장 내 괴롭힘을 하면 과태료는 최대 얼마일까요?",
                   b_boss, "만 원", 0, 5000, 100,
                   f"{cite(KLS, '제116조', 1)} 1호(사용자의 제76조의2 위반)에서 «○ 이하의 과태료»를 "
                   f"뽑으면 {b_boss:,}만 원",
                   "괴롭힘에 «사장»이 직접 나선 경우를 법이 따로 정해 두었습니다."),
            slider("bl2", "괴롭힘 신고를 받고도 회사가 조사하지 않으면 과태료는 최대 얼마일까요?",
                   b_noinq, "만 원", 0, 5000, 100,
                   f"{cite(KLS, '제116조', 2)}(제76조의3제2항 위반 포함)에서 «○ 이하의 과태료»를 "
                   f"뽑으면 {b_noinq:,}만 원",
                   "신고만 하면 끝이 아니라, 회사에는 «지체 없이» 조사할 의무가 있습니다."),
            slider("bl3", "신고한 사람에게 불이익을 주면 징역은 최대 몇 년일까요?",
                   b_jail, "년", 0, 10, 1,
                   f"{cite(KLS, '제109조', 1)}(제76조의3제6항 위반)에서 «○년 이하의 징역»을 뽑으면 "
                   f"{b_jail}년",
                   "괴롭힘 자체보다 신고자에게 보복하는 쪽이 더 무겁게 처벌됩니다."),
            slider("bl4", "같은 경우 벌금은 최대 얼마일까요?",
                   b_fine, "만 원", 0, 10000, 100,
                   f"{cite(KLS, '제109조', 1)}에서 «징역 또는 ○ 이하의 벌금»을 뽑으면 {b_fine:,}만 원",
                   "과태료(행정 제재)와 벌금(형사 처벌)은 다른 것입니다."),
            choice("bl5", "동료 근로자가 괴롭힘을 하면, 근로기준법상 과태료는 얼마일까요?",
                   PEER, peer_ans,
                   f"{cite(KLS, '제116조', 1)}에서 제76조의2(괴롭힘 금지)를 다루는 호를 찾으면 대상이 "
                   f"«사용자»로만 적혀 있어 동료 근로자는 과태료 대상이 아님",
                   "동료의 괴롭힘은 과태료가 아니라 회사의 징계 · 조치 의무로 다룹니다.",
                   limit="조문에 «없다»고 적힌 것이 아니라, 과태료 대상이 사용자로만 정해져 있다는 데서 "
                         "끌어낸 답입니다. 동료에게도 회사 징계나 다른 법의 책임은 따를 수 있습니다."),
        ], caveat=SMALL + " 괴롭힘 조항도 4명 이하 사업장에는 적용되지 않습니다.")

    # ── 6. 성희롱 · 성차별 ─────────────────────────────────────────
    assert has(GEN, "제39조", "제13조제1항을 위반하여 성희롱 예방 교육을 하지", 3)
    assert has(GEN, "제37조", "제14조제6항", 2)
    s_edu = pick(GEN, "제13조", r"교육\(이하 “성희롱 예방 교육”이라 한다\)을 (\S+) 실시", 1, str)
    s_boss = pick(GEN, "제39조", r"(\d+천만원|\d+백만원|\d+만원) 이하의 과태료", 2, won)
    s_noedu = pick(GEN, "제39조", r"(\d+천만원|\d+백만원|\d+만원) 이하의 과태료", 3, won)
    s_jail = pick(GEN, "제37조", r"(\d+)년 이하의 징역", 2)
    s_marry = pick(GEN, "제37조", r"(\d+)년 이하의 징역", 1)
    EDU = ["매년", "2년마다", "입사할 때 한 번", "정해진 주기 없음"]
    law_topic(
        "labor-harass", "⚖️", "직장 내 성희롱과 성차별 바로 알기",
        "예방 교육부터 신고 뒤 보호까지", [GEN], [
            choice("sh1", "직장 내 성희롱 예방 교육은 얼마나 자주 해야 할까요?",
                   EDU, s_edu,
                   f"{cite(GEN, '제13조', 1)}에서 «성희롱 예방 교육을 ○ 실시»를 뽑으면 «{s_edu}»",
                   "한 번 들으면 끝인 교육이 아닙니다."),
            slider("sh2", "사업주가 직접 성희롱을 하면 과태료는 최대 얼마일까요?",
                   s_boss, "만 원", 0, 5000, 100,
                   f"{cite(GEN, '제39조', 2)}에서 «○ 이하의 과태료»를 뽑으면 {s_boss:,}만 원",
                   "사업주 본인이 행위자일 때를 법이 따로 정해 두었습니다."),
            slider("sh3", "예방 교육을 하지 않은 회사의 과태료는 최대 얼마일까요?",
                   s_noedu, "만 원", 0, 5000, 100,
                   f"{cite(GEN, '제39조', 3)}(제13조제1항 위반 포함)에서 «○ 이하의 과태료»를 뽑으면 "
                   f"{s_noedu:,}만 원",
                   "교육을 빠뜨린 것만으로도 제재 대상입니다."),
            slider("sh4", "성희롱을 신고한 사람에게 불이익을 주면 징역은 최대 몇 년일까요?",
                   s_jail, "년", 0, 10, 1,
                   f"{cite(GEN, '제37조', 2)}(제14조제6항 위반)에서 «○년 이하의 징역»을 뽑으면 "
                   f"{s_jail}년",
                   "신고자 보호 위반은 과태료가 아니라 형사 처벌입니다."),
            slider("sh5", "«결혼 · 임신하면 퇴직»하는 근로계약을 맺으면 징역은 최대 몇 년일까요?",
                   s_marry, "년", 0, 10, 1,
                   f"{cite(GEN, '제37조', 1)}(제11조 위반)에서 «○년 이하의 징역»을 뽑으면 {s_marry}년",
                   "옛날 이야기 같지만, 이 법에서 가장 무거운 처벌 중 하나입니다."),
        ])

    # ── 7. 출산 · 육아 ──────────────────────────────────────────────
    f_birth = pick(KLS, "제74조", r"출산 후를 통하여 (\d+)일", 1)
    f_twin = pick(KLS, "제74조", r"둘 이상 자녀를 임신한 경우에는 (\d+)일\)의 출산전후휴가", 1)
    f_dad = pick(GEN, "제18조의2", r"(\d+)일의 휴가를 주어야", 1)
    f_leave = pick(GEN, "제19조", r"육아휴직의 기간은 (\d+)년 이내", 2)
    f_age = pick(GEN, "제19조의2", r"만 (\d+)세 이하", 1)
    law_topic(
        "labor-family", "👶", "출산·육아와 일·가정 양립 제도",
        "출산휴가, 배우자 휴가, 육아휴직", [GEN, KLS], [
            slider("fm1", "출산전후휴가는 며칠일까요? (아이 한 명)",
                   f_birth, "일", 0, 180, 5,
                   f"{cite(KLS, '제74조', 1)}에서 «출산 전과 출산 후를 통하여 ○일»을 뽑으면 {f_birth}일",
                   "«출산휴가 3개월»이라는 말이 실제 일수와 맞는지 확인해 볼 만합니다.",
                   limit=f"아이가 한 명이어도 미숙아를 출산하면 "
                         f"{pick(KLS, '제74조', r'미숙아를 출산한 경우에는 (\d+)일', 1)}일입니다."),
            slider("fm2", "쌍둥이를 임신했다면 출산전후휴가는 며칠일까요?",
                   f_twin, "일", 0, 180, 5,
                   f"{cite(KLS, '제74조', 1)}에서 «둘 이상 자녀를 임신한 경우에는 ○일»을 뽑으면 "
                   f"{f_twin}일",
                   "다태아는 휴가가 더 길다는 사실을 모르는 경우가 많습니다."),
            slider("fm3", "배우자 출산휴가는 며칠일까요?",
                   f_dad, "일", 0, 60, 1,
                   f"{cite(GEN, '제18조의2', 1)}에서 «○일의 휴가를 주어야»를 뽑으면 {f_dad}일 (유급)",
                   "몇 년 사이에 크게 늘어서, 예전 기준으로 기억하는 사람이 많습니다."),
            slider("fm4", "육아휴직은 기본 몇 개월까지 쓸 수 있을까요?",
                   f_leave * 12, "개월", 0, 36, 1,
                   f"{cite(GEN, '제19조', 2)}에서 «육아휴직의 기간은 ○년 이내»를 뽑아 개월로 바꾸면 "
                   f"{f_leave * 12}개월 (부모 모두 3개월 이상 쓰는 등의 경우 6개월 추가)",
                   "엄마 아빠가 각각 쓸 수 있는 기간이라는 점을 놓치기 쉽습니다."),
            slider("fm5", "육아기 근로시간 단축은 자녀가 만 몇 살 이하일 때까지 쓸 수 있을까요?",
                   f_age, "세", 0, 18, 1,
                   f"{cite(GEN, '제19조의2', 1)}에서 «만 ○세 이하 또는 초등학교 6학년 이하»를 뽑으면 "
                   f"만 {f_age}세",
                   "육아휴직(만 8세 이하)과 대상 나이가 다릅니다.",
                   limit=f"원문은 «만 {f_age}세 이하 또는 초등학교 "
                         f"{pick(GEN, '제19조의2', r'초등학교 (\d+)학년 이하', 1)}학년 이하»라서, "
                         f"만 {f_age}세를 넘긴 그 학년 자녀도 대상입니다."),
        ])

    # ── 8. 산업재해 · 안전 ─────────────────────────────────────────
    k_dead = pick(SAFE, "제2조", r"가\. 사망자가 (\d+)명 이상")
    k_hurt = pick(SAFE, "제2조", r"6개월 이상 치료가 필요한 부상자가 (\d+)명 이상")
    k_corp = pick(SAFE, "제7조", r"1\. 제6조제1항의 경우: (\d+)억원", conv=lambda s: int(s))
    k_dmg = pick(SAFE, "제15조", r"손해액의 (\d+)배", 1)
    k_small = pick(SAFE, "제3조", r"상시 근로자가 (\d+)명 미만")
    law_topic(
        "labor-safety", "⛑️", "산업재해와 근로자의 안전보건 권리",
        "중대재해처벌법이 정한 선", [SAFE], [
            slider("sf1", "사망자가 몇 명 이상 나면 «중대산업재해»일까요?",
                   k_dead, "명", 0, 10, 1,
                   f"{cite(SAFE, '제2조')} 2호 가목에서 «사망자가 ○명 이상»을 뽑으면 {k_dead}명",
                   "«중대»라는 말 때문에 여러 명이 숨져야 한다고 생각하기 쉽습니다."),
            slider("sf2", "같은 사고로 6개월 이상 치료가 필요한 부상자가 몇 명 이상이면 중대산업재해일까요?",
                   k_hurt, "명", 0, 10, 1,
                   f"{cite(SAFE, '제2조')} 2호 나목에서 «부상자가 ○명 이상»을 뽑으면 {k_hurt}명",
                   "사망이 없어도 중대산업재해가 될 수 있습니다."),
            slider("sf3", "근로자가 숨진 중대산업재해에서 법인 벌금은 최대 몇 억 원일까요?",
                   k_corp, "억 원", 0, 100, 1,
                   f"{cite(SAFE, '제7조')} 1호(제6조제1항의 경우)에서 «○억원 이하의 벌금»을 뽑으면 "
                   f"{k_corp}억 원",
                   "경영책임자 개인 처벌과 별도로 회사(법인)에도 벌금이 붙습니다."),
            slider("sf4", "중대재해 손해배상은 손해액의 최대 몇 배까지일까요?",
                   k_dmg, "배", 0, 10, 1,
                   f"{cite(SAFE, '제15조', 1)}에서 «손해액의 ○배를 넘지 아니하는»을 뽑으면 {k_dmg}배",
                   "실제 손해보다 더 물어내게 하는 «징벌적 손해배상»입니다."),
            slider("sf5", "상시 근로자가 몇 명 미만인 사업장은 중대재해처벌법이 적용되지 않을까요?",
                   k_small, "명", 0, 50, 1,
                   f"{cite(SAFE, '제3조')}에서 «상시 근로자가 ○명 미만인 사업 또는 사업장»을 뽑으면 "
                   f"{k_small}명",
                   "50명 미만도 이미 적용되고 있다는 사실을 모르는 경우가 많습니다.",
                   limit="50명 미만 사업장에 적용되기 시작한 시점은 법 부칙에 있는데, 부칙은 이 퀴즈의 "
                         "원본에 들어 있지 않습니다."),
        ])

    # ── 9. 수습 · 계약직 ────────────────────────────────────────────
    c_year = pick(FIX, "제4조", r"(\d+)년을 초과하지 아니하는 범위", 1)
    c_part = pick(FIX, "제6조", r"1주간에 (\d+)시간을 초과하여", 1)
    c_rate = pick(FIX, "제6조", r"100분의 (\d+) 이상을 가산", 3)
    c_claim = pick(FIX, "제9조", r"종료일\)부터 (\d+)개월", 1)
    c_trial = pick(MW, "제5조", r"수습을 시작한 날부터 (\d+)개월 이내", 2)
    law_topic(
        "labor-contract", "📝", "수습·시용·계약직 근로자의 권리",
        "기간제 · 단시간 · 수습이 알아야 할 숫자", [FIX, MW], [
            slider("ct1", "계약직(기간제)은 최대 몇 년까지 쓸 수 있을까요?",
                   c_year, "년", 0, 10, 1,
                   f"{cite(FIX, '제4조', 1)}에서 «○년을 초과하지 아니하는 범위»를 뽑으면 {c_year}년 "
                   f"(넘기면 기간의 정함이 없는 근로자로 봄)",
                   "계약을 여러 번 갱신해도 합친 기간으로 셉니다.",
                   limit="고령자, 전문직, 특정 업무 완성 등 제4조제1항 단서의 예외에 해당하면 이 기간을 "
                         "넘겨 계약직으로 쓸 수 있습니다."),
            slider("ct2", "단시간근로자의 초과근로는 1주 최대 몇 시간일까요?",
                   c_part, "시간", 0, 40, 1,
                   f"{cite(FIX, '제6조', 1)}에서 «1주간에 ○시간을 초과하여 근로하게 할 수 없다»를 "
                   f"뽑으면 {c_part}시간",
                   "파트타이머도 무한정 더 일하게 할 수는 없습니다."),
            slider("ct3", "단시간근로자가 정해진 시간보다 더 일하면 통상임금에 몇 %를 더 받을까요?",
                   c_rate, "%", 0, 200, 5,
                   f"{cite(FIX, '제6조', 3)}에서 «100분의 ○ 이상을 가산»을 뽑으면 {c_rate}%",
                   "하루 8시간을 넘지 않아도 «정해진 시간»을 넘으면 가산됩니다.",
                   limit="원문은 «○ 이상을 가산»으로 법이 정한 최소 가산율입니다."),
            slider("ct4", "차별을 받았다면 몇 개월 안에 노동위원회에 시정신청을 해야 할까요?",
                   c_claim, "개월", 0, 24, 1,
                   f"{cite(FIX, '제9조', 1)}에서 «차별적 처우가 있은 날(계속되면 종료일)부터 ○개월»을 "
                   f"뽑으면 {c_claim}개월",
                   "시정신청에도 기한이 있어서 미루면 기회를 잃습니다."),
            slider("ct5", "수습 중 최저임금보다 적게 줄 수 있는 기간은 수습 시작부터 최대 몇 개월일까요?",
                   c_trial, "개월", 0, 12, 1,
                   f"{cite(MW, '제5조', 2)}에서 «수습을 시작한 날부터 ○개월 이내»를 뽑으면 "
                   f"{c_trial}개월 (1년 이상 계약일 때만, 단순노무직은 제외)",
                   "«수습이면 깎아도 된다»가 아니라 조건과 기간이 정해져 있습니다."),
        ])

    # ── 10. 해고 · 징계 ─────────────────────────────────────────────
    d_pay = pick(KLS, "제26조", r"(\d+)일분 이상의 통상임금")
    d_paper = has(KLS, "제27조", "서면으로 통지하여야 효력이 있다", 2)
    d_claim = pick(KLS, "제28조", r"(\d+)개월 이내", 2)
    d_once = pick(KLS, "제95조", r"평균임금의 1일분의 (\d+)분의 1")
    d_total = pick(KLS, "제95조", r"임금 총액의 (\d+)분의 1")
    PAPER = ["효력 없음", "효력 있음", "30일 뒤부터 효력", "본인이 동의하면 효력"]
    law_topic(
        "labor-dismiss", "📮", "해고와 징계, 회사 마음대로 할 수 있을까?",
        "통보 방법, 대응 기한, 감봉의 한도", [KLS], [
            slider("ds1", "예고 없이 바로 해고되면 통상임금 며칠분을 받을 수 있을까요?",
                   d_pay, "일분", 0, 90, 1,
                   f"{cite(KLS, '제26조')}에서 «예고를 하지 아니하였을 때에는 ○일분 이상의 통상임금»을 "
                   f"뽑으면 {d_pay}일분 (3개월 미만 근무 등은 예외)",
                   "해고 예고를 못 받았다면 «해고예고수당»을 청구할 수 있습니다."),
            choice("ds2", "해고를 말이나 문자로만 통보받았다면, 그 해고의 효력은?",
                   PAPER, PAPER[0] if d_paper else PAPER[1],
                   f"{cite(KLS, '제27조', 2)}에서 «서면으로 통지하여야 효력이 있다»를 확인하면, 서면이 "
                   f"없는 해고는 효력 없음",
                   "«내일부터 나오지 마»라는 말만으로는 해고가 성립하지 않습니다."),
            slider("ds3", "부당해고라고 생각되면 몇 개월 안에 노동위원회에 구제를 신청해야 할까요?",
                   d_claim, "개월", 0, 24, 1,
                   f"{cite(KLS, '제28조', 2)}에서 «부당해고등이 있었던 날부터 ○개월 이내»를 뽑으면 "
                   f"{d_claim}개월",
                   "억울해도 기한을 넘기면 노동위원회 구제를 받을 수 없습니다."),
            slider("ds4", "감봉 징계 1회로 깎을 수 있는 금액은 하루 평균임금의 최대 몇 %일까요?",
                   100 / d_once, "%", 0, 100, 5,
                   f"{cite(KLS, '제95조')}에서 «1회의 금액이 평균임금의 1일분의 ○분의 1»을 뽑아 %로 "
                   f"바꾸면 {100 / d_once:.0f}%",
                   "«월급의 절반 감봉» 같은 징계는 법의 한도를 넘습니다."),
            slider("ds5", "감봉 총액은 한 달 치 임금 총액의 최대 몇 %일까요?",
                   100 / d_total, "%", 0, 100, 5,
                   f"{cite(KLS, '제95조')}에서 «총액이 1임금지급기의 임금 총액의 ○분의 1»을 뽑아 %로 "
                   f"바꾸면 {100 / d_total:.0f}%",
                   "감봉이 여러 번 겹쳐도 한 달에 깎을 수 있는 총액에는 상한이 있습니다."),
        ], caveat=SMALL + " 해고 제한(제23조) · 구제신청(제28조)은 4명 이하 사업장에 적용되지 "
                          "않습니다.")

    # ── 11. 고용보험 · 실업급여 ─────────────────────────────────────
    e_days = pick(EI, "제40조", r"합산하여 (\d+)일 이상일 것", 1)
    e_base = pick(EI, "제40조", r"기준기간은 이직일 이전 (\d+)개월", 2)
    e_within = pick(EI, "제48조", r"(\d+)개월 내에", 1)
    e_leave = pick(EI, "제70조", r"육아휴직을 (\d+)일", 1)
    e_apply = pick(EI, "제70조", r"끝난 날 이후 (\d+)개월 이내", 2)
    law_topic(
        "ins-employ", "🧾", "실업급여와 고용보험",
        "실업급여 · 육아휴직 급여를 받으려면", [EI], [
            slider("ei1", "실업급여를 받으려면 고용보험 가입(피보험 단위기간)이 최소 며칠이어야 할까요?",
                   e_days, "일", 0, 365, 5,
                   f"{cite(EI, '제40조', 1)} 1호에서 «피보험 단위기간이 합산하여 ○일 이상»을 뽑으면 "
                   f"{e_days}일",
                   "«6개월 다니면 된다»는 말과 비슷하지만, 세는 날은 달력 날짜가 아니라 보수를 받은 "
                   "날입니다.",
                   limit="피보험 단위기간은 달력의 날짜가 아니라 보수를 받은 날로 세므로(제41조), 실제로 "
                         "다닌 기간은 이보다 길어야 합니다."),
            slider("ei2", "그 기간은 그만두기 전 몇 개월 안에서 셀까요?",
                   e_base, "개월", 0, 36, 1,
                   f"{cite(EI, '제40조', 2)}에서 «기준기간은 이직일 이전 ○개월»을 뽑으면 {e_base}개월",
                   "오래전에 일한 기간은 합쳐지지 않을 수 있습니다.",
                   limit=f"질병 등으로 보수를 못 받은 기간이 있으면 늘어나고, 주 15시간 미만 · 주 2일 "
                         f"이하로 일했다면 "
                         f"{pick(EI, '제40조', r'모두 해당하는 경우: 이직일 이전 (\d+)개월', 2)}"
                         f"개월로 셉니다."),
            slider("ei3", "실업급여는 그만둔 다음 날부터 몇 개월 안에 다 받아야 할까요?",
                   e_within, "개월", 0, 36, 1,
                   f"{cite(EI, '제48조', 1)}에서 «이직일의 다음 날부터 … ○개월 내에»를 뽑으면 "
                   f"{e_within}개월",
                   "신청을 미루면 받을 수 있는 날이 남아 있어도 기간이 끝나 버립니다."),
            slider("ei4", "육아휴직 급여를 받으려면 육아휴직을 최소 며칠 써야 할까요?",
                   e_leave, "일", 0, 90, 1,
                   f"{cite(EI, '제70조', 1)}에서 «육아휴직을 ○일 … 이상 부여받은»을 뽑으면 {e_leave}일",
                   "아주 짧은 육아휴직은 급여 대상이 아닐 수 있습니다.",
                   limit=f"원문은 «{e_leave}일 또는 단기 육아휴직 ○일»로 묶여 있어, 1~2주짜리 단기 육아휴직은 "
                         f"{pick(EI, '제70조', r'제19조제6항에 따른 육아휴직을 (\d+)일', 1)}일만 써도 "
                         f"급여 대상입니다."),
            slider("ei5", "육아휴직 급여는 휴직이 끝난 뒤 몇 개월 안에 신청해야 할까요?",
                   e_apply, "개월", 0, 36, 1,
                   f"{cite(EI, '제70조', 2)}에서 «육아휴직이 끝난 날 이후 ○개월 이내»를 뽑으면 "
                   f"{e_apply}개월",
                   "복직하고 바쁘다 보면 신청 기한을 넘기기 쉽습니다."),
        ], caveat="실업급여의 액수 · 받는 날수는 법률 별표와 시행령에 있어 이 주제에서는 다루지 "
                  "않습니다.")

    # ── 12. 국민연금 ────────────────────────────────────────────────
    p_from = pick(NP, "제6조", r"(\d+)세 이상 \d+세 미만")
    p_min = pick(NP, "제61조", r"가입기간이 (\d+)년 이상", 1)
    p_late = pick(NP, "제62조", r"1개월마다 그 금액의 1천분의 (\d+)", 4)
    p_early = pick(NP, "제63조", r"55세부터 지급받는 경우에는 1천분의 (\d+)", 2)
    p_10y = pick(NP, "제63조", r"기본연금액의 1천분의 (\d+)에 해당하는 금액에 가입기간", 1)
    law_topic(
        "ins-pension", "👵", "국민연금, 언제 얼마나 받나",
        "가입 나이, 최소 가입기간, 앞당기기와 미루기", [NP], [
            slider("pn1", "국민연금 가입 대상은 몇 세 이상부터일까요?",
                   p_from, "세", 0, 30, 1,
                   f"{cite(NP, '제6조')}에서 «○세 이상 60세 미만»을 뽑으면 {p_from}세",
                   "취업하기 전 대학생 나이부터 가입 대상입니다."),
            slider("pn2", "노령연금을 받으려면 최소 몇 년 가입해야 할까요?",
                   p_min, "년", 0, 30, 1,
                   f"{cite(NP, '제61조', 1)}에서 «가입기간이 ○년 이상»을 뽑으면 {p_min}년",
                   "기간을 채우지 못하면 연금이 아니라 낸 돈을 돌려받는 데 그칩니다."),
            slider("pn3", "가입기간 10년만 채우면 기본연금액의 몇 %를 받을까요?",
                   p_10y / 10, "%", 0, 100, 5,
                   f"{cite(NP, '제63조', 1)} 2호에서 «기본연금액의 1천분의 ○»을 뽑아 %로 바꾸면 "
                   f"{p_10y / 10:.0f}% (20년 이상이면 기본연금액 전부)",
                   "최소 기간만 채우면 연금이 많이 깎입니다."),
            slider("pn4", "55세부터 앞당겨 받으면(조기노령연금) 원래 연금의 몇 %를 받을까요?",
                   p_early / 10, "%", 0, 100, 5,
                   f"{cite(NP, '제63조', 2)} 1호에서 «55세부터 지급받는 경우에는 1천분의 ○»을 뽑아 %로 "
                   f"바꾸면 {p_early / 10:.0f}%",
                   "앞당긴 해마다 깎이는 비율이 커서, 가장 이르게 받으면 차이가 큽니다.",
                   limit=f"법 본문은 «55세부터»지만 부칙에 따라 출생연도별로 조기 수령 나이가 늦춰져, "
                         f"지금 세대는 55세에 받을 수 없습니다. «"
                         f"{pick(NP, '제61조', r'(\d+)세\(특수직종근로자는', 1) - 55}년 앞당기면 "
                         f"{p_early / 10:.0f}%»로 이해하는 것이 정확합니다."),
            slider("pn5", "연금 받기를 미루면 1개월마다 몇 %씩 더 받을까요?",
                   p_late / 10, "%", 0, 2, 0.1,
                   f"{cite(NP, '제62조', 4)} 2호에서 «1개월마다 그 금액의 1천분의 ○»을 뽑아 %로 바꾸면 "
                   f"{p_late / 10}% (1년 미루면 {p_late * 12 / 10:.1f}%)",
                   "한 달 치는 작아 보여도 1년이면 꽤 큰 비율이 됩니다."),
        ], caveat="연금을 받기 시작하는 나이와 보험료율은 출생연도 · 연도별 경과 규정(부칙)에 "
                  "따라 달라서 이 주제에서는 다루지 않습니다.")

    # ── 13. 건강보험 ────────────────────────────────────────────────
    n_cap = pick(NHI, "제73조", r"1천분의 (\d+)의 범위", 1)
    n_half = pick(NHI, "제76조", r"100분의 (\d+)씩 부담", 1)
    n_abroad = pick(NHI, "제73조", r"100분의 (\d+)으로 한다", 2)
    n_baby = pick(NHI, "제52조", r"영유아건강검진: (\d+)세 미만", 2)
    n_next = has(NHI, "제69조", "자격을 취득한 날이 속하는 달의 다음 달부터", 2)
    WHEN = ["입사한 달부터", "다음 달부터", "3개월 뒤부터", "1년 뒤부터"]
    law_topic(
        "ins-health", "🏥", "건강보험료, 누가 얼마나 내나",
        "보험료율 상한, 회사와 나누는 비율", [NHI], [
            slider("nh1", "직장인 건강보험료율은 법으로 최대 몇 %까지 정할 수 있을까요?",
                   n_cap / 10, "%", 0, 20, 0.5,
                   f"{cite(NHI, '제73조', 1)}에서 «1천분의 ○의 범위»를 뽑아 %로 바꾸면 {n_cap / 10}%",
                   "해마다 오르는 보험료율에도 법이 정한 천장이 있습니다.",
                   limit="법이 정한 상한입니다. 실제 보험료율은 시행령으로 정해지며 이보다 낮습니다."),
            slider("nh2", "직장인 건강보험료 중 근로자 본인이 내는 비율은?",
                   n_half, "%", 0, 100, 5,
                   f"{cite(NHI, '제76조', 1)}에서 «각각 보험료액의 100분의 ○씩 부담»을 뽑으면 {n_half}%",
                   "월급명세서에 찍힌 금액은 전체 보험료가 아니라 내 몫만입니다."),
            slider("nh3", "해외에서 일하는 직장가입자의 보험료율은 원래의 몇 %일까요?",
                   n_abroad, "%", 0, 100, 5,
                   f"{cite(NHI, '제73조', 2)}에서 «보험료율의 100분의 ○으로 한다»를 뽑으면 {n_abroad}%",
                   "해외 근무 중에도 보험료가 0이 되지는 않습니다."),
            slider("nh4", "영유아건강검진은 몇 세 미만까지 받을까요?",
                   n_baby, "세", 0, 18, 1,
                   f"{cite(NHI, '제52조', 2)} 3호에서 «영유아건강검진: ○세 미만»을 뽑으면 {n_baby}세",
                   "초등학교 입학 전까지가 영유아검진 대상입니다."),
            choice("nh5", "15일에 입사했다면 건강보험료는 언제부터 낼까요?",
                   WHEN, WHEN[1] if n_next else WHEN[0],
                   f"{cite(NHI, '제69조', 2)}에서 «자격을 취득한 날이 속하는 달의 다음 달부터 … "
                   f"징수»를 확인하면 다음 달부터 (1일 입사는 그달부터)",
                   "입사한 달 월급에서 바로 빠질 것 같지만, 원칙은 다음 달부터입니다."),
        ])


def write_labor():
    """노동법 · 보험 주제만 쓰고, topics.json 목록을 이 주제들로 바꾼다.

    예전 11주제의 topics/*.json 은 지우지도 다시 계산하지도 않는다. 목록에서만 내린다.
    """
    build_labor()
    OUT.mkdir(parents=True, exist_ok=True)
    for t in TOPICS:
        assert len(t["questions"]) == 5, f"{t['id']}: 문항이 5개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))

    idx = json.load(io.open(APP / "topics.json", encoding="utf-8"))
    idx["topics"] = [{k: t[k] for k in ("id", "emoji", "title", "blurb", "source")}
                     for t in TOPICS]
    io.open(APP / "topics.json", "w", encoding="utf-8").write(
        json.dumps(idx, ensure_ascii=False, indent=2))

    md = [f"# 문항 정답지 — 노동법 · 보험 {len(TOPICS)}주제 "
          f"{sum(len(t['questions']) for t in TOPICS)}문항", "",
          "> 모든 값은 `data/raw/` 의 법령 원문에서 `tools/build_topics.py` 가 뽑습니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "", f"- 출처: {t['source']}", ""]
        for q in t["questions"]:
            a = f"{q['answer']:g}{q['unit']}" if q["type"] == "slider" else q["answer"]
            md += [f"**{q['text']}**", "", f"- 정답 **{a}**", f"- 근거 {q['basis']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}")
        for q in t["questions"]:
            a = f"{q['answer']:g}{q['unit']}" if q["type"] == "slider" else q["answer"]
            print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {a}")


if __name__ == "__main__" and "--legacy" not in sys.argv:
    write_labor()
    raise SystemExit


# ════════════════════════════════════════════════════════════════
# 기상 공통
# ════════════════════════════════════════════════════════════════
w = load_json("seoul_weather.json")["daily"]
W = [{"d": dt.date.fromisoformat(t), "hi": hi, "lo": lo, "rain": r}
     for t, hi, lo, r in zip(w["time"], w["temperature_2m_max"],
                             w["temperature_2m_min"], w["precipitation_sum"])]
W24 = [x for x in W if x["d"].year == 2024]


def years(a, b):
    return [x for x in W if a <= x["d"].year <= b]


# ── 1. 서울 기온 ─────────────────────────────────────────────────
# ERA5 는 1950~70년대 구간의 품질이 낮고(초기 확장), 격자 평균이라 도심
# 관측값보다 낮게 나온다. 그래서 '역대 최고기온'이나 '폭염일 추세'처럼
# 그 구간에 기대는 문항은 쓰지 않는다. 열대야·연평균처럼 신호가 뚜렷한 것만 쓴다.
tropical_24 = sum(1 for x in W24 if x["lo"] >= 25)
trop_50s = sum(1 for x in years(1950, 1959) if x["lo"] >= 25) / 10
trop_10s = sum(1 for x in years(2015, 2024) if x["lo"] >= 25) / 10
t_ratio = trop_10s / trop_50s if trop_50s else 0
mean_50s = mean((x["hi"] + x["lo"]) / 2 for x in years(1950, 1959))
mean_10s = mean((x["hi"] + x["lo"]) / 2 for x in years(2015, 2024))
warming = mean_10s - mean_50s
below0_24 = sum(1 for x in W24 if x["lo"] < 0)
hot_days = Counter((x["d"].month, x["d"].day)
                   for x in years(1995, 2024) if x["hi"] >= 33)
peak_day = hot_days.most_common(1)[0]
# 한계 문장의 숫자도 손으로 적지 않는다 — 원본에서 가장 더웠던 날을 찾는다
hottest = max(W, key=lambda x: x["hi"])

topic(
    "seoul-heat", "🌡️", "서울은 얼마나 더워졌나",
    "1950년부터 2024년까지, 서울의 매일 기온",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("h1", "2024년 서울에서 열대야(밤 최저기온 25도 이상)는 며칠이었을까요?",
               tropical_24, "일", 0, 60, 1,
               f"2024년 일최저기온 25도 이상인 날 {tropical_24}일",
               "유난히 더웠던 밤 몇 번이 기억을 지배합니다. 실제 일수는 세어 봐야 "
               "압니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (2.8배 → «약 3배»)
        choice("h2", "1950년대와 2015~2024년, 열대야는 몇 배 차이일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if t_ratio < 1.5 else 1 if t_ratio < 2.5
                   else 2 if t_ratio < 4 else 3],
               f"연평균 열대야 1950년대 {trop_50s:.1f}일 → 2015~2024년 "
               f"{trop_10s:.1f}일 ({t_ratio:.1f}배)",
               "'옛날에도 더웠다'는 느낌과 기록은 다릅니다. 기억은 유난히 더웠던 "
               "몇 밤으로 남지만, 기록은 해마다 빠짐없이 셉니다."),
        slider("h3", "1950년대와 비교해 서울의 연평균 기온은 몇 도 올랐을까요?",
               warming, "도", 0, 4, 0.1,
               f"1950년대 {mean_50s:.2f}도 → 2015~2024년 {mean_10s:.2f}도 "
               f"(+{warming:.2f}도)",
               "1~2도는 작아 보이지만, 그 변화가 열대야 일수를 몇 배로 바꿉니다. "
               "평균의 변화와 극단의 변화는 크기가 다릅니다."),
        choice("h4", "최근 30년간 33도 이상인 날이 가장 잦았던 날짜는?",
               ["7월 초", "7월 말", "8월 초", "8월 말"],
               "7월 말" if peak_day[0][0] == 7 and peak_day[0][1] >= 20
               else "8월 초" if peak_day[0][0] == 8 and peak_day[0][1] <= 10
               else "7월 초" if peak_day[0][0] == 7 else "8월 말",
               f"1995~2024년 중 가장 잦았던 날짜는 {peak_day[0][0]}월 "
               f"{peak_day[0][1]}일 ({peak_day[1]}회)",
               "장마가 끝나는 시점과 가장 더운 시점은 다릅니다."),
        slider("h5", "2024년 서울에서 밤 기온이 영하로 내려간 날은 며칠이었을까요?",
               below0_24, "일", 30, 150, 5,
               f"2024년 일최저기온 0도 미만인 날 {below0_24}일",
               "겨울이 짧아졌다고 느끼지만, 영하로 내려가는 날은 여전히 석 달 "
               "치가 넘습니다."),
    ],
    caveat="ERA5는 넓은 격자의 재분석 값이라 도심 관측소와 다르게 나옵니다. "
           f"예컨대 여기서는 역대 최고기온이 {hottest['hi']:.1f}도"
           f"({hottest['d']:%Y년})지만 기상청 서울 관측 기록은 2018년 39.6도입니다. "
           "같은 '서울 기온'도 출처에 따라 다릅니다.")

# ── 2. 비 ────────────────────────────────────────────────────────
rain_days = [sum(1 for x in W if x["d"].year == y and x["rain"] >= 1.0)
             for y in range(1995, 2025)]
rain_avg = mean(rain_days)
by_month = {m: mean([sum(x["rain"] for x in W
                         if x["d"].year == y and x["d"].month == m)
                     for y in range(1995, 2025)]) for m in range(1, 13)}
wettest_m = max(by_month, key=by_month.get)
max_day = max(W, key=lambda x: x["rain"])
ann = {y: sum(x["rain"] for x in W if x["d"].year == y) for y in range(1995, 2025)}
norm = mean(ann.values())
r2024 = ann[2024]


def days_to_half(y):
    v = sorted((x["rain"] for x in W if x["d"].year == y), reverse=True)
    half, s = sum(v) / 2, 0
    for i, r in enumerate(v, 1):
        s += r
        if s >= half:
            return i
    return len(v)


half_days = round(mean(days_to_half(y) for y in range(1995, 2025)))

topic(
    "seoul-rain", "☔", "비는 언제, 얼마나",
    "서울의 하루치 강수량 30년",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("r1", "서울에서 1년 중 비가 온 날(1mm 이상)은 며칠쯤일까요?",
               rain_avg, "일", 40, 160, 5,
               f"1995~2024년 평균 {rain_avg:.1f}일 "
               f"(최소 {min(rain_days)}일 · 최대 {max(rain_days)}일)",
               "비 오는 날은 기억에 오래 남아서 실제보다 많게 느껴집니다."),
        choice("r2", "1년 강수량이 가장 많은 달은?",
               ["6월", "7월", "8월", "9월"], f"{wettest_m}월",
               " · ".join(f"{m}월 {by_month[m]:.0f}mm" for m in (6, 7, 8, 9)),
               "장마가 낀 달과 비가 가장 많이 오는 달이 같지 않을 수 있습니다."),
        slider("r3", "하루에 내린 비의 최대 기록은?",
               max_day["rain"], "mm", 100, 500, 10,
               f"{max_day['d']:%Y년 %m월 %d일} {max_day['rain']:.1f}mm",
               f"가장 많이 온 날 하루에, 비가 가장 많은 {wettest_m}월 한 달 평균"
               f"({by_month[wettest_m]:.0f}mm)의 {max_day['rain'] / by_month[wettest_m] * 100:.0f}%가 "
               "쏟아졌습니다. 비는 고르게 오지 않습니다."),
        slider("r4", "1년 강수량의 절반은 '비 온 날' 며칠 만에 채워질까요?",
               half_days, "일", 3, 40, 1,
               f"많이 온 날부터 더해서 연 강수량의 절반에 도달하는 데 "
               f"평균 {half_days}일 (1995~2024년)",
               "비는 고르게 오지 않습니다. 열흘 남짓이 1년의 절반을 만듭니다."),
        slider("r5", "2024년 서울 강수량은 30년 평균의 몇 %였을까요?",
               r2024 / norm * 100, "%", 50, 180, 5,
               f"2024년 {r2024:.0f}mm · 1995~2024년 평균 {norm:.0f}mm",
               "'올해 비가 많았다'는 체감과 실제 총량은 자주 어긋납니다."),
    ],
    caveat="ERA5 재분석 값입니다. 기상청 관측 강수량과 조금씩 다릅니다.")

# ── 3. 미세먼지 ──────────────────────────────────────────────────
a = load_json("seoul_air.json")["hourly"]
A = [{"t": dt.datetime.fromisoformat(t), "pm25": p25, "pm10": p10}
     for t, p25, p10 in zip(a["time"], a["pm2_5"], a["pm10"])]
A24 = [x for x in A if x["t"].year == 2024]
pm_month = {m: mean([x["pm25"] for x in A if x["t"].month == m])
            for m in range(1, 13)}
worst_m = max(pm_month, key=pm_month.get)
pm_hour = {h: mean([x["pm25"] for x in A if x["t"].hour == h])
           for h in range(24)}
worst_h = max(pm_hour, key=pm_hour.get)
pm24_avg = mean(x["pm25"] for x in A24)


def daily_avg(year):
    d = {}
    for x in A:
        if x["t"].year == year:
            d.setdefault(x["t"].date(), []).append(x["pm25"])
    return {k: mean(v) for k, v in d.items()}


d24 = daily_avg(2024)
d23 = daily_avg(2023)
bad_ratio = sum(1 for v in d24.values() if v > 35) / len(d24) * 100
worse_year = "2023년" if mean(d23.values()) > mean(d24.values()) else "2024년"

topic(
    "seoul-air", "😷", "미세먼지, 언제 나쁜가",
    "서울의 시간별 초미세먼지 2년치",
    "Open-Meteo Air Quality (CAMS)", "https://open-meteo.com/",
    [
        choice("a1", "초미세먼지(PM2.5)가 가장 나쁜 달은?",
               ["1월", "3월", "5월", "11월"],
               f"{worst_m}월" if f"{worst_m}월" in ["1월", "3월", "5월", "11월"]
               else "3월",
               " · ".join(f"{m}월 {pm_month[m]:.1f}" for m in (1, 3, 5, 11))
               + f" (최악은 {worst_m}월 {pm_month[worst_m]:.1f})",
               "황사 뉴스가 많은 달과 실제 수치가 높은 달은 다를 수 있습니다."),
        slider("a2", "2024년 서울의 초미세먼지 연평균 농도는?",
               pm24_avg, "㎍/㎥", 5, 60, 1,
               f"2024년 시간값 {len(A24):,}개의 평균 {pm24_avg:.1f}㎍/㎥ "
               f"(WHO 권고 연평균 5, 국내 기준 15)",
               "'나쁨'인 날이 인상에 남아서 연평균을 높게 잡게 됩니다."),
        choice("a3", "하루 중 초미세먼지가 가장 높은 시간대는?",
               ["새벽 4시", "오전 10시", "오후 3시", "밤 9시"],
               {4: "새벽 4시", 10: "오전 10시", 15: "오후 3시",
                21: "밤 9시"}.get(worst_h, "오전 10시"),
               " · ".join(f"{h}시 {pm_hour[h]:.1f}" for h in (4, 10, 15, 21))
               + f" (최고는 {worst_h}시)",
               "출퇴근 시간이 가장 나쁠 것 같지만 대기가 정체되는 시간은 따로 "
               "있습니다."),
        slider("a4", "2024년 하루 평균이 '나쁨'(35㎍/㎥ 초과)이었던 날의 비율은?",
               bad_ratio, "%", 0, 60, 1,
               f"2024년 {len(d24)}일 중 "
               f"{sum(1 for v in d24.values() if v > 35)}일",
               "마스크를 챙긴 날은 강하게 기억되지만, 1년 전체로 보면 비율이 "
               "다릅니다."),
        choice("a5", "2023년과 2024년 중 초미세먼지가 더 나빴던 해는?",
               ["2023년", "2024년"], worse_year,
               f"연평균 2023년 {mean(d23.values()):.1f} · "
               f"2024년 {mean(d24.values()):.1f}㎍/㎥",
               "체감은 최근 쪽으로 쏠립니다. 두 해 차이는 생각보다 작습니다."),
    ],
    caveat="CAMS 대기질 모델의 추정값입니다. 에어코리아 측정소 실측값과 "
           "다를 수 있습니다.")

# ── 4. 노동시간 ──────────────────────────────────────────────────
wh = [r for r in load_csv("working_hours.csv") if r["working_hours_omm"]]
latest_year = max(int(r["year"]) for r in wh if r["code"] == "KOR")
cur = owid_countries(wh, latest_year, "working_hours_omm")
kor = cur["South Korea"]
rank = sorted(cur.items(), key=lambda kv: -kv[1])
kor_rank = [k for k, _ in rank].index("South Korea") + 1
longer = kor_rank - 1
past = {int(r["year"]): float(r["working_hours_omm"])
        for r in wh if r["code"] == "KOR"}
y30 = latest_year - 30
drop = past[y30] - kor
trio = {c: cur[c] for c in ("South Korea", "Japan", "Germany") if c in cur}
shortest = min(trio, key=trio.get)
name_ko = {"South Korea": "한국", "Japan": "일본", "Germany": "독일"}

topic(
    "working-hours", "⏰", "우리는 얼마나 일하나",
    "나라별 1인당 연간 노동시간",
    "Our World in Data", "https://ourworldindata.org/grapher/annual-working-hours-per-worker",
    [
        slider("w1", f"{latest_year}년 한국의 1인당 연간 노동시간은?",
               kor, "시간", 1200, 2600, 50,
               f"{latest_year}년 한국 {kor:,.0f}시간 "
               f"(주 5일 기준 하루 약 {kor / 250:.1f}시간)",
               "연 단위로 물으면 감이 잘 안 옵니다. 하루로 나눠 보면 체감과 "
               "맞는지 확인할 수 있습니다."),
        slider("w2", f"한국보다 더 오래 일하는 나라는 {len(cur)}개국 중 몇 개일까요?",
               longer, "개국", 0, 60, 1,
               f"{latest_year}년 기준 {len(cur)}개국 중 한국은 {kor_rank}위",
               "'한국이 제일 많이 일한다'는 인상이 강하지만, 비교 대상에 따라 "
               "순위가 달라집니다."),
        slider("w3", f"한국의 노동시간은 30년 전({y30}년)보다 몇 시간 줄었을까요?",
               drop, "시간", 0, 900, 50,
               f"{y30}년 {past[y30]:,.0f}시간 → {latest_year}년 {kor:,.0f}시간",
               "줄어든 폭은 대개 과소평가됩니다. 하루로 치면 크게 달라진 값입니다."),
        choice("w4", "한국·일본·독일 중 가장 적게 일하는 나라는?",
               ["한국", "일본", "독일"], name_ko[shortest],
               " · ".join(f"{name_ko[c]} {trio[c]:,.0f}시간" for c in trio),
               "나라마다 통계 기준이 다릅니다. 순위보다 격차의 크기를 봅니다."),
        slider("w5", "한국과 독일의 연간 노동시간 차이는?",
               abs(cur["South Korea"] - cur["Germany"]), "시간", 0, 900, 50,
               f"한국 {cur['South Korea']:,.0f} · 독일 "
               f"{cur['Germany']:,.0f}시간",
               "두 나라 차이를 주 단위로 나눠 보면 체감이 확 달라집니다."),
    ],
    caveat="이 자료에는 개발도상국이 많이 포함돼 있어, OECD 안에서의 순위와 "
           "전체 순위가 다릅니다. '어느 집단과 비교하느냐'가 순위를 만듭니다.")

# ── 5. 인구와 출산 ───────────────────────────────────────────────
fert = [r for r in load_json("wb_fertility.json")[1] if r["value"] is not None]
f_latest = max(int(r["date"]) for r in fert if r["countryiso3code"] == "KOR")
f_cur = wb_countries(fert, f_latest)
kor_f = f_cur["Korea, Rep."]
f_rank = sorted(f_cur.items(), key=lambda kv: kv[1])
kor_f_rank = [k for k, _ in f_rank].index("Korea, Rep.") + 1
kor_1970 = next(r["value"] for r in fert
                if r["countryiso3code"] == "KOR" and r["date"] == "1970")

pop = load_json("wb_pop_kor.json")[1]
tot = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.POP.TOTL" and r["value"]}
old = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.POP.65UP.TO.ZS" and r["value"]}
urb = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.URB.TOTL.IN.ZS" and r["value"]}
peak_year = max(tot, key=tot.get)
old_latest = max(old)
urb_latest = max(urb)

topic(
    "population", "👶", "인구와 출산",
    "전 세계 출산율과 한국의 인구 구조",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("p1", f"{f_latest}년 한국의 합계출산율(여성 1명당 출생아 수)은?",
               kor_f, "명", 0.5, 3.0, 0.05,
               f"{f_latest}년 한국 {kor_f:.2f}명",
               "숫자는 자주 들었어도 '여성 1명당'이라는 단위는 잘 안 와닿습니다."),
        slider("p2", f"출산율이 낮은 순으로 세면 한국은 {len(f_cur)}개 나라·지역 중 몇 위일까요?",
               kor_f_rank, "위", 1, 30, 1,
               f"{f_latest}년 기준 {len(f_cur)}곳 중 {kor_f_rank}위 "
               f"(1위 {f_rank[0][0]} {f_rank[0][1]:.2f})",
               "'꼴찌'라고 알고 있지만, 비교 목록에 어떤 나라·지역이 들어가느냐에 "
               "따라 순위가 달라집니다."),
        slider("p3", "1970년 한국의 출산율은 몇 명이었을까요?",
               kor_1970, "명", 1.0, 7.0, 0.1,
               f"1970년 {kor_1970:.2f}명 → {f_latest}년 {kor_f:.2f}명",
               "한 세대 만에 일어난 변화의 크기는 대개 과소평가됩니다."),
        slider("p4", f"{old_latest}년 한국에서 65세 이상 인구의 비율은?",
               old[old_latest], "%", 5, 35, 1,
               f"{old_latest}년 {old[old_latest]:.1f}% "
               f"(World Bank 최신 공표치. 최근 연도는 추계값입니다)",
               "고령화는 '다가올 일'로 느껴지지만 이미 지나온 숫자입니다."),
        slider("p5", f"{urb_latest}년 한국에서 도시에 사는 사람의 비율은?",
               urb[urb_latest], "%", 50, 100, 1,
               f"{urb_latest}년 {urb[urb_latest]:.1f}% "
               f"(World Bank 최신 공표치. 최근 연도는 추계값입니다)",
               "'절반쯤'이라고 답하기 쉽지만 한국은 세계에서도 손꼽히는 도시 국가입니다."),
    ])

# ── 6. 인터넷 ────────────────────────────────────────────────────
net = [r for r in load_json("wb_internet.json")[1] if r["value"] is not None]
n_latest = max(int(r["date"]) for r in net if r["countryiso3code"] == "KOR")
n_cur = wb_countries(net, n_latest)
kor_n = n_cur["Korea, Rep."]
n_rank = sorted(n_cur.items(), key=lambda kv: -kv[1])
kor_n_rank = [k for k, _ in n_rank].index("Korea, Rep.") + 1
kor_2000 = next(r["value"] for r in net
                if r["countryiso3code"] == "KOR" and r["date"] == "2000")
world = next((r["value"] for r in net
              if r["countryiso3code"] == "WLD" and int(r["date"]) == n_latest), None)
if world is None:
    world = mean(n_cur.values())
offline = 100 - world

topic(
    "internet", "🌐", "인터넷과 연결",
    "나라별 인터넷 사용 인구 비율",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("i1", f"{n_latest}년 한국에서 인터넷을 쓰는 사람의 비율은?",
               kor_n, "%", 60, 100, 1,
               f"{n_latest}년 한국 {kor_n:.1f}%",
               "'거의 다'라고 생각하지만 100%는 아닙니다. 남은 몇 %가 누구인지가 "
               "정책의 대상입니다."),
        slider("i2", f"한국보다 인터넷 사용률이 높은 나라는 {len(n_cur)}곳 중 몇 곳일까요?",
               kor_n_rank - 1, "곳", 0, 60, 1,
               f"{n_latest}년 {len(n_cur)}곳 중 한국 {kor_n_rank}위",
               "'IT 강국'이라는 말과 실제 보급률 순위는 다른 이야기입니다."),
        slider("i3", "2000년 한국의 인터넷 사용률은?",
               kor_2000, "%", 0, 100, 5,
               f"2000년 {kor_2000:.1f}% → {n_latest}년 {kor_n:.1f}%",
               "20여 년 전을 떠올릴 때는 지금의 기준으로 과대평가하기 쉽습니다."),
        slider("i4", f"{n_latest}년 전 세계 평균 인터넷 사용률은?",
               world, "%", 20, 100, 5,
               f"{n_latest}년 세계 {world:.1f}%",
               "내 주변이 전부 연결돼 있으면 세계도 그럴 거라고 생각하게 됩니다."),
        slider("i5", "전 세계에서 인터넷을 쓰지 않는 사람은 몇 %일까요?",
               offline, "%", 0, 70, 5,
               f"100 - {world:.1f} = {offline:.1f}%",
               "같은 사실을 뒤집어 물으면 전혀 다른 크기로 느껴집니다."),
    ])

# ── 7. 환율 ──────────────────────────────────────────────────────
fx = load_json("usdkrw.json")["rates"]
FX = sorted((d, v["KRW"]) for d, v in fx.items() if "KRW" in v)
hi_d, hi_v = max(FX, key=lambda x: x[1])
lo_d, lo_v = min(FX, key=lambda x: x[1])
avg_fx = mean(v for _, v in FX)
under1200 = sum(1 for _, v in FX if v < 1200) / len(FX) * 100
last_d, last_v = FX[-1]
era = ("1997~1999년 외환위기" if hi_d < "2005" else
       "2008~2009년 금융위기" if hi_d < "2012" else
       "2020년 코로나" if hi_d < "2022" else "2022년 이후")

topic(
    "usdkrw", "💵", "원달러 환율 26년",
    "1999년부터 오늘까지의 원달러 환율",
    "Frankfurter (유럽중앙은행 고시)", "https://frankfurter.dev/",
    [
        slider("x1", "1999년 이후 원달러 환율의 최고 기록은?",
               hi_v, "원", 1100, 1800, 25,
               f"{hi_d} {hi_v:,.2f}원",
               "최고치는 위기의 기억과 함께 남지만, 정확한 시점은 자주 헷갈립니다."),
        choice("x2", "그 최고치를 찍은 시기는?",
               ["1997~1999년 외환위기", "2008~2009년 금융위기",
                "2020년 코로나", "2022년 이후"], era,
               f"최고 {hi_v:,.2f}원 ({hi_d}). 이 데이터는 1999년부터라 "
               f"1997~98년 외환위기 구간은 포함되어 있지 않습니다",
               "데이터가 시작하는 시점을 확인하지 않으면 '역대 최고'를 잘못 "
               "말하게 됩니다."),
        slider("x3", "26년간의 평균 환율은?",
               avg_fx, "원", 900, 1500, 25,
               f"{FX[0][0]} ~ {FX[-1][0]} 거래일 {len(FX):,}일 평균 "
               f"{avg_fx:,.0f}원 (최저 {lo_v:,.0f}원 · {lo_d})",
               "최근 값이 기준점이 되어 과거 평균을 높게 잡게 됩니다."),
        slider("x4", "환율이 1,200원 아래였던 날은 전체의 몇 %일까요?",
               under1200, "%", 0, 100, 5,
               f"거래일 {len(FX):,}일 중 1,200원 미만은 "
               f"{sum(1 for _, v in FX if v < 1200):,}일",
               "'원래 1,100원대였는데'라는 감각이 맞는지 비율로 확인해 봅니다."),
        slider("x5", f"{last_d} 기준 환율은?",
               last_v, "원", 1100, 1800, 25,
               f"{last_d} {last_v:,.2f}원",
               "가장 최근 값조차 기억은 며칠 전 뉴스에 묶여 있습니다."),
    ])

# ── 8. 도시 비교 ─────────────────────────────────────────────────
CITY = {}
for cid in ("seoul", "tokyo", "london", "singapore"):
    _d = load_json(f"city_{cid}.json")["daily"]
    CITY[cid] = [{"d": dt.date.fromisoformat(t), "hi": a, "lo": b, "r": c}
                 for t, a, b, c in zip(_d["time"], _d["temperature_2m_max"],
                                       _d["temperature_2m_min"],
                                       _d["precipitation_sum"])]
CN = {"seoul": "서울", "tokyo": "도쿄", "london": "런던", "singapore": "싱가포르"}
YRS = 30
c_rain = {k: sum(x["r"] for x in v) / YRS for k, v in CITY.items()}
c_days = {k: sum(1 for x in v if x["r"] >= 1) / YRS for k, v in CITY.items()}
c_temp = {k: mean((x["hi"] + x["lo"]) / 2 for x in v) for k, v in CITY.items()}
c_hot = {k: max(x["hi"] for x in v) for k, v in CITY.items()}
c_jan = {k: mean(x["lo"] for x in v if x["d"].month == 1) for k, v in CITY.items()}
dry = min(c_rain, key=c_rain.get)
hottest = max(c_hot, key=c_hot.get)
colder = "서울" if c_jan["seoul"] < c_jan["tokyo"] else "도쿄"

topic(
    "cities", "🏙️", "서울·도쿄·런던·싱가포르",
    "네 도시의 30년 평년값 (1991~2020)",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        choice("c1", "1년 강수량이 가장 적은 도시는?",
               ["서울", "도쿄", "런던", "싱가포르"], CN[dry],
               " · ".join(f"{CN[k]} {c_rain[k]:,.0f}mm" for k in CITY),
               "비가 자주 오는 것과 많이 오는 것은 다릅니다. 런던은 자주 오지만 "
               "적게 옵니다."),
        slider("c2", "런던에서 1년에 비가 오는 날(1mm 이상)은 며칠일까요?",
               c_days["london"], "일", 40, 220, 5,
               f"런던 {c_days['london']:.0f}일 · 서울 {c_days['seoul']:.0f}일 "
               f"(강수량은 런던 {c_rain['london']:,.0f}mm · "
               f"서울 {c_rain['seoul']:,.0f}mm)",
               "런던은 서울보다 비 오는 날이 많은데 총량은 절반입니다. "
               "'며칠 왔나'와 '얼마나 왔나'는 다른 질문입니다."),
        choice("c3", "30년간 가장 높은 기온을 기록한 도시는?",
               ["서울", "도쿄", "런던", "싱가포르"], CN[hottest],
               " · ".join(f"{CN[k]} {c_hot[k]:.1f}도" for k in CITY),
               "적도에 가까울수록 덥다고 생각하지만, 최고기온 기록은 중위도 "
               "도시에서 나옵니다."),
        slider("c4", "서울의 연평균 기온은?",
               c_temp["seoul"], "도", 5, 30, 0.5,
               " · ".join(f"{CN[k]} {c_temp[k]:.1f}도" for k in CITY),
               "여름과 겨울의 기억이 강해서 연평균은 감이 잘 안 옵니다."),
        choice("c5", "1월 밤이 더 추운 도시는?",
               ["서울", "도쿄"], colder,
               f"1월 평균 최저기온 서울 {c_jan['seoul']:.1f}도 · "
               f"도쿄 {c_jan['tokyo']:.1f}도",
               "위도가 비슷해도 대륙의 영향을 받는 도시가 훨씬 춥습니다."),
    ],
    caveat="ERA5 재분석 값이고, 도시별로 관측소 위치와 기준이 다릅니다.")

# ── 9. 지진 ──────────────────────────────────────────────────────
Q = [f["properties"] for f in load_json("quakes.geojson")["features"]]
QK = [f["properties"] for f in load_json("quakes_korea.geojson")["features"]]
n_years = 25
per_year = len(Q) / n_years
m7 = sum(1 for p in Q if p["mag"] >= 7.0) / n_years
biggest = max(Q, key=lambda p: p["mag"])


def region(place):
    return (place or "").split(",")[-1].strip()


top_region = Counter(region(p["place"]) for p in Q).most_common(1)[0]
region_ko = {"Japan": "일본", "Indonesia": "인도네시아", "Chile": "칠레",
             "Philippines": "필리핀"}
kr_band = ("50건 미만" if len(QK) < 50 else "50~150건" if len(QK) <= 150
           else "150~400건" if len(QK) <= 400 else "400건 이상")

topic(
    "quakes", "🌎", "지진은 얼마나 자주",
    "2000~2024년 전 세계 지진 기록",
    "USGS 지진 카탈로그", "https://earthquake.usgs.gov/",
    [
        slider("q1", "규모 5.5 이상 지진은 전 세계에서 1년에 몇 번쯤 일어날까요?",
               per_year, "회", 50, 1200, 50,
               f"2000~2024년 {len(Q):,}건 ÷ {n_years}년 = "
               f"연평균 {per_year:.0f}회",
               "뉴스에 나오는 지진만 세면 실제보다 훨씬 적게 잡게 됩니다."),
        slider("q2", "규모 7.0 이상은 1년에 몇 번쯤일까요?",
               m7, "회", 0, 40, 1,
               f"2000~2024년 규모 7.0 이상 "
               f"{sum(1 for p in Q if p['mag'] >= 7.0)}건, 연평균 {m7:.1f}회",
               "규모는 로그 척도입니다. 0.5만 올라가도 횟수가 크게 줄어듭니다."),
        choice("q3", "규모 5.5 이상 지진이 가장 자주 기록된 나라는?",
               ["일본", "인도네시아", "칠레", "필리핀"],
               region_ko.get(top_region[0], "인도네시아"),
               f"1위 {top_region[0]} {top_region[1]:,}건",
               "지진 하면 떠오르는 나라와 실제로 가장 많이 기록되는 곳은 "
               "다를 수 있습니다."),
        slider("q4", "2000년 이후 기록된 가장 큰 지진의 규모는?",
               biggest["mag"], "", 7.0, 9.9, 0.1,
               f"규모 {biggest['mag']} · "
               f"{dt.datetime.fromtimestamp(biggest['time'] / 1000, dt.UTC):%Y-%m-%d} "
               f"{biggest['place']}",
               "규모 9는 8보다 약 32배 큰 에너지입니다."),
        choice("q5", "한반도 주변(위도 33~39.5도)에서 25년간 기록된 규모 3.0 이상 지진은?",
               ["50건 미만", "50~150건", "150~400건", "400건 이상"], kr_band,
               f"USGS 기준 {len(QK)}건. 이 관측망은 작은 지진을 모두 잡지는 "
               f"못하므로 기상청 집계와 다릅니다",
               "'어느 기관이 센 숫자인가'를 확인하지 않으면 같은 현상도 다른 "
               "값이 됩니다."),
    ],
    caveat="USGS 카탈로그는 작은 지진을 모두 담지 못합니다. 한반도 지진은 "
           "기상청 집계가 더 많습니다.")

# ── 10. 수명 ─────────────────────────────────────────────────────
le = [r for r in load_csv("life_expectancy.csv") if r["life_expectancy_0"]]
l_latest = max(int(r["year"]) for r in le if r["code"] == "KOR")
l_cur = owid_countries(le, l_latest, "life_expectancy_0")
kor_l = l_cur["South Korea"]
l_rank = sorted(l_cur.items(), key=lambda kv: -kv[1])
kor_l_rank = [k for k, _ in l_rank].index("South Korea") + 1
_kle = {r["year"]: float(r["life_expectancy_0"]) for r in le if r["code"] == "KOR"}
kor_1950, kor_1953, kor_1955 = _kle["1950"], _kle["1953"], _kle["1955"]
wld = next(float(r["life_expectancy_0"]) for r in le
           if r["code"] == "OWID_WRL" and int(r["year"]) == l_latest)
trio_l = {c: l_cur[c] for c in ("South Korea", "Japan", "United States")
          if c in l_cur}
top_l = max(trio_l, key=trio_l.get)
name_l = {"South Korea": "한국", "Japan": "일본", "United States": "미국"}

topic(
    "life", "🩺", "얼마나 오래 사나",
    "나라별 기대수명 1950~현재",
    "Our World in Data", "https://ourworldindata.org/grapher/life-expectancy",
    [
        slider("l1", f"{l_latest}년 한국의 기대수명은?",
               kor_l, "세", 60, 95, 1,
               f"{l_latest}년 한국 {kor_l:.1f}세",
               "기대수명은 '지금 태어난 아이가 평균적으로 살 햇수'입니다. "
               "지금 살아 있는 사람의 예상 수명과는 다릅니다."),
        slider("l2", f"기대수명이 긴 순으로 세면 한국은 {len(l_cur)}곳 중 몇 위일까요?",
               kor_l_rank, "위", 1, 60, 1,
               f"{l_latest}년 {len(l_cur)}곳 중 {kor_l_rank}위 "
               f"(1위 {l_rank[0][0]} {l_rank[0][1]:.1f}세)",
               "상위권인 것은 맞지만 몇 위인지는 대개 크게 빗나갑니다."),
        slider("l3", "1950년 한국의 기대수명은?",
               kor_1950, "세", 20, 70, 1,
               f"1950년 {kor_1950:.1f}세. 한국전쟁 기간의 사망이 반영된 값이라 "
               f"1953년 {kor_1953:.1f}세, 1955년 {kor_1955:.1f}세로 빠르게 "
               f"회복합니다. {l_latest}년은 {kor_l:.1f}세",
               "숫자가 튀면 사건을 의심해야 합니다. 이 값은 오류가 아니라 "
               "전쟁의 기록입니다."),
        choice("l4", "한국·일본·미국 중 기대수명이 가장 긴 나라는?",
               ["한국", "일본", "미국"], name_l[top_l],
               " · ".join(f"{name_l[c]} {trio_l[c]:.1f}세" for c in trio_l),
               "가장 잘사는 나라가 가장 오래 사는 나라는 아닙니다."),
        slider("l5", f"{l_latest}년 세계 평균 기대수명은?",
               wld, "세", 50, 90, 1,
               f"{l_latest}년 세계 평균 {wld:.1f}세 · 한국 {kor_l:.1f}세",
               "내가 사는 곳의 수준을 세계 평균으로 착각하기 쉽습니다."),
    ])

# ── 11. 서울의 눈 ────────────────────────────────────────────────
# '눈 온 날' = 하루 강설량 1cm 이상. ERA5 는 0.07cm 같은 아주 적은 값을 자주 내놓아서
# 0 초과로 세면 눈 온 날이 세 배 넘게 불어난다. 쌓일 만한 눈만 센다
s = load_json("seoul_snow.json")["daily"]
S = [{"d": dt.date.fromisoformat(t), "snow": v}
     for t, v in zip(s["time"], s["snowfall_sum"])]
SNOW_CM = 1.0


def snow_days(y):
    return sum(1 for x in S if x["d"].year == y and x["snow"] >= SNOW_CM)


snow_avg = mean(snow_days(y) for y in range(1990, 2025))
snow_90s = mean(snow_days(y) for y in range(1990, 2000))
snow_10s = mean(snow_days(y) for y in range(2015, 2025))
s_ratio = snow_10s / snow_90s if snow_90s else 0
snow_max = max(S, key=lambda x: x["snow"])
# 첫눈은 달력 해로 세면 거의 언제나 1월이 된다. 겨울(7월~이듬해 6월) 단위로 센다.
# 원본이 1990-01 ~ 2024-12 라 온전한 겨울은 1990/91 ~ 2023/24 의 34번
winters = range(1990, 2024)
first_snow = [f for f in (
    next((x["d"] for x in S
          if dt.date(y, 7, 1) <= x["d"] < dt.date(y + 1, 7, 1)
          and x["snow"] >= SNOW_CM), None) for y in winters) if f]
first_m = Counter(f.month for f in first_snow)
first_peak, first_peak_n = first_m.most_common(1)[0]


def in_winter(f):
    """겨울 시작(7월 1일)부터 며칠째인가 — 11월과 이듬해 2월을 한 줄에 세우려고"""
    return (f - dt.date(f.year if f.month >= 7 else f.year - 1, 7, 1)).days


first_early = min(first_snow, key=in_winter)
first_late = max(first_snow, key=in_winter)
snow_month = {m: mean([sum(x["snow"] for x in S
                           if x["d"].year == y and x["d"].month == m)
                       for y in range(1990, 2025)]) for m in range(1, 13)}
snowiest = max(snow_month, key=snow_month.get)
WINTER_M = ["11월", "12월", "1월", "2월"]

topic(
    "seoul-snow", "❄️", "서울에는 눈이 얼마나 오나",
    "1990년부터 2024년까지, 서울의 하루 강설량",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("s1", "1990~2024년, 서울에서 한 해에 눈이 온 날은 평균 며칠일까요?",
               snow_avg, "일", 0, 30, 1,
               f"1990~2024년 해마다 하루 강설량 1cm 이상인 날을 세어 평균하면 "
               f"{snow_avg:.1f}일",
               "눈발이 날린 날과 쌓일 만큼 온 날은 다릅니다. 기준을 정해야 셀 수 "
               "있습니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다
        choice("s2", "1990년대와 2015~2024년, 한 해 눈 온 날은 몇 배 차이일까요?",
               ["약 0.5배", "약 0.8배", "거의 같다", "약 1.5배"],
               ["약 0.5배", "약 0.8배", "거의 같다", "약 1.5배"][
                   0 if s_ratio < 0.65 else 1 if s_ratio < 0.9
                   else 2 if s_ratio < 1.25 else 3],
               f"하루 강설량 1cm 이상인 날의 연평균을 세면 1990~1999년 "
               f"{snow_90s:.1f}일 → 2015~2024년 {snow_10s:.1f}일 ({s_ratio:.2f}배)",
               "'요즘은 눈이 안 온다'는 느낌이 맞는지는 같은 기준으로 세어 봐야 "
               "압니다."),
        slider("s3", "1990~2024년, 서울에서 하루에 가장 많이 내린 눈은 몇 cm일까요?",
               snow_max["snow"], "cm", 0, 50, 1,
               f"1990~2024년 하루 강설량 중 최댓값은 "
               f"{snow_max['d']:%Y년 %m월 %d일} {snow_max['snow']:.1f}cm",
               "기억에 남은 폭설의 숫자는 출처마다 다릅니다. 격자 평균인 재분석 "
               "값은 관측소보다 낮게 나오기 쉽습니다."),
        choice("s4", "1990~2024년, 서울의 첫눈은 보통 몇 월에 올까요?",
               WINTER_M, f"{first_peak}월",
               f"1990/91~2023/24 겨울(7월~이듬해 6월) {len(winters)}번마다 하루 "
               f"강설량 1cm 이상인 첫날의 달을 세면 "
               + " · ".join(f"{m}월 {c}번" for m, c in first_m.most_common()),
               f"'보통'이 늘 그렇다는 뜻은 아닙니다. {len(first_snow)}번 중 "
               f"{len(first_snow) - first_peak_n}번은 {first_peak}월이 아니었고, "
               f"가장 이른 첫눈은 {first_early:%Y년 %m월 %d일}, 가장 늦은 첫눈은 "
               f"{first_late:%Y년 %m월 %d일}이었습니다."),
        choice("s5", "서울에서 눈이 가장 많이 내리는 달은 언제일까요?",
               WINTER_M, f"{snowiest}월",
               "1990~2024년 달마다 강설량을 합해 해마다 평균하면 "
               + " · ".join(f"{m}월 {snow_month[m]:.1f}cm" for m in (11, 12, 1, 2))
               + f" (가장 많은 달 {snowiest}월)",
               "가장 추운 달과 눈이 가장 많이 오는 달이 같은지는 따로 세어 봐야 "
               "압니다."),
    ],
    caveat="ERA5 재분석의 강설량은 하늘에서 내린 눈의 양을 추정한 값입니다. "
           "기상청이 재는 적설(쌓인 눈의 깊이)과는 다른 양이라 값이 다르게 나옵니다.")


# ════════════════════════════════════════════════════════════════
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for t in TOPICS:
        assert len(t["questions"]) == 5, f"{t['id']}: 문항이 5개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))
        index.append({k: t[k] for k in ("id", "emoji", "title", "blurb",
                                        "source")})

    # 제목·부제는 화면을 바꾸며 고친 값을 지킨다 (2장에서 내 제목으로 바꾼다).
    # 다시 계산해도 내 제목이 «감 테스트»로 돌아가지 않게, 있던 값을 읽어 쓴다
    old = {}
    if (APP / "topics.json").exists():
        try:
            old = json.load(io.open(APP / "topics.json", encoding="utf-8"))
        except ValueError:
            old = {}
    io.open(APP / "topics.json", "w", encoding="utf-8").write(json.dumps({
        "title": old.get("title", "감 테스트"),
        "subtitle": old.get("subtitle", "숫자에 대한 당신의 감은 몇 점입니까"),
        # 등급·문구는 여기서 고칩니다. 코드를 건드릴 일이 아닙니다
        "grades": [
            {"min": 90, "name": "촉이 데이터급", "emoji": "🎯"},
            {"min": 70, "name": "감이 좋은 편", "emoji": "📊"},
            {"min": 50, "name": "보통의 감각", "emoji": "🙂"},
            {"min": 30, "name": "느낌대로 삽니다", "emoji": "🎲"},
            {"min": 0, "name": "감은 접어두시죠", "emoji": "🙈"},
        ],
        "reactions_choice": {"hit": "맞히셨습니다", "miss": "다들 그렇게 찍습니다"},
        "reactions": [
            {"max": 5, "text": "촉이 좋으시네요"},
            {"max": 20, "text": "비슷하게 보셨습니다"},
            {"max": 60, "text": "음…"},
            {"max": 999, "text": "꽤 멀리 가셨습니다"},
        ],
        "topics": index,
    }, ensure_ascii=False, indent=2))

    # 사람이 읽는 정답지
    md = [f"# 문항 정답지 — {len(TOPICS)}주제 "
          f"{sum(len(t['questions']) for t in TOPICS)}문항", "",
          "> 모든 값은 `data/raw/` 의 원본에서 `tools/build_topics.py` 가 계산합니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "",
               f"- 출처: {t['source']} · {t['source_url']}"]
        if t["caveat"]:
            md += [f"- **한계** {t['caveat']}"]
        md += [""]
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            md += [f"**{q['text']}**", "",
                   f"- 정답 **{a}**", f"- 근거 {q['basis']}",
                   f"- 왜 틀리나 {q['why']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}  ({t['source']})")
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {a}")


if __name__ == "__main__":
    main()
