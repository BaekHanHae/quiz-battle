"""JMdict / KANJIDIC2 로딩 공용 모듈.

gen_kokugo_reading.py 와 validate_bank.py 가 같은 '진실'을 공유하도록
파싱 로직을 한곳에 둔다.

데이터 출처: EDRDG (JMdict, KANJIDIC2) — CC BY-SA 4.0. SOURCES.md 참조.
"""
import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"

PRI_TAGS = {"news1", "news2", "ichi1", "ichi2", "spec1", "spec2", "gai1", "gai2"}

# 아이용 문제에서 제외할 misc 태그 (sense의 misc 텍스트 앞부분으로 매칭)
BAD_MISC_PREFIXES = (
    "archaic",      # 고어
    "obscure",      # 난해어
    "rare",         # 희귀어
    "vulgar",       # 비속어
    "derogatory",   # 경멸 표현
    "dated",        # 구식 표현
    "slang",        # 속어
)
UK_TEXT = "usually written using kana alone"

CJK_RANGES = ((0x4E00, 0x9FFF), (0x3400, 0x4DBF))
ITERATION_MARK = "々"  # U+3005


def _open(path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def kata_to_hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def load_kanji():
    """KANJIDIC2 → (grade: {char: int}, readings: {char: set(hiragana readings)}).

    grade가 없는 한자는 상용·인명용 밖이라 dict에 없다.
    readings는 熟字訓 판정(단어 읽기를 한자별로 쪼갤 수 있는가)에만 쓴다.
    """
    grade, readings = {}, {}
    path = SOURCES / "kanjidic2.xml.gz"
    with _open(path) as f:
        for _ev, el in ET.iterparse(f, events=("end",)):
            if el.tag != "character":
                continue
            lit = el.findtext("literal")
            g = el.findtext("./misc/grade")
            if g is not None:
                try:
                    grade[lit] = int(g)
                except ValueError:
                    pass
            rset = set()
            for r in el.findall("./reading_meaning/rmgroup/reading"):
                rtype = r.get("r_type")
                if rtype == "ja_on":
                    rset.add(kata_to_hira(r.text))
                elif rtype == "ja_kun":
                    t = r.text.lstrip("-")
                    rset.add(t.replace(".", ""))          # 전체형 (つぐ)
                    stem = t.split(".")[0]
                    if stem:
                        rset.add(stem)                    # 어간 (つ)
            if rset:
                readings[lit] = rset
            el.clear()
    return grade, readings


def is_kanji_char(c):
    if c == ITERATION_MARK:
        return True
    o = ord(c)
    return any(lo <= o <= hi for lo, hi in CJK_RANGES)


def kanji_chars(keb):
    """keb 안의 한자 목록 (々는 앞 한자를 반복한 것으로 간주해 그대로 포함)."""
    return [c for c in keb if is_kanji_char(c)]


def max_grade(keb, grade):
    """구성 한자의 최대 grade. grade를 모르는 한자가 있으면 None.

    々는 바로 앞 한자의 grade를 따른다.
    """
    mx = 0
    prev = None
    for c in keb:
        if not is_kanji_char(c):
            return None
        if c == ITERATION_MARK:
            if prev is None:
                return None
            g = prev
        else:
            g = grade.get(c)
            if g is None:
                return None
            prev = g
        mx = max(mx, g)
    return mx


class KebInfo:
    __slots__ = ("readings", "answer", "has_pri", "has_clean", "uk_all",
                 "_answer_from_pri")

    def __init__(self):
        self.readings = set()   # 이 표제어의 실제 읽기 전부 (모든 항목 합집합)
        self.answer = None      # 대표 항목의 첫 번째 읽기
        self.has_pri = False    # pri 태그를 가진 항목이 하나라도 있는가
        self.has_clean = False  # 부적합 misc 없는 항목이 하나라도 있는가
        self.uk_all = True      # 모든 항목이 '보통 가나 표기'인가
        self._answer_from_pri = False


def _misc_is_bad(misc_texts):
    return any(t.startswith(BAD_MISC_PREFIXES) for t in misc_texts)


def load_jmdict():
    """JMdict_e → {keb: KebInfo}."""
    out = {}
    path = SOURCES / "JMdict_e.gz"
    with _open(path) as f:
        for _ev, el in ET.iterparse(f, events=("end",)):
            if el.tag != "entry":
                continue
            senses = el.findall("sense")
            sense_misc = [[m.text or "" for m in s.findall("misc")] for s in senses]
            entry_bad = bool(senses) and all(_misc_is_bad(ms) for ms in sense_misc)
            entry_uk = bool(senses) and all(UK_TEXT in ms for ms in sense_misc)

            rebs = []  # (reb, {적용 가능한 keb 집합 or None}, re_pri set)
            for r in el.findall("r_ele"):
                reb = r.findtext("reb")
                restr = {x.text for x in r.findall("re_restr")}
                rpri = {x.text for x in r.findall("re_pri")}
                rebs.append((reb, restr or None, rpri))

            for k in el.findall("k_ele"):
                keb = k.findtext("keb")
                if not keb:
                    continue
                kpri = {x.text for x in k.findall("ke_pri")}
                applicable = [(reb, rpri) for reb, restr, rpri in rebs
                              if restr is None or keb in restr]
                if not applicable:
                    continue
                info = out.setdefault(keb, KebInfo())
                for reb, _ in applicable:
                    info.readings.add(reb)
                entry_pri = bool(kpri & PRI_TAGS) or any(rp & PRI_TAGS for _, rp in applicable)
                if entry_pri:
                    info.has_pri = True
                if not entry_bad:
                    info.has_clean = True
                if not entry_uk:
                    info.uk_all = False
                # 대표 읽기: pri 항목의 첫 읽기를 우선, 없으면 처음 본 항목의 첫 읽기
                if info.answer is None or (entry_pri and not info._answer_from_pri):
                    if entry_pri or info.answer is None:
                        info.answer = applicable[0][0]
                        info._answer_from_pri = entry_pri
            el.clear()
    return out


DAKUTEN = {}
for _plain, _voiced in [
    ("かきくけこ", "がぎぐげご"), ("さしすせそ", "ざじずぜぞ"),
    ("たちつてと", "だぢづでど"), ("はひふへほ", "ばびぶべぼ"),
    ("はひふへほ", "ぱぴぷぺぽ"),
]:
    for p, v in zip(_plain, _voiced):
        DAKUTEN.setdefault(p, []).append(v)
        DAKUTEN.setdefault(v, []).append(p)
# う→ゔ는 표기 흔들기로 부적절해 제외


def segmentable(reading, keb, kanji_readings):
    """단어 읽기를 한자별 읽기로 쪼갤 수 있으면 True (아니면 熟字訓 추정).

    연탁 변형도 허용한다. 々는 앞 한자의 읽기 선택지를 그대로 쓴다.
    """
    chars = []
    for c in keb:
        if c == ITERATION_MARK:
            chars.append(chars[-1] if chars else None)
        else:
            chars.append(c)
    if any(c is None for c in chars):
        return False
    options = []
    for c in chars:
        base = kanji_readings.get(c, set())
        opts = set(base)
        for r in base:  # 연탁 변형
            if r and r[0] in DAKUTEN:
                for v in DAKUTEN[r[0]]:
                    opts.add(v + r[1:])
        options.append(opts)

    memo = {}

    def rec(i, rest):
        if i == len(options):
            return rest == ""
        key = (i, rest)
        if key in memo:
            return memo[key]
        ok = False
        for r in options[i]:
            if r and rest.startswith(r) and rec(i + 1, rest[len(r):]):
                ok = True
                break
        memo[key] = ok
        return ok

    return rec(0, reading)
