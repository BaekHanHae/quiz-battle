"""quiz-battle 참여자별 레벨 검증 테스트.

호스트(shou5)와 게스트(ippan)에게 서로 다른 레벨을 지정하고 게임을 시작해,
각자 자기 레벨 문제만 받는지 확인한다. 국어(레벨 태그가 있는 문제은행)와
수학(레벨별 생성) 두 과목으로 검증한다.

사용법: python tests/per_level_test.py [base_url]   (기본 http://127.0.0.1:8765)
"""
import asyncio
import json
import sys
from fractions import Fraction
from pathlib import Path

import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
WS_URL = BASE.replace("http", "ws") + "/ws"
DATA = Path(__file__).resolve().parent.parent / "data"


def bank_levels():
    """문제 텍스트 → 레벨 집합 (은행 파일 전체 + 생성 파트)."""
    levels = {}
    for path in [DATA / "questions_ja.json"] + sorted(DATA.glob("questions_ja_gen_*.json")):
        for it in json.loads(path.read_text(encoding="utf-8")):
            q = it.get("question") or it.get("q")
            if q:
                levels.setdefault(q, set()).add(it.get("level", "ippan"))
    return levels


class Client:
    def __init__(self, name):
        self.name = name
        self.queue = asyncio.Queue()

    async def connect(self):
        self.ws = await websockets.connect(WS_URL)
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        try:
            async for raw in self.ws:
                await self.queue.put(json.loads(raw))
        except Exception:
            pass

    async def send(self, obj):
        await self.ws.send(json.dumps(obj))

    async def wait_for(self, mtype, timeout=10, pred=None):
        while True:
            msg = await asyncio.wait_for(self.queue.get(), timeout)
            if msg["type"] == "error":
                raise AssertionError(f"{self.name} 서버 오류: {msg['message']}")
            if msg["type"] == mtype and (pred is None or pred(msg)):
                return msg

    async def close(self):
        self.reader.cancel()
        await self.ws.close()


async def make_room():
    host, guest = Client("호스트"), Client("게스트")
    await host.connect()
    await guest.connect()
    await host.send({"type": "create_room", "nickname": "호스트",
                     "character": {"kind": "preset", "id": "cat"}})
    created = await host.wait_for("room_created")
    await guest.send({"type": "join_room", "room_code": created["room_code"],
                      "nickname": "게스트", "character": {"kind": "preset", "id": "dog"}})
    joined = await guest.wait_for("joined")
    await host.wait_for("lobby_update", pred=lambda m: len(m["players"]) == 2)
    return host, guest, created["player_id"], joined["player_id"]


async def main():
    levels = bank_levels()

    # --- 시나리오 1: 국어, 호스트 shou5 / 게스트 ippan ---
    host, guest, host_id, guest_id = await make_room()
    await host.send({"type": "set_player_level", "player_id": guest_id, "level": "ippan"})
    lobby = await host.wait_for(
        "lobby_update",
        pred=lambda m: {p["id"]: p["level"] for p in m["players"]}.get(guest_id) == "ippan")
    by_id = {p["id"]: p["level"] for p in lobby["players"]}
    assert by_id[host_id] == "shou5" and by_id[guest_id] == "ippan", by_id
    print("PASS 로비 레벨 지정: 호스트 shou5 / 게스트 ippan")

    await host.send({"type": "start_game", "subject": "ja"})
    g_host = await host.wait_for("game_started")
    g_guest = await guest.wait_for("game_started")
    assert g_host["level"] == "shou5" and g_guest["level"] == "ippan", (g_host["level"], g_guest["level"])
    for q in g_host["questions"]:
        assert "shou5" in levels.get(q["question"], set()), f"호스트에게 shou5 아닌 문제: {q['question']}"
    for q in g_guest["questions"]:
        assert levels.get(q["question"], set()) == {"ippan"}, f"게스트에게 ippan 아닌 문제: {q['question']}"
    host_texts = {q["question"] for q in g_host["questions"]}
    guest_texts = {q["question"] for q in g_guest["questions"]}
    assert host_texts.isdisjoint(guest_texts), "레벨이 다른데 문제 세트가 겹침"
    print("PASS 국어 출제: 호스트 20문제 전부 shou5, 게스트 20문제 전부 ippan, 겹침 없음")
    await host.close()
    await guest.close()

    # --- 시나리오 2: 수학, 호스트 chuu1 / 게스트 shou5 (shou5는 음수 없음) ---
    host, guest, host_id, guest_id = await make_room()
    await host.send({"type": "set_player_level", "player_id": host_id, "level": "chuu1"})
    await host.wait_for(
        "lobby_update",
        pred=lambda m: {p["id"]: p["level"] for p in m["players"]}.get(host_id) == "chuu1")
    await host.send({"type": "start_game", "subject": "math"})
    g_host = await host.wait_for("game_started")
    g_guest = await guest.wait_for("game_started")
    assert g_host["level"] == "chuu1" and g_guest["level"] == "shou5"
    for q in g_guest["questions"]:
        expr = q["question"].replace("= ?", "").strip()
        a_s, op, b_s = expr.split()
        a, b = Fraction(a_s), Fraction(b_s)
        assert a >= 0 and b >= 0, f"shou5에 음수 피연산자: {q['question']}"
        if op == "-":
            assert a - b >= 0, f"shou5에 음수 결과: {q['question']}"
        for c in q["choices"]:
            assert Fraction(c) >= 0, f"shou5에 음수 선택지: {q['question']} / {c}"
    print("PASS 수학 출제: 게스트(shou5) 20문제 전부 음수 없음, 호스트는 chuu1 세트 수신")
    await host.close()
    await guest.close()

    print("PER-LEVEL TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
