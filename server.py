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
def fmt_frac(fr):
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"


def pick_distractors(correct, candidates):
    out = []
    for v in candidates:
        if v != correct and v not in out:
            out.append(v)
        if len(out) == 3:
            break
    return out


def make_question(text, correct, distractors):
    values = [correct] + distractors
    choices = [fmt_frac(v) for v in values]
    random.shuffle(choices)
    return {"question": text, "choices": choices,
            "answer": choices.index(fmt_frac(correct))}


def gen_arith(cfg):
    op = random.choice(["+", "-", "*", "/"])
    if op == "+":
        a, b = random.randint(2, cfg["add_sub_max"]), random.randint(2, cfg["add_sub_max"])
        r = a + b
    elif op == "-":
        a = random.randint(2, cfg["add_sub_max"])
        b = random.randint(2, a)
        r = a - b
    elif op == "*":
        a, b = random.randint(2, cfg["mul_a_max"]), random.randint(2, cfg["mul_b_max"])
        r = a * b
    else:
        b = random.randint(2, cfg["divisor_max"])
        r = random.randint(2, cfg["div_result_max"])
        a = b * r
    sym = {"+": "+", "-": "-", "*": "×", "/": "÷"}[op]
    correct = Fraction(r)
    offsets = [1, -1, 2, -2, 10, -10, 5, -5, 3, -3, 20, -20]
    distractors = pick_distractors(correct, [correct + o for o in offsets])
    return make_question(f"{a} {sym} {b} = ?", correct, distractors)


def gen_fraction(cfg):
    dens = cfg["fraction_denominators"]
    d1, d2 = random.choice(dens), random.choice(dens)
    f1 = Fraction(random.randint(1, d1), d1)
    f2 = Fraction(random.randint(1, d2), d2)
    op = random.choice(["+", "-"])
    if op == "-" and f2 > f1:
        f1, f2 = f2, f1
    correct = f1 + f2 if op == "+" else f1 - f2
    cands = [
        correct + Fraction(1, d1), correct - Fraction(1, d1),
        correct + Fraction(1, d2), correct - Fraction(1, d2),
        Fraction(correct.numerator + 1, correct.denominator),
        correct + 1, correct + Fraction(1, 2),
    ]
    distractors = pick_distractors(correct, [c for c in cands if c >= 0])
    return make_question(f"{fmt_frac(f1)} {op} {fmt_frac(f2)} = ?", correct, distractors)


def gen_math_questions(n):
    cfg = CONFIG["math"]
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < 2000:
        tries += 1
        if random.random() < cfg.get("fraction_probability", 0.25):
            q = gen_fraction(cfg)
        else:
            q = gen_arith(cfg)
        if q["question"] in seen:
            continue
        seen.add(q["question"])
        out.append(q)
    return out


def load_bank_questions(subject, n):
    path = BASE / "data" / f"questions_{subject}.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    valid = []
    for it in items:
        choices = list(it["choices"])
        if len(choices) == 4 and it["a"] in choices:
            valid.append(it)
    random.shuffle(valid)
    out = []
    for it in valid[:n]:
        choices = list(it["choices"])
        random.shuffle(choices)
        out.append({"question": it["q"], "choices": choices,
                    "answer": choices.index(it["a"])})
    return out


def build_questions(subject, n):
    if subject == "math":
        return gen_math_questions(n)
    return load_bank_questions(subject, n)


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
    return name or "플레이어"


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
        "players": [public_player(p, total) for p in room["players"].values()],
    }


def progress_msg(room):
    total = len(room["questions"]) or CONFIG["questions_per_game"]
    return {
        "type": "progress",
        "players": [public_player(p, total) for p in room["players"].values()],
    }


