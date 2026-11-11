"""quiz-battle 서버.

호스트 PC에서 실행하면 LAN 주소와 QR 코드를 표시하고, 스마트폰 브라우저가
WebSocket으로 접속해 방을 만들고/입장해서 동시에 퀴즈 배틀을 진행한다.
게임 수치(점수, 아이템 효과 시간 등)는 config.json에서 읽는다.
"""
import base64
import json
import os
import random
import secrets
import socket
import sqlite3
import string
import sys
import time
from datetime import datetime
from fractions import Fraction
from io import BytesIO
from pathlib import Path

import qrcode
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
CHAR_DIR = BASE / "static" / "characters"
CHAR_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE / "results.sqlite3"

PRESET_IDS = ["cat", "dog", "rabbit", "bear", "fox", "panda", "frog", "owl"]
OFFENSIVE_ITEMS = {"shake", "freeze", "hide", "flip"}
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

app = FastAPI(title="quiz-battle")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

rooms = {}  # code -> room dict


# ---------------------------------------------------------------- DB (랭킹)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS results (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               played_at TEXT,
               room_code TEXT,
               subject TEXT,
               player_name TEXT,
               score INTEGER,
               correct_count INTEGER,
               is_winner INTEGER
           )"""
    )
    conn.commit()
    conn.close()


def save_results(room, results):
    conn = sqlite3.connect(DB_PATH)
    played_at = datetime.now().isoformat(timespec="seconds")
    for r in results:
        conn.execute(
            "INSERT INTO results (played_at, room_code, subject, player_name,"
            " score, correct_count, is_winner) VALUES (?,?,?,?,?,?,?)",
            (played_at, room["code"], room["subject"], r["nickname"],
             r["score"], r["correct"], 1 if r["winner"] else 0),
        )
    conn.commit()
    conn.close()


def load_ranking():
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT player_name, COUNT(*) AS games, SUM(is_winner) AS wins,
                  SUM(score) AS total_score, MAX(score) AS best_score
           FROM results GROUP BY player_name
           ORDER BY wins DESC, total_score DESC"""
    ).fetchall()
    conn.close()
    return [
        {"player_name": n, "games": g, "wins": w, "total_score": ts, "best_score": bs}
        for (n, g, w, ts, bs) in rows
    ]


init_db()


# ---------------------------------------------------------------- 문제 생성
LEVELS = ("shou5", "chuu1", "ippan")
DEFAULT_LEVEL = CONFIG.get("default_level", "shou5")
if DEFAULT_LEVEL not in LEVELS:
    DEFAULT_LEVEL = "shou5"


def fmt_frac(fr):
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"


def fmt_dec(fr):
    """소수 표기. 분모가 2/5의 거듭제곱으로 떨어지지 않으면 분수 표기로 폴백."""
    if fr.denominator == 1:
        return str(fr.numerator)
    d, twos, fives = fr.denominator, 0, 0
    while d % 2 == 0:
        d //= 2
        twos += 1
    while d % 5 == 0:
        d //= 5
        fives += 1
    if d != 1:
        return fmt_frac(fr)
    k = max(twos, fives)
    n = (fr * (10 ** k)).numerator
    digits = str(abs(n)).rjust(k + 1, "0")
    return ("-" if n < 0 else "") + digits[:-k] + "." + digits[-k:]


def pick_distractors(correct, candidates):
    out = []
    for v in candidates:
        if v != correct and v not in out:
            out.append(v)
        if len(out) == 3:
            break
    return out


def fill_distractors(correct, distractors, allow_negative):
    """후보가 모자라면 오프셋을 키워가며 3개까지 채운다."""
    extra = 30
    while len(distractors) < 3:
        c = correct + extra
        extra += 7
        if c != correct and c not in distractors and (allow_negative or c >= 0):
            distractors.append(c)
    return distractors


def make_question(text, correct, distractors, fmt=fmt_frac):
    values = [correct] + list(distractors)
    choices = [fmt(v) for v in values]
    random.shuffle(choices)
    return {"question": text, "choices": choices,
            "answer": choices.index(fmt(correct))}


