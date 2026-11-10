"""quiz-battle 스모크 테스트.

실행 중인 서버에 WebSocket으로 호스트+게스트 2명이 접속해 방 생성/입장 →
동시 시작 → 수학 문제를 계산해 정답 제출 → 아이템 획득/사용 → 완주 →
결과와 누적 랭킹 저장까지 확인한다.

사용법: python tests/smoke_test.py [base_url]   (기본 http://127.0.0.1:8765)
"""
import asyncio
import json
import sys
import urllib.request
from fractions import Fraction

import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
WS_URL = BASE.replace("http", "ws") + "/ws"
OFFENSIVE = {"shake", "freeze", "hide", "flip"}


def solve(question_text, choices):
    """'12 + 7 = ?' / '1/2 + 1/4 = ?' 형태의 수학 문제를 정확히 계산해 정답 선택지 인덱스를 찾는다."""
    expr = question_text.replace("= ?", "").strip()
    a_s, op, b_s = expr.split()
    a, b = Fraction(a_s), Fraction(b_s)
    val = {"+": a + b, "-": a - b, "×": a * b, "÷": a / b}[op]
    for i, c in enumerate(choices):
        if Fraction(c) == val:
            return i
    raise AssertionError(f"정답을 찾지 못함: {question_text} / {choices} / 계산값 {val}")


class Client:
    def __init__(self, name):
        self.name = name
        self.queue = asyncio.Queue()
        self.ws = None

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
        seen = []
        while True:
            msg = await asyncio.wait_for(self.queue.get(), timeout)
            seen.append(msg["type"])
            if msg["type"] == "error":
                raise AssertionError(f"{self.name} 서버 오류: {msg['message']} (기다린 것: {mtype}, 받은 것: {seen})")
            if msg["type"] == mtype and (pred is None or pred(msg)):
                return msg

    async def close(self):
        self.reader.cancel()
        await self.ws.close()


async def main():
    host = Client("호스트")
    guest = Client("게스트")
    await host.connect()
    await guest.connect()

    # 1) 방 생성/입장
    await host.send({"type": "create_room", "nickname": "호스트",
                     "character": {"kind": "preset", "id": "cat"}})
    created = await host.wait_for("room_created")
    code = created["room_code"]
    assert len(code) == 4, code
    print(f"PASS 방 생성: 코드 {code}")

    await guest.send({"type": "join_room", "room_code": code, "nickname": "게스트",
                      "character": {"kind": "preset", "id": "dog"}})
    joined = await guest.wait_for("joined")
    host_id = created["player_id"]
    guest_id = joined["player_id"]
    lobby = await host.wait_for("lobby_update", pred=lambda m: len(m["players"]) == 2)
    assert len(lobby["players"]) == 2, lobby["players"]
    print("PASS 게스트 입장: 대기실 2명 확인")

    # 2) 동시 시작 (수학)
    await host.send({"type": "start_game", "subject": "math"})
    g_host = await host.wait_for("game_started")
    g_guest = await guest.wait_for("game_started")
    assert g_guest["total"] == 20 and len(g_guest["questions"]) == 20
    questions = g_guest["questions"]
    print("PASS 동시 시작: 20문제 수신")

    async def answer_one(client, idx, questions_):
        q = questions_[idx]
        choice = solve(q["question"], q["choices"])
        await client.send({"type": "answer", "choice": choice})
        res = await client.wait_for("answer_result")
        assert res["correct"], f"{client.name} {idx + 1}번 오답 판정: {q}"
        return res

    # 3) 게스트가 정답을 쌓아 아이템을 얻고, 공격 아이템이 나오면 호스트에게 사용
    guest_progress = 0
    item_used_effect = None
    first_gain_at = None
    while guest_progress < 20 and item_used_effect is None:
        res = await answer_one(guest, guest_progress, questions)
        guest_progress += 1
        if res["item_gained"] and first_gain_at is None:
            first_gain_at = guest_progress
        inv = res["inventory"]
        offensive = [i for i in inv if i in OFFENSIVE]
        if offensive:
            await guest.send({"type": "use_item", "item": offensive[0], "target_id": host_id})
            effect = await host.wait_for("item_effect")
            assert effect["effect"] in OFFENSIVE, effect
            item_used_effect = effect["effect"]
            print(f"PASS 아이템 사용: {offensive[0]} → 호스트가 효과 수신 ({item_used_effect})")
    assert first_gain_at == 3, f"첫 아이템은 3연속 정답에서 나와야 함 (실제: {first_gain_at})"
    print("PASS 아이템 획득: 3연속 정답에서 첫 아이템")
    assert item_used_effect is not None, "20문제 안에 공격 아이템을 얻지 못함"

    # 4) 남은 문제 완주 (게스트 → 호스트)
    last_guest_res = res
    while guest_progress < 20:
        last_guest_res = await answer_one(guest, guest_progress, questions)
        guest_progress += 1
    assert last_guest_res["finished"], "게스트 완주 플래그 없음"
    print(f"PASS 게스트 완주: 점수 {last_guest_res['score']}")

    host_questions = g_host["questions"]
    last_host_res = None
    for idx in range(20):
        last_host_res = await answer_one(host, idx, host_questions)
    assert last_host_res["finished"]
    print(f"PASS 호스트 완주: 점수 {last_host_res['score']}")

    # 5) 결과 화면 데이터
    over_guest = await guest.wait_for("game_over")
    over_host = await host.wait_for("game_over")
    results = over_guest["results"]
    assert len(results) == 2, results
    guest_row = [r for r in results if r["nickname"] == "게스트"][0]
    assert guest_row["correct"] == 20, guest_row
    assert results[0]["score"] >= results[1]["score"], "결과 정렬 오류"
    print(f"PASS 게임 결과: 1위 {results[0]['nickname']} {results[0]['score']}점, "
          f"게스트 정답 {guest_row['correct']}/20")

    await guest.close()
    await host.close()

    # 6) 누적 랭킹 저장 확인 (SQLite 기반 엔드포인트)
    with urllib.request.urlopen(BASE + "/api/ranking", timeout=5) as resp:
        ranking = json.loads(resp.read().decode("utf-8"))["ranking"]
    names = {r["player_name"]: r for r in ranking}
    assert "게스트" in names and "호스트" in names, ranking
    assert names["게스트"]["games"] >= 1 and names["게스트"]["total_score"] > 0
    wins = names["게스트"]["wins"] + names["호스트"]["wins"]
    assert wins >= 1, ranking
    print(f"PASS 누적 랭킹 저장: {ranking}")

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
