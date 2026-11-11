"""国語 '숙어 읽기' 문제 자동 생성 (A안: JMdict × KANJIDIC2).

사용법:
  python gen_kokugo_reading.py [--level shou5] [--target 1000] [--seed 42]
                               [--out out/kokugo_shou5.csv]

생성 규칙 (설계 문서 question-bank-method.md):
- 후보: JMdict 항목 중 한자 2–4자 표기, pri 태그 보유, 구성 한자의 최대
  KANJIDIC2 grade가 레벨 구간(shou5 0-5 / chuu1 6-8 / ippan 9-, ippan은
  grade 없는 한자 포함도 허용)에 들고, 부적합 misc만 있는 항목이 아니고,
  '보통 가나 표기(uk)' 전용이 아닌 단어.
- 정답: 대표(pri 우선) 항목의 첫 번째 읽기.
- 오답: (a) 가나 변형 (탁점/촉음/장음/요음 흔들기),
        (b) 같은 한자를 공유하는 다른 후보 단어의 실제 읽기.
  변형이 그 단어의 실제 읽기 집합(JMdict 등재 읽기 전부)에 닿으면 버린다.
- 熟字訓(한자별로 쪼갤 수 없는 통째 읽기)은 전체의 15% 상한, note에 표기.

출처: EDRDG JMdict / KANJIDIC2 (CC BY-SA 4.0)
"""
import argparse
import csv
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from jm_sources import (DAKUTEN, is_kanji_char, kanji_chars, load_jmdict,  # noqa: E402
                        load_kanji, max_grade, segmentable)

LEVEL_GRADE_CAP = {"shou5": 5, "chuu1": 8, "ippan": 99}
# 레벨은 상한만이 아니라 구간(band)으로 나눈다. 구간이 겹치면 레벨별 풀이 섞인다.
# ippan은 grade 9-10(인명용)에 더해, grade가 없는 한자(상용 외)를 포함한 단어도
# 허용한다 — max_grade가 None을 돌려주는 경우로, validate_bank도 ippan만 예외.
LEVEL_GRADE_BAND = {"shou5": (0, 5), "chuu1": (6, 8), "ippan": (9, 99)}
SOURCE_TAG = "jmdict-kanjidic2"
SEED = 42
JUKUJIKUN_CAP_RATIO = 0.15

KANA_RE = __import__("re").compile(r"^[ぁ-ゖァ-ヶー・]+$")

O_ROW = set("おこそとのほもよろをござどぼぽ")
E_ROW = set("えけせてねへめれげぜでべぺ")


def mutate_kana(s, rng):
    """읽기 문자열에 흔들기 변형 1개를 적용한 후보를 돌려준다 (불가하면 None)."""
    ops = ["dakuten", "sokuon", "longvowel", "youon"]
    rng.shuffle(ops)
    for op in ops:
        out = _mutate(s, op, rng)
        if out and out != s:
            return out
    return None