def gen_arith(cfg):
    allow_neg = cfg.get("allow_negative", False)
    op = random.choice(["+", "-", "*", "/"])
    sym = {"+": "+", "-": "-", "*": "×", "/": "÷"}[op]
    if op in ("+", "-"):
        a = random.randint(cfg["add_sub_min"], cfg["add_sub_max"])
        b = random.randint(cfg["add_sub_min"], cfg["add_sub_max"])
        if allow_neg:
            if random.random() < 0.4:
                a = -a
            if random.random() < 0.4:
                b = -b
        elif op == "-" and b > a:
            a, b = b, a
        r = a + b if op == "+" else a - b
    elif op == "*":
        alt = cfg.get("mul_alt")
        if alt and random.random() < alt["probability"]:
            a = random.randint(alt["a_min"], alt["a_max"])
            b = random.randint(alt["b_min"], alt["b_max"])
        else:
            a = random.randint(cfg["mul_a_min"], cfg["mul_a_max"])
            b = random.randint(cfg["mul_b_min"], cfg["mul_b_max"])
        if allow_neg and random.random() < 0.45:
            if random.random() < 0.5:
                a = -a
            else:
                b = -b
        r = a * b
    else:
        b = random.randint(cfg["divisor_min"], cfg["divisor_max"])
        r = random.randint(cfg["div_result_min"], cfg["div_result_max"])
        if allow_neg:
            if random.random() < 0.4:
                b = -b
            if random.random() < 0.4:
                r = -r
        a = b * r
    correct = Fraction(r)
    offsets = [1, -1, 2, -2, 10, -10, 5, -5, 3, -3, 20, -20, 11, -11, 100, -100]
    cands = [correct + o for o in offsets]
    if not allow_neg:
        cands = [c for c in cands if c >= 0]
    distractors = fill_distractors(correct, pick_distractors(correct, cands), allow_neg)
    return make_question(f"{a} {sym} {b} = ?", correct, distractors)


def gen_fraction(cfg):
    dens = cfg["fraction_denominators"]
    op = random.choice(cfg.get("fraction_ops", ["+", "-"]))
    same_p = cfg.get("fraction_same_denominator_probability", 0.0)
    d1 = random.choice(dens)
    d2 = d1 if random.random() < same_p else random.choice(dens)
    f1 = Fraction(random.randint(1, d1), d1)
    f2 = Fraction(random.randint(1, d2), d2)
    if op == "+":
        correct = f1 + f2
    elif op == "-":
        if f2 > f1:
            f1, f2 = f2, f1
        correct = f1 - f2
    elif op == "*":
        correct = f1 * f2
    else:
        correct = f1 / f2
    sym = {"+": "+", "-": "-", "*": "×", "/": "÷"}[op]
    cands = [
        correct + Fraction(1, d1), correct - Fraction(1, d1),
        correct + Fraction(1, d2), correct - Fraction(1, d2),
        Fraction(correct.numerator + 1, correct.denominator),
        correct + 1, correct - 1,
        correct + Fraction(1, 2), correct - Fraction(1, 2),
    ]
    distractors = fill_distractors(
        correct, pick_distractors(correct, [c for c in cands if c >= 0]), False)
    return make_question(f"{fmt_frac(f1)} {sym} {fmt_frac(f2)} = ?", correct, distractors)


def gen_decimal(cfg):
    allow_neg = cfg.get("allow_negative", False)
    scale = 10
    op = random.choice(cfg.get("decimal_ops", ["+", "-"]))
    sym = {"+": "+", "-": "-", "*": "×"}[op]
    a = Fraction(random.randint(1, cfg.get("decimal_hi", 99)), scale)
    b = Fraction(random.randint(1, cfg.get("decimal_hi", 99)), scale)
    if allow_neg and random.random() < 0.35:
        if random.random() < 0.5:
            a = -a
        else:
            b = -b
    if op == "-" and not allow_neg and b > a:
        a, b = b, a
    if op == "+":
        correct = a + b
    elif op == "-":
        correct = a - b
    else:
        correct = a * b
    step = Fraction(1, scale)
    cands = [correct + step, correct - step, correct + 2 * step, correct - 2 * step,
             correct + 1, correct - 1, correct + 10 * step, correct - 10 * step]
    if not allow_neg:
        cands = [c for c in cands if c >= 0]
    distractors = fill_distractors(correct, pick_distractors(correct, cands), allow_neg)
    return make_question(f"{fmt_dec(a)} {sym} {fmt_dec(b)} = ?", correct,
                         distractors, fmt=fmt_dec)


