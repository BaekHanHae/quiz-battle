"""quiz-battle 게임 중 조작 검증: 일시정지/재개, 기권, 즉시 종료, 퇴장·호스트 승계.

사용법: python tests/controls_test.py [base_url]   (기본 http://127.0.0.1:8765)
"""
import asyncio
import json
import sys
from fractions import Fraction

import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
WS_URL = BASE.replace("http", "ws") + "/ws"


def solve(question_text, choices):
    expr = question_text.replace("= ?", "").strip()
    a_s, op, b_s = expr.split()
    a, b = Fraction(a_s), Fraction(b_s)
    val = {"+": a + b, "-": a - b, "×": a * b, "÷": a / b}[op]
    for i, c in enumerate(choices):
        if Fraction(c) == val:
            return i
    raise AssertionError(f"정답을 찾지 못함: {question_text} / {choices}")


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


async def make_room(names=("호스트", "게스트")):
    clients = []
    for i, name in enumerate(names):
        c = Client(name)
        await c.connect()
        clients.append(c)
    host = clients[0]
    await host.send({"type": "create_room", "nickname": names[0],
                     "character": {"kind": "preset", "id": "cat"}})
    created = await host.wait_for("room_created")
    ids = [created["player_id"]]
    for c, name in zip(clients[1:], names[1:]):
        await c.send({"type": "join_room", "room_code": created["room_code"],
                      "nickname": name, "character": {"kind": "preset", "id": "dog"}})
        joined = await c.wait_for("joined")
        ids.append(joined["player_id"])
    await host.wait_for("lobby_update", pred=lambda m: len(m["players"]) == len(names))
    return clients, created["room_code"], ids


async def start_math(clients):
    await clients[0].send({"type": "start_game", "subject": "math"})
    return [await c.wait_for("game_started") for c in clients]


async def answer(client, started, idx, correct=True):
    q = started["questions"][idx]
    choice = solve(q["question"], q["choices"])
    if not correct:
        choice = (choice + 1) % len(q["choices"])
    await client.send({"type": "answer", "choice": choice})
    return await client.wait_for("answer_result")


async def scenario_pause_forfeit():
    (host, guest), code, (host_id, guest_id) = await make_room()
    g_host, g_guest = await start_math([host, guest])

    # 게스트가 3문제를 맞혀 점수를 쌓는다
    for i in range(3):
        await answer(guest, g_guest, i)
    # 호스트가 일시정지 → 게스트의 답변은 무시돼야 한다
    await host.send({"type": "pause_game"})
    await guest.wait_for("paused")
    q = g_guest["questions"][3]
    await guest.send({"type": "answer", "choice": solve(q["question"], q["choices"])})
    await asyncio.sleep(0.6)
    assert guest.queue.empty() or all(
        m["type"] != "answer_result" for m in list(guest.queue._queue)), \
        "일시정지 중 답변이 처리됐다"
    print("PASS 일시정지: 진행 중 답변이 무시됨")
    # 재개 후 같은 문제에 답하면 progress=4 (3+1) 여야 한다
    await host.send({"type": "resume_game"})
    await guest.wait_for("resumed")
    res = await answer(guest, g_guest, 3)
    assert res["progress"] == 4, res
    print("PASS 재개: 답변 처리 재개, progress 정확")

    # 게스트 기권 → 점수가 높아도 완주자(호스트)보다 뒤 순위
    await guest.send({"type": "forfeit"})
    await guest.wait_for("forfeited")
    for i in range(20):
        last = await answer(host, g_host, i, correct=False)  # 호스트는 전부 오답(0점)으로 완주
    over = await host.wait_for("game_over")
    results = over["results"]
    assert results[0]["nickname"] == "호스트" and results[0]["score"] == 0, results
    assert results[1]["nickname"] == "게스트" and results[1]["forfeited"] is True, results
    assert results[1]["score"] > 0, results
    print(f"PASS 기권: 점수 {results[1]['score']}점이어도 리타이어로 2위, 승자는 완주자")
    await host.close()
    await guest.close()


async def scenario_end_and_leave():
    (host, guest), code, (host_id, guest_id) = await make_room()
    g_host, g_guest = await start_math([host, guest])
    await answer(host, g_host, 0)
    # 호스트가 즉시 종료 → 현재 점수로 결과
    await host.send({"type": "end_game"})
    over = await guest.wait_for("game_over")
    assert len(over["results"]) == 2 and over["results"][0]["nickname"] == "호스트", over["results"]
    print("PASS 즉시 종료: 현재 점수로 결과 확정")
    await host.close()
    await guest.close()

    # 로비 퇴장 + 호스트 승계
    (h2, g2, g3), code2, ids2 = await make_room(("방장", "둘째", "셋째"))
    await g2.send({"type": "leave_room"})
    await g2.wait_for("left")
    lobby = await h2.wait_for("lobby_update", pred=lambda m: len(m["players"]) == 2)
    assert {p["nickname"] for p in lobby["players"]} == {"방장", "셋째"}
    print("PASS 로비 퇴장: 방에서 제거됨")
    await h2.send({"type": "leave_room"})
    await h2.wait_for("left")
    lobby3 = await g3.wait_for("lobby_update", pred=lambda m: m["host_id"] == ids2[2])
    assert lobby3["host_id"] == ids2[2], lobby3
    print("PASS 호스트 승계: 방장이 나가면 다음 사람이 호스트")
    for c in (h2, g2, g3):
        await c.close()


async def main():
    await scenario_pause_forfeit()
    await scenario_end_and_leave()
    print("CONTROLS TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