def _mutate(s, op, rng):
    chars = list(s)
    idxs = list(range(len(chars)))
    rng.shuffle(idxs)
    if op == "dakuten":
        for i in idxs:
            if chars[i] in DAKUTEN:
                chars[i] = rng.choice(DAKUTEN[chars[i]])
                return "".join(chars)
    elif op == "sokuon":
        if "っ" in chars:  # 제거
            i = chars.index("っ")
            del chars[i]
            return "".join(chars)
        for i in idxs:  # 삽입: 무성 파열/마찰음 앞 (단어 첫머리는 제외 — っ로 시작하는 단어는 없다)
            if i >= 1 and chars[i] in "かきくけこさしすせそたちつてとぱぴぷぺぽ":
                chars.insert(i, "っ")
                return "".join(chars)
    elif op == "longvowel":
        for i in idxs:
            if i + 1 < len(chars) and chars[i] in O_ROW and chars[i + 1] == "う":
                del chars[i + 1]  # こう → こ
                return "".join(chars)
            if i + 1 < len(chars) and chars[i] in E_ROW and chars[i + 1] == "い":
                del chars[i + 1]  # けい → け
                return "".join(chars)
            if chars[i] in O_ROW and (i + 1 == len(chars) or chars[i + 1] != "う"):
                chars.insert(i + 1, "う")  # こ → こう
                return "".join(chars)
            if chars[i] in E_ROW and (i + 1 == len(chars) or chars[i + 1] != "い"):
                chars.insert(i + 1, "い")  # け → けい
                return "".join(chars)
    elif op == "youon":
        small = {"ゃ": "や", "ゅ": "ゆ", "ょ": "よ"}
        full = {"や": "ゃ", "ゆ": "ゅ", "よ": "ょ"}
        for i in idxs:
            if chars[i] in small:
                chars[i] = small[chars[i]]
                return "".join(chars)
            if i > 0 and chars[i] in full and chars[i - 1] in "きしちにひみりぎじぢびぴ":
                chars[i] = full[chars[i]]
                return "".join(chars)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="shou5", choices=list(LEVEL_GRADE_CAP))
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    band_lo, band_hi = LEVEL_GRADE_BAND[args.level]
    out_path = Path(args.out) if args.out else HERE / "out" / f"kokugo_{args.level}.csv"

    print("KANJIDIC2 로딩...")
    grade, kanji_readings = load_kanji()
    print(f"  grade 보유 한자 {len(grade)}자")
    print("JMdict 로딩...")
    jmdict = load_jmdict()
    print(f"  표제어 {len(jmdict)}개")

    # ---- 후보 풀 ----
    pool = []
    reject_stat = {"not_all_kanji_2_4": 0, "grade_over": 0, "grade_under": 0,
                   "no_pri": 0, "no_clean": 0, "uk_only": 0, "no_answer": 0}
    for keb, info in jmdict.items():
        chars = kanji_chars(keb)
        if not (2 <= len(keb) <= 4) or len(chars) != len(keb):
            reject_stat["not_all_kanji_2_4"] += 1
            continue
        mg = max_grade(keb, grade)
        if mg is None:
            if args.level != "ippan":  # grade 없는 한자 포함 단어는 ippan만
                reject_stat["grade_over"] += 1
                continue
            mg = 99  # 정렬용
        elif mg > band_hi:
            reject_stat["grade_over"] += 1
            continue
        elif mg < band_lo:
            reject_stat["grade_under"] += 1
            continue
        if not info.has_pri:
            reject_stat["no_pri"] += 1
            continue
        if not info.has_clean:
            reject_stat["no_clean"] += 1
            continue
        if info.uk_all:
            reject_stat["uk_only"] += 1
            continue
        if not info.answer:
            reject_stat["no_answer"] += 1
            continue
        is_juku = not segmentable(info.answer, keb, kanji_readings)
        pool.append({"keb": keb, "answer": info.answer, "real": info.readings,
                     "max_grade": mg, "jukujikun": is_juku})
    print(f"후보 풀: {len(pool)}개 (제외 통계: {reject_stat})")

    # 낮은 학년 우선 + 시드 고정 무작위
    pool.sort(key=lambda c: (c["max_grade"], rng.random()))

    # 같은 한자를 공유하는 단어의 읽기 (오답 재료 b)
    by_kanji = {}
    for c in pool:
        for ch in set(kanji_chars(c["keb"])):
            by_kanji.setdefault(ch, set()).add(c["answer"])

    # ---- 생성 ----
    rows = []
    juku_count = 0
    juku_cap = int(args.target * JUKUJIKUN_CAP_RATIO)
    tried = 0
    distractor_fail = 0
    for c in pool:
        if len(rows) >= args.target:
            break
        if c["jukujikun"] and juku_count >= juku_cap:
            continue
        tried += 1
        distractors = []
        seen = set()
        # (b) 같은 한자 공유 단어의 읽기
        shared = set()
        for ch in set(kanji_chars(c["keb"])):
            shared |= by_kanji.get(ch, set())
        shared_list = [r for r in shared
                       if r not in c["real"] and abs(len(r) - len(c["answer"])) <= 2
                       and KANA_RE.match(r)]
        rng.shuffle(shared_list)
        for r in shared_list[:6]:
            if len(distractors) >= 2:  # (b)는 최대 2개까지
                break
            if r not in seen:
                distractors.append(r)
                seen.add(r)
        # (a) 가나 변형
        attempts = 0
        while len(distractors) < 3 and attempts < 60:
            attempts += 1
            m = mutate_kana(c["answer"], rng)
            if not m or m in c["real"] or m in seen or not KANA_RE.match(m):
                continue
            distractors.append(m)
            seen.add(m)
        if len(distractors) < 3:
            distractor_fail += 1
            continue
        choices = distractors + [c["answer"]]
        rng.shuffle(choices)
        rows.append({
            "subject": "ja", "level": args.level, "question": c["keb"],
            "choice1": choices[0], "choice2": choices[1],
            "choice3": choices[2], "choice4": choices[3],
            "answer": c["answer"], "source": SOURCE_TAG,
            "note": "jukujikun" if c["jukujikun"] else "",
        })
        if c["jukujikun"]:
            juku_count += 1

    print(f"생성 시도 {tried}개 중 오답 부족으로 제외 {distractor_fail}개")
    print(f"최종 생성: {len(rows)}문항 (숙자훈 {juku_count}개 = "
          f"{(juku_count / len(rows) * 100 if rows else 0):.1f}%)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["subject", "level", "question",
                                          "choice1", "choice2", "choice3",
                                          "choice4", "answer", "source", "note"])
        w.writeheader()
        w.writerows(rows)
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
