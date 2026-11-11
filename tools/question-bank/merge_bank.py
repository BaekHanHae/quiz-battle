"""검증 통과 CSV를 게임 은행 JSON(data/questions_<subject>.json)에 병합.

사용법:
  python merge_bank.py <valid.csv> [<valid2.csv> ...] [--data-dir ../../data]

- subject별로 대상 파일을 정한다.
- 기존 은행에 같은 question이 있으면 (레벨 무관) 건너뜴다.
- 은행 항목은 게임 로더 호환을 위해 {question, choices, answer, level} 4키만.
- 병합 전후 과목×레벨별 문항 수를 출력한다.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# 자동 생성 은행(tools/question-bank 설계): source가 'jmdict'로 시작하는 행은
# 본 은행이 아니라 questions_<subject>_gen_<level>_part<n>.json 파트 파일로
# 나눠 넣는다 (파트당 최대 문항 수). GitHub push_files 단일 인자 128KB 제한 대응.
PART_MAX = 350


def load_bank(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def counts(items):
    return Counter(it.get("level", "ippan") for it in items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--data-dir", default=str(REPO / "data"))
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    rows_by_subject = {}
    for inp in args.inputs:
        with open(inp, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows_by_subject.setdefault(r["subject"].strip(), []).append(r)

    for subject, rows in sorted(rows_by_subject.items()):
        path = data_dir / f"questions_{subject}.json"
        bank = load_bank(path)
        part_files = sorted(data_dir.glob(f"questions_{subject}_gen_*_part*.json"))
        parts = {p: load_bank(p) for p in part_files}
        before = counts(bank) + counts([it for ps in parts.values() for it in ps])
        existing_q = {it.get("question") for it in bank}
        for ps in parts.values():
            existing_q |= {it.get("question") for it in ps}
        added, added_gen, skipped = 0, 0, 0
        gen_rows = {}
        for r in rows:
            q = r["question"].strip()
            if q in existing_q:
                skipped += 1
                continue
            choices = [r[f"choice{i}"].strip() for i in range(1, 5)]
            answer = r["answer"].strip()
            if answer not in choices or len(set(choices)) != 4:
                skipped += 1
                continue
            item = {"question": q, "choices": choices,
                    "answer": answer, "level": r["level"].strip()}
            existing_q.add(q)
            if (r.get("source") or "").strip().startswith("jmdict"):
                gen_rows.setdefault(item["level"], []).append(item)
                added_gen += 1
            else:
                bank.append(item)
                added += 1
        path.write_text(json.dumps(bank, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        for lv, items in sorted(gen_rows.items()):
            lv_parts = sorted(
                (p for p in parts if f"_gen_{lv}_part" in p.name),
                key=lambda p: int(p.stem.rsplit("part", 1)[1]))
            idx = 0
            for p in lv_parts:
                room = PART_MAX - len(parts[p])
                take = items[idx:idx + room]
                parts[p].extend(take)
                idx += len(take)
                p.write_text(json.dumps(parts[p], ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
            n = (int(lv_parts[-1].stem.rsplit("part", 1)[1]) if lv_parts else 0)
            while idx < len(items):
                n += 1
                p = data_dir / f"questions_{subject}_gen_{lv}_part{n}.json"
                chunk = items[idx:idx + PART_MAX]
                idx += len(chunk)
                p.write_text(json.dumps(chunk, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
                parts[p] = chunk
        after = counts(bank) + counts([it for ps in parts.values() for it in ps])
        total = sum(after.values())
        print(f"[{subject}] 전체 {total}문항 "
              f"(본 은행 병합 +{added}, 생성 파트 +{added_gen}, 건너뜀 {skipped})")
        for lv in ("shou5", "chuu1", "ippan"):
            print(f"  {lv}: {before.get(lv, 0)} → {after.get(lv, 0)}")


if __name__ == "__main__":
    main()