def gen_math_questions(level, n):
    cfg = CONFIG["math_by_level"].get(level) or CONFIG["math_by_level"]["ippan"]
    dec_p = cfg.get("decimal_probability", 0.0)
    frac_p = cfg.get("fraction_probability", 0.25)
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < 6000:
        tries += 1
        r = random.random()
        if r < dec_p:
            q = gen_decimal(cfg)
        elif r < dec_p + frac_p:
            q = gen_fraction(cfg)
        else:
            q = gen_arith(cfg)
        if q["question"] in seen:
            continue
        seen.add(q["question"])
        out.append(q)
    return out


def load_bank_questions(subject, level, n):
    path = BASE / "data" / f"questions_{subject}.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    # 자동 생성 은행은 push 크기 제한 때문에 파트 파일로 나뉘어 있다 (tools/question-bank 참조)
    for extra in sorted(path.parent.glob(f"questions_{subject}_gen_*.json")):
        items.extend(json.loads(extra.read_text(encoding="utf-8")))
    valid = []
    for it in items:
        q_text = it.get("question") or it.get("q")
        answer = it.get("answer") or it.get("a")
        choices = list(it.get("choices") or [])
        if q_text and len(choices) == 4 and answer in choices:
            valid.append({"question": q_text, "choices": choices,
                          "answer_text": answer,
                          "level": it.get("level", "ippan")})
    pool = [it for it in valid if it["level"] == level] or valid
    if len(pool) >= n:
        picked = random.sample(pool, n)
    else:
        # 안전장치: 레벨 문제 수가 부족하면 복원 추출로 채운다
        picked = list(pool)
        while len(picked) < n:
            picked.append(random.choice(pool))
    out = []
    for it in picked:
        choices = list(it["choices"])
        random.shuffle(choices)
        out.append({"question": it["question"], "choices": choices,
                    "answer": choices.index(it["answer_text"])})
    return out


def build_questions(subject, level, n):
    if subject == "math":
        return gen_math_questions(level, n)
    return load_bank_questions(subject, level, n)


def sanitize(questions):
    return [{"question": q["question"], "choices": q["choices"]} for q in questions]


# ---------------------------------------------------------------- 플레이어/방
class Player:
    def __init__(self, token, nickname, character):
        self.token = token
        self.nickname = nickname
        self.character = character
        self.ws = None
        self.connected = False
        # 레벨은 방 공통이 아니라 플레이어마다 따로 가진다 (실력차 대응).
        # 새 참가자는 방의 기본 레벨로 시작하고, 호스트가 로비에서 개별 조정한다.
        self.level = DEFAULT_LEVEL
        self.questions = []  # 이 플레이어 전용 문제 세트 (자기 레벨로 생성)
        self.reset()

    def reset(self):
        self.score = 0
        self.progress = 0  # 답한 문제 수
        self.correct = 0
        self.streak = 0
        self.inventory = []
        self.shield = False
        self.finished = False
        self.finish_seq = None
        self.q_start = time.time()


def public_player(p, total):
    return {
        "id": p.token,
        "nickname": p.nickname,
        "character": p.character,
        "level": p.level,
        "score": p.score,
        "progress": p.progress,
        "total": total,
        "correct": p.correct,
        "finished": p.finished,
        "shield": p.shield,
        "connected": p.connected,
    }


def new_room_code():
    while True:
        code = "".join(random.choice(CODE_ALPHABET)
                       for _ in range(CONFIG["room_code_length"]))
        if code not in rooms:
            return code


def clean_nickname(raw):
    name = (raw or "").strip()[:12]
    return name or "プレイヤー"


def clean_character(raw):
    if isinstance(raw, dict) and raw.get("kind") == "preset" and raw.get("id") in PRESET_IDS:
        return {"kind": "preset", "id": raw["id"]}
    return {"kind": "preset", "id": "cat"}


async def send(p, msg):
    if p is not None and p.ws is not None and p.connected:
        try:
            await p.ws.send_json(msg)
        except Exception:
            pass


async def broadcast(room, msg):
    for p in list(room["players"].values()):
        await send(p, msg)


def lobby_msg(room):
    total = CONFIG["questions_per_game"]
    return {
        "type": "lobby_update",
        "room_code": room["code"],
        "host_id": room["host"],
        "state": room["state"],
        "subject": room["subject"],
        "level": room["level"],
        "players": [public_player(p, total) for p in room["players"].values()],
    }


def progress_msg(room):
    total = CONFIG["questions_per_game"]
    return {
        "type": "progress",
        "players": [public_player(p, total) for p in room["players"].values()],
    }


