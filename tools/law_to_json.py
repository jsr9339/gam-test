# -*- coding: utf-8 -*-
"""법령 파일 → 조문별 JSON. 국가법령정보센터에서 「DOC」 으로 저장한 파일을 읽는다.

그 「DOC」 은 이름만 .doc 이고 속은 RTF 다. 한글은 \\u 이스케이프로 들어 있다.
외부 라이브러리 없이 RTF 를 직접 읽는다 (pip 설치가 필요 없다).

  읽는 것   data/raw/근로기준법.doc
  쓰는 것   data/raw/근로기준법.json

**같은 조문이 두 번 나올 수 있다.** 개정됐지만 아직 시행 전이면 현행본 뒤에
시행 예정본이 붙는다. 앞의 것을 "현행", 뒤의 것을 "예정" 으로 나눠 둘 다 담는다.
퀴즈 정답은 "현행" 에서 고른다.

부칙은 담지 않는다 — 부칙의 조문 번호(제1조 …)는 본문과 겹친다.

실행 (저장소 최상위에서):
    python tools/law_to_json.py data/raw/근로기준법.doc
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 글자로 옮기지 않을 RTF 묶음 — 글꼴표 · 색표 · 그림 · 쪽 머리글/바닥글
SKIP = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "footer", "header",
        "listtable", "listoverridetable", "shppict", "nonshppict", "object"}
BREAK = {"par": "\n", "line": "\n", "row": "\n", "cell": " ", "tab": "\t"}


def rtf_text(data: bytes) -> str:
    out, stack = [], []
    skip, uc, pending = False, 1, 0
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c == 0x7B:                                  # {
            stack.append((skip, uc)); i += 1
        elif c == 0x7D:                                # }
            skip, uc = stack.pop() if stack else (False, 1); i += 1
        elif c == 0x5C:                                # 역슬래시
            i += 1
            if i >= n:
                break
            c = data[i]
            if c == 0x27:                              # \'hh
                if pending:
                    pending -= 1
                elif not skip:
                    out.append(bytes([int(data[i + 1:i + 3], 16)]).decode("cp1252", "replace"))
                i += 3
            elif chr(c).isalpha():
                j = i
                while j < n and chr(data[j]).isalpha():
                    j += 1
                word = data[i:j].decode()
                k = j
                if k < n and (data[k] == 0x2D or chr(data[k]).isdigit()):
                    k += 1
                    while k < n and chr(data[k]).isdigit():
                        k += 1
                arg = data[j:k].decode() or None
                if k < n and data[k] == 0x20:
                    k += 1
                i = k
                if word == "bin":
                    i += int(arg)                      # 그림 바이트를 건너뛴다
                elif word in SKIP:
                    skip = True
                elif word == "uc":
                    uc = int(arg)
                elif word == "u":
                    if not skip:
                        v = int(arg)                   # 32767 넘는 글자는 음수로 적혀 있다
                        out.append(chr(v + 65536 if v < 0 else v))
                    pending = uc                       # 뒤따르는 대체 글자는 버린다
                elif word in BREAK and not skip:
                    out.append(BREAK[word])
            else:                                      # \* \\ \{ \} \~
                if c == 0x2A:
                    skip = True
                elif not skip and chr(c) in "\\{}":
                    out.append(chr(c))
                elif not skip and c == 0x7E:
                    out.append(" ")
                i += 1
        elif c in (0x0D, 0x0A):
            i += 1
        else:
            if pending:
                pending -= 1
            elif not skip:
                out.append(chr(c))
            i += 1
    return "".join(out)


HEAD = re.compile(r"^(제\d+조(?:의\d+)?)(?:\(([^)]*)\))?\s*(.*)$")
CHAPTER = re.compile(r"^제\d+장(?:의\d+)?\s")
SECTION = re.compile(r"^제\d+(?:절|관)(?:의\d+)?\s")
WHEN = re.compile(r"^\[시행일[:\]]\s*(?:(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\])?\s*(.*)$")


def ymd(y, m, d):
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def parse(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    # 「근로자퇴직급여 보장법 ( 약칭: 퇴직급여법 )」 → 이름과 약칭을 나눈다
    name = re.match(r"(.+?)\s*(?:\(\s*약칭:\s*(.+?)\s*\))?$", lines[0])
    m = re.match(r"\[시행 (\d{4})\. (\d{1,2})\. (\d{1,2})\.\] \[(법률 제\d+호)", lines[1])
    meta = {"law": name[1], "short": name[2] or name[1],
            "enforced": ymd(*m.groups()[:3]), "act": m[4]}

    articles, chapter, cur = [], None, None
    for ln in lines[2:]:
        if ln.startswith("부칙"):
            break
        if CHAPTER.match(ln):
            chapter, cur = ln, None
            continue
        if SECTION.match(ln):
            continue                                   # 「제2절 …」 이 앞 조문 본문에 붙지 않게
        h = HEAD.match(ln)
        if h and (h[2] is not None or h[3].startswith("삭제")):
            cur = {"no": h[1], "title": h[2], "chapter": chapter,
                   "deleted": h[2] is None, "lines": [h[3]] if h[3] else [], "notes": []}
            articles.append(cur)
            continue
        if cur is None:
            continue                                   # 머리의 담당 부서 · 전화번호
        if WHEN.match(ln) or (ln.startswith("[") and ln.endswith("]")):
            cur["notes"].append(ln)                    # [시행일: …] · [본조신설 …] · [제목개정 …]
        else:
            cur["lines"].append(ln)

    seen = set()
    for a in articles:
        a["status"] = "예정" if a["no"] in seen else "현행"
        seen.add(a["no"])
        a["effective"] = meta["enforced"]
        if a["status"] == "예정":
            dates = [ymd(*w.groups()[:3]) for w in map(WHEN.match, a["notes"]) if w and w[1]]
            a["effective"] = min(dates) if dates else None
        a["text"] = "\n".join(a.pop("lines"))

    keys = ["no", "title", "chapter", "status", "effective", "deleted", "text", "notes"]
    meta["articles"] = [{k: a[k] for k in keys} for a in articles]
    return meta


def main(src: Path) -> None:
    law = parse(rtf_text(src.read_bytes()))
    out = src.with_suffix(".json")
    out.write_text(json.dumps(law, ensure_ascii=False, indent=2), encoding="utf-8")

    A = law["articles"]
    now = [a for a in A if a["status"] == "현행"]
    print(f"{law['law']}  [시행 {law['enforced']}] {law['act']}")
    print(f"  조문 {len(A)}개 = 현행 {len(now)} + 시행 예정 {len(A) - len(now)}"
          f"  (삭제된 조문 {sum(a['deleted'] for a in now)})")
    print(f"  마지막 조문 {now[-1]['no']}  →  {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python tools/law_to_json.py data/raw/근로기준법.doc")
    main(Path(sys.argv[1]))