async def finish_game(room):
    if room["state"] != "playing":
        return
    room["state"] = "finished"
    total = len(room["questions"])
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
                    await fail("세션을 찾을 수 없습니다. 새로 입장해 주세요.")
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
                        "total": len(room["questions"]),
                        "questions": sanitize(room["questions"]),
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
                    await fail("이미 방에 있습니다.")
                    continue
                token = secrets.token_hex(8)
                player = Player(token, clean_nickname(msg.get("nickname")),
                                clean_character(msg.get("character")))
                player.ws = ws
                player.connected = True
                code = new_room_code()
                room = {"code": code, "host": token, "players": {token: player},
                        "state": "lobby", "subject": "math", "questions": [],
                        "results": None, "finish_counter": 0}
                rooms[code] = room
                await ws.send_json({"type": "room_created", "room_code": code,
                                    "player_id": token, "token": token})
                await broadcast(room, lobby_msg(room))
                continue

            if mtype == "join_room":
                if player is not None:
                    await fail("이미 방에 있습니다.")
                    continue
                code = (msg.get("room_code") or "").strip().upper()
                target = rooms.get(code)
                if not target:
                    await fail("방을 찾을 수 없습니다.")
                    continue
                if target["state"] != "lobby":
                    await fail("이미 시작된 방입니다.")
                    continue
                if len(target["players"]) >= CONFIG["max_players_per_room"]:
                    await fail("방이 가득 찼습니다.")
                    continue
                token = secrets.token_hex(8)
                player = Player(token, clean_nickname(msg.get("nickname")),
                                clean_character(msg.get("character")))
                player.ws = ws
                player.connected = True
                room = target
                room["players"][token] = player
                await ws.send_json({"type": "joined", "room_code": code,
                                    "player_id": token, "token": token})
                await broadcast(room, lobby_msg(room))
                continue

            if player is None or room is None:
                await fail("먼저 방을 만들거나 입장하세요.")
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
                    await fail("이미지를 읽을 수 없습니다.")
                    continue
                if len(raw) > CONFIG["max_custom_image_bytes"]:
                    await fail("이미지가 너무 큽니다.")
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

            elif mtype == "start_game":
                if room["host"] != player.token:
                    await fail("방장만 시작할 수 있습니다.")
                    continue
                if room["state"] != "lobby":
                    await fail("이미 진행 중인 게임입니다.")
                    continue
                subject = msg.get("subject", "math")
                if subject not in ("math", "en", "ja"):
                    await fail("과목이 올바르지 않습니다.")
                    continue
                total = CONFIG["questions_per_game"]
                questions = build_questions(subject, total)
                if len(questions) < total:
                    await fail("문제가 부족합니다.")
                    continue
                room["subject"] = subject
                room["questions"] = questions
                room["state"] = "playing"
                room["results"] = None
                room["finish_counter"] = 0
                for p in room["players"].values():
                    p.reset()
                await broadcast(room, {
                    "type": "game_started",
                    "subject": subject,
                    "total": len(questions),
                    "questions": sanitize(questions),
                })
                await broadcast(room, progress_msg(room))

            elif mtype == "answer":
                if room["state"] != "playing" or player.finished:
                    continue
                idx = player.progress
                if idx >= len(room["questions"]):
                    continue
                q = room["questions"][idx]
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
                if player.progress >= len(room["questions"]):
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
                    "total": len(room["questions"]),
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
                    await fail("그 아이템이 없습니다.")
                    continue
                if item in OFFENSIVE_ITEMS:
                    target = room["players"].get(msg.get("target_id") or "")
                    if target is None or target is player:
                        await fail("공격할 상대를 고르세요.")
                        continue
                    if target.finished:
                        await fail("이미 완주한 상대입니다.")
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
                            wrong = [i for i in range(len(room["questions"][target.progress]["choices"]))
                                     if i != room["questions"][target.progress]["answer"]]
                            effect["choice_index"] = random.choice(wrong)
                        await send(target, effect)
                        await ws.send_json({"type": "item_used", "item": item,
                                            "target_id": target.token, "blocked": False})
                    await broadcast(room, progress_msg(room))
                elif item == "shield":
                    if player.shield:
                        await fail("이미 실드가 켜져 있습니다.")
                        continue
                    player.inventory.remove(item)
                    player.shield = True
                    await ws.send_json({"type": "item_used", "item": item,
                                        "target_id": player.token, "blocked": False})
                    await broadcast(room, progress_msg(room))
                elif item == "hint":
                    q = room["questions"][player.progress]
                    wrong = [i for i in range(len(q["choices"])) if i != q["answer"]]
                    player.inventory.remove(item)
                    await ws.send_json({"type": "hint", "choice_index": random.choice(wrong),
                                        "question_index": player.progress})
                    await ws.send_json({"type": "item_used", "item": item,
                                        "target_id": player.token, "blocked": False})

            elif mtype == "rematch":
                if room["host"] != player.token:
                    await fail("방장만 다시 시작할 수 있습니다.")
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
