"""문제 은행 CSV 검증: 형식 검증 + 사실 검증(JMdict/KANJIDIC2 대조).

사용법:
  python validate_bank.py <input.csv> [--out <valid.csv>] [--rejects <rejects.csv>]

- 형식: 선택지 정확히 4개·빈 값 없음·중복 없음 / answer ∈ choices /
  level ∈ {shou5, chuu1, ippan} / subject+level 내 question 중복 금지.
- 사실 (subject=ja이고 source에 jmdict가 포함된 행):
  question이 JMdict에 존재하고 answer가 실제 읽기 집합에 포함 /
  오답이 실제 읽기 집합과 겹치지 않음 / 구성 한자 최대 grade <= 레벨 상한.
- 통과분은 --out(기본: <input>.valid.csv), 반려분은 rejects.csv에 사유와 함께.
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from jm_sources import load_jmdict, load_kanji, max_grade  # noqa: E402

LEVELS = {"shou5", "chuu1", "ippan"}
LEVEL_GRADE_CAP = {"shou5": 5, "chuu1": 8, "ippan": 99}
LEVEL_GRADE_MIN = {"shou5": 0, "chuu1": 6, "ippan": 9}
SUBJECTS = {"ja", "en"}
FIELDS = ["subject", "level", "question", "choice1", "choice2", "choice3",
          "choice4", "answer", "source", "note"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    ap.add_argument("--rejects", default=None)
    args = ap.parse_args()

    in_path = Path(args.input)
    if args.out:
        out_path = Path(args.out)
    elif str(in_path).endswith(".csv"):
        out_path = Path(str(in_path)[:-4] + ".valid.csv")
    else:
        out_path = Path(str(in_path) + ".valid.csv")
    rej_path = Path(args.rejects) if args.rejects else in_path.parent / "rejects.csv"

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"입력: {len(rows)}행")

    need_fact = any(r.get("subject") == "ja" and "jmdict" in (r.get("source") or "")
                    for r in rows)
    jmdict = grade = None
    if need_fact:
        print("사실 검증용 JMdict/KANJIDIC2 로딩...")
        grade, _ = load_kanji()
        jmdict = load_jmdict()

    valid, rejects = [], []
    reasons = Counter()
    seen_q = set()

    def reject(row, reason):
        reasons[reason] += 1
        r = dict(row)
        r["reject_reason"] = reason
        rejects.append(r)

    for row in rows:
        subject = (row.get("subject") or "").strip()
        level = (row.get("level") or "").strip()
        q = (row.get("question") or "").strip()
        choices = [(row.get(f"choice{i}") or "").strip() for i in range(1, 5)]
        answer = (row.get("answer") or "").strip()
        source = (row.get("source") or "").strip()

        # ---- 형식 검증 ----
        if subject not in SUBJECTS:
            reject(row, "bad_subject"); continue
        if level not in LEVELS:
            reject(row, "bad_level"); continue
        if not q or any(not c for c in choices) or not answer:
            reject(row, "empty_field"); continue
        if len(set(choices)) != 4:
            reject(row, "choices_not_distinct"); continue
        if answer not in choices:
            reject(row, "answer_not_in_choices"); continue
        key = (subject, level, q)
        if key in seen_q:
            reject(row, "duplicate_question"); continue
        seen_q.add(key)

        # ---- 사실 검증 (생성분 국어 읽기) ----
        if subject == "ja" and "jmdict" in source and jmdict is not None:
            info = jmdict.get(q)
            if info is None:
                reject(row, "not_in_jmdict"); continue
            if answer not in info.readings:
                reject(row, "answer_not_a_real_reading"); continue
            distractors = [c for c in choices if c != answer]
            if any(d in info.readings for d in distractors):
                reject(row, "distractor_is_real_reading"); continue
            mg = max_grade(q, grade)
            if mg is None:
                # grade 없는 한자(상용 외)를 포함한 단어는 ippan만 허용
                if level != "ippan":
                    reject(row, "kanji_grade_unknown"); continue
            else:
                if mg > LEVEL_GRADE_CAP[level]:
                    reject(row, "grade_over_level_cap"); continue
                if mg < LEVEL_GRADE_MIN[level]:
                    reject(row, "grade_under_level_min"); continue

        valid.append(row)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in valid:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    with open(rej_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + ["reject_reason"])
        w.writeheader()
        for r in rejects:
            w.writerow({k: r.get(k, "") for k in FIELDS + ["reject_reason"]})

    print(f"검증 통과: {len(valid)}행 → {out_path}")
    print(f"검증 반려: {len(rejects)}행 → {rej_path}")
    print(f"반려 사유 분포: {dict(reasons)}")


if __name__ == "__main__":
    main()