async def finish_game(room):
    if room["state"] != "playing":
        return
    room["state"] = "finished"
    total = CONFIG["questions_per_game"]
    ordered = sorted(
        room["players"].values(),
        key=lambda p: (-p.score, p.finish_seq if p.finish_seq is not None else 10 ** 9),
    )
    results = []
    for i, p in enumerate(ordered):
        results.append({
            "rank": i + 1,
            "id": p.token,
            "nickname": p.nickname,
            "character": p.character,
            "score": p.score,
            "correct": p.correct,
            "total": total,
            "winner": i == 0,
        })
    room["results"] = results
    try:
        save_results(room, results)
    except Exception as e:  # 저장 실패가 게임 종료를 막지 않게
        print("결과 저장 실패:", e)
    await broadcast(room, {"type": "game_over", "results": results})


def maybe_finish(room):
    """전원이 완주했거나 접속이 끊기면 게임을 끝낸다."""
    if room["state"] != "playing" or not room["players"]:
        return False
    if all(p.finished or not p.connected for p in room["players"].values()):
        return True
    return False


# ---------------------------------------------------------------- HTTP
@app.get("/")
async def index():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/ranking")
async def api_ranking():
    return JSONResponse({"ranking": load_ranking()})


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/api/qrcode")
async def api_qrcode(request: Request):
    port = CONFIG["port"]
    url = f"http://{lan_ip()}:{port}/"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# ---------------------------------------------------------------- WebSocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    player = None
    room = None

    async def fail(text):
        await ws.send_json({"type": "error", "message": text})

    try:
        while True:
            try:
                msg = await ws.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                continue
            mtype = msg.get("type")

            if mtype == "rejoin":
                token = msg.get("token", "")
                found_room, found_player = None, None
                for r in rooms.values():
                    if token in r["players"]:
                        found_room, found_player = r, r["players"][token]
                        break
                if not found_player:
                    await fail("セッションが見つかりません。新しく参加してください。")
                    continue
                room, player = found_room, found_player
                player.ws = ws
                player.connected = True
                await ws.send_json({
                    "type": "rejoined",
                    "room_code": room["code"],
                    "player_id": player.token,
                    "is_host": room["host"] == player.token,
                    "state": room["state"],
                })
                if room["state"] == "lobby":
                    await broadcast(room, lobby_msg(room))
                elif room["state"] == "playing":
                    await ws.send_json({
                        "type": "game_state",
                        "subject": room["subject"],
                        "level": player.level,
                        "total": len(player.questions),
                        "questions": sanitize(player.questions),
                        "you": {
                            "progress": player.progress,
                            "score": player.score,
                            "streak": player.streak,
                            "inventory": player.inventory,
                            "shield": player.shield,
                            "finished": player.finished,
                        },
                    })
                    await broadcast(room, progress_msg(room))
                elif room["state"] == "finished" and room.get("results"):
                    await ws.send_json({"type": "game_over", "results": room["results"]})
                continue

            if mtype == "create_room":
                if player is not None:
                    await fail("すでにルームにいます。")
                    continue
                token = secrets.token_hex(8)
                player = Player(token, clean_nickname(msg.get("nickname")),
                                clean_character(msg.get("character")))
                player.ws = ws
                player.connected = True
                code = new_room_code()
                room = {"code": code, "host": token, "players": {token: player},
                        "state": "lobby", "subject": "math", "level": DEFAULT_LEVEL,
                        "questions": [], "results": None, "finish_counter": 0}
                rooms[code] = room
                await ws.send_json({"type": "room_created", "room_code": code,
                                    "player_id": token, "token": token})
                await broadcast(room, lobby_msg(room))
                continue

            if mtype == "join_room":
                if player is not None:
                    await fail("すでにルームにいます。")
                    continue
                code = (msg.get("room_code") or "").strip().upper()
                target = rooms.get(code)
                if not target:
                    await fail("ルームが見つかりません。")
                    continue
                if target["state"] != "lobby":
                    await fail("すでに始まっているルームです。")
                    continue
                if len(target["players"]) >= CONFIG["max_players_per_room"]:
                    await fail("ルームが満員です。")
                    continue
                token = secrets.token_hex(8)
                player = Player(token, clean_nickname(msg.get("nickname")),
                                clean_character(msg.get("character")))
                player.ws = ws
                player.connected = True
                player.level = target["level"]  # 방 기본 레벨로 시작, 호스트가 개별 조정 가능
                room = target
                room["players"][token] = player
                await ws.send_json({"type": "joined", "room_code": code,
                                    "player_id": token, "token": token})
                await broadcast(room, lobby_msg(room))
                continue

            if player is None or room is None:
                await fail("先にルームを作るか参加してください。")
                continue

            if mtype == "set_character":
                player.character = clean_character(msg.get("character"))
                await broadcast(room, lobby_msg(room)
                                if room["state"] == "lobby" else progress_msg(room))

            elif mtype == "upload_character":
                data = msg.get("image", "")
                header, _, b64 = data.partition(",")
                try:
                    raw = base64.b64decode(b64 or data)
                except Exception:
                    await fail("画像を読み取れませんでした。")
                    continue
                if len(raw) > CONFIG["max_custom_image_bytes"]:
                    await fail("画像が大きすぎます。")
                    continue
                ext = "png" if "png" in header else "jpg"
                fname = f"{player.token}.{ext}"
                (CHAR_DIR / fname).write_bytes(raw)
                player.character = {"kind": "custom",
                                    "src": f"/static/characters/{fname}"}
                await ws.send_json({"type": "character_updated",
                                    "character": player.character})
                await broadcast(room, lobby_msg(room)
                                if room["state"] == "lobby" else progress_msg(room))

            elif mtype == "set_subject":
                if room["host"] != player.token or room["state"] != "lobby":
                    continue
                subject = msg.get("subject")
                if subject in ("math", "en", "ja"):
                    room["subject"] = subject
                    await broadcast(room, lobby_msg(room))

            elif mtype == "set_level":
                # 방 기본 레벨 변경 = 전원 일괄 적용. 이후 개별 조정은 set_player_level.
                if room["host"] != player.token or room["state"] != "lobby":
                    continue
                level = msg.get("level")
                if level in LEVELS:
                    room["level"] = level
                    for p in room["players"].values():
                        p.level = level
                    await broadcast(room, lobby_msg(room))

            elif mtype == "set_player_level":
                # 호스트가 참가자 한 사람의 레벨만 지정한다 (실력차 대응).
                if room["host"] != player.token or room["state"] != "lobby":
                    continue
                target = room["players"].get(msg.get("player_id") or "")
                level = msg.get("level")
                if target is not None and level in LEVELS:
                    target.level = level
                    await broadcast(room, lobby_msg(room))

            elif mtype == "start_game":
                if room["host"] != player.token:
                    await fail("ホストだけがスタートできます。")
                    continue
                if room["state"] != "lobby":
                    await fail("すでにゲームが進んでいます。")
                    continue
                subject = msg.get("subject") or room["subject"]
                if subject not in ("math", "en", "ja"):
                    await fail("科目が正しくありません。")
                    continue
                total = CONFIG["questions_per_game"]
                # 문제는 플레이어마다 자기 레벨로 따로 생성한다 (전원 같은 문제 아님).
                per_player = {}
                for p in room["players"].values():
                    qs = build_questions(subject, p.level, total)
                    if len(qs) < total:
                        await fail("問題が足りません。")
                        per_player = None
                        break
                    per_player[p.token] = qs
                if per_player is None:
                    continue
                room["subject"] = subject
                room["questions"] = []
                room["state"] = "playing"
                room["results"] = None
                room["finish_counter"] = 0
                for p in room["players"].values():
                    p.reset()
                    p.questions = per_player[p.token]
                for p in room["players"].values():
                    await send(p, {
                        "type": "game_started",
                        "subject": subject,
                        "level": p.level,
                        "total": len(p.questions),
                        "questions": sanitize(p.questions),
                    })
                await broadcast(room, progress_msg(room))

            elif mtype == "answer":
                if room["state"] != "playing" or player.finished:
                    continue
                idx = player.progress
                if idx >= len(player.questions):
                    continue
                q = player.questions[idx]
                try:
                    choice = int(msg.get("choice"))
                except Exception:
                    continue
                now = time.time()
                elapsed = now - player.q_start
                is_correct = choice == q["answer"]
                item_gained = None
                gained = 0
                if is_correct:
                    player.streak += 1
                    player.correct += 1
                    frac = max(0.0, 1.0 - elapsed / CONFIG["speed_bonus_window_sec"])
                    speed_bonus = int(CONFIG["speed_bonus_max"] * frac)
                    combo = min(player.streak - 1,
                                CONFIG["combo_bonus_max_steps"]) * CONFIG["combo_bonus_step"]
                    gained = CONFIG["points_correct"] + speed_bonus + combo
                    player.score += gained
                    if player.streak % CONFIG["item_every_streak"] == 0:
                        item_gained = random.choice(CONFIG["item_pool"])
                        player.inventory.append(item_gained)
                else:
                    player.streak = 0
                player.progress += 1
                player.q_start = now
                if player.progress >= len(player.questions):
                    player.finished = True
                    room["finish_counter"] += 1
                    player.finish_seq = room["finish_counter"]
                await ws.send_json({
                    "type": "answer_result",
                    "correct": is_correct,
                    "correct_index": q["answer"],
                    "gained": gained,
                    "score": player.score,
                    "streak": player.streak,
                    "item_gained": item_gained,
                    "inventory": list(player.inventory),
                    "progress": player.progress,
                    "total": len(player.questions),
                    "finished": player.finished,
                })
                await broadcast(room, progress_msg(room))
                if maybe_finish(room):
                    await finish_game(room)

            elif mtype == "use_item":
                if room["state"] != "playing" or player.finished:
                    continue
                item = msg.get("item")
                if item not in player.inventory:
                    await fail("そのアイテムを持っていません。")
                    continue
                if item in OFFENSIVE_ITEMS:
                    target = room["players"].get(msg.get("target_id") or "")
                    if target is None or target is player:
                        await fail("攻撃する相手を選んでください。")
                        continue
                    if target.finished:
                        await fail("すでにゴールした相手です。")
                        continue
                    player.inventory.remove(item)
                    if target.shield:
                        target.shield = False
                        await send(target, {"type": "shield_blocked", "item": item,
                                            "from": player.nickname})
                        await ws.send_json({"type": "item_used", "item": item,
                                            "target_id": target.token, "blocked": True})
                    else:
                        effect = {
                            "type": "item_effect",
                            "effect": item,
                            "duration_ms": CONFIG["effects_ms"][item],
                            "from": player.nickname,
                            "question_index": target.progress,
                        }
                        if item == "hide":
                            tq = target.questions[target.progress]
                            wrong = [i for i in range(len(tq["choices"]))
                                     if i != tq["answer"]]
                            effect["choice_index"] = random.choice(wrong)
                        await send(target, effect)
                        await ws.send_json({"type": "item_used", "item": item,
                                            "target_id": target.token, "blocked": False})
                    await broadcast(room, progress_msg(room))
                elif item == "shield":
                    if player.shield:
                        await fail("すでにシールドが有効です。")
                        continue
                    player.inventory.remove(item)
                    player.shield = True
                    await ws.send_json({"type": "item_used", "item": item,
                                        "target_id": player.token, "blocked": False})
                    await broadcast(room, progress_msg(room))
                elif item == "hint":
                    q = player.questions[player.progress]
                    wrong = [i for i in range(len(q["choices"])) if i != q["answer"]]
                    player.inventory.remove(item)
                    await ws.send_json({"type": "hint", "choice_index": random.choice(wrong),
                                        "question_index": player.progress})
                    await ws.send_json({"type": "item_used", "item": item,
                                        "target_id": player.token, "blocked": False})

            elif mtype == "rematch":
                if room["host"] != player.token:
                    await fail("ホストだけがもう一度始められます。")
                    continue
                if room["state"] != "finished":
                    continue
                for p in room["players"].values():
                    p.reset()
                room["state"] = "lobby"
                room["questions"] = []
                room["results"] = None
                await broadcast(room, lobby_msg(room))

    except WebSocketDisconnect:
        pass
    finally:
        if player is not None and room is not None:
            player.connected = False
            player.ws = None
            # 접속이 끊긴 플레이어 때문에 게임을 끝내지는 않는다. 단, 아직 접속 중인
            # 전원이 완주했고 남은 미완주자가 전부 끊긴 경우에만 종료한다.
            # 아무도 접속해 있지 않으면 재접속으로 이어갈 수 있게 게임을 유지한다.
            if room["state"] == "playing":
                if any(p.connected for p in room["players"].values()) and maybe_finish(room):
                    await finish_game(room)
            elif room["state"] == "lobby":
                await broadcast(room, lobby_msg(room))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("QB_PORT", sys.argv[1] if len(sys.argv) > 1
                              else CONFIG["port"]))
    url = f"http://{lan_ip()}:{port}/"
    print("=" * 46)
    print(" quiz-battle 서버가 시작됐습니다")
    print(f" 호스트 화면/접속 주소: {url}")
    print(f" 이 컴퓨터에서: http://127.0.0.1:{port}/")
    print(" 폰 카메라로 아래 QR을 스캔해 접속하세요")
    print("=" * 46)
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
