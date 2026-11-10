"use strict";

// ------------------------------------------------------------ 캐릭터 (인라인 SVG)
const FACE = (color, inner) =>
  `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;
const EYES = `<circle cx="38" cy="54" r="4.5" fill="#26221f"/><circle cx="62" cy="54" r="4.5" fill="#26221f"/>`;
const MOUTH = `<path d="M44 66 Q50 71 56 66" stroke="#26221f" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;

const PRESETS = [
  { id: "cat", name: "고양이", svg: FACE("#f7b731",
    `<polygon points="27,36 36,8 50,28" fill="#f7b731"/><polygon points="73,36 64,8 50,28" fill="#f7b731"/>
     <circle cx="50" cy="56" r="32" fill="#f7b731"/>${EYES}${MOUTH}`) },
  { id: "dog", name: "강아지", svg: FACE("#c98d5e",
    `<ellipse cx="20" cy="46" rx="9" ry="19" fill="#9a6a3e"/><ellipse cx="80" cy="46" rx="9" ry="19" fill="#9a6a3e"/>
     <circle cx="50" cy="56" r="32" fill="#c98d5e"/><ellipse cx="50" cy="66" rx="13" ry="9" fill="#ffffff" opacity="0.5"/>${EYES}${MOUTH}`) },
  { id: "rabbit", name: "토끼", svg: FACE("#f2a7c3",
    `<ellipse cx="35" cy="15" rx="7" ry="16" fill="#f2a7c3"/><ellipse cx="65" cy="15" rx="7" ry="16" fill="#f2a7c3"/>
     <ellipse cx="35" cy="16" rx="3.5" ry="10" fill="#ffd9e6"/><ellipse cx="65" cy="16" rx="3.5" ry="10" fill="#ffd9e6"/>
     <circle cx="50" cy="58" r="30" fill="#fdfdfd" stroke="#e5e5e5"/>${EYES}${MOUTH}`) },
  { id: "bear", name: "곰", svg: FACE("#a9744f",
    `<circle cx="26" cy="28" r="11" fill="#a9744f"/><circle cx="74" cy="28" r="11" fill="#a9744f"/>
     <circle cx="26" cy="28" r="5" fill="#7d5433"/><circle cx="74" cy="28" r="5" fill="#7d5433"/>
     <circle cx="50" cy="56" r="32" fill="#a9744f"/><ellipse cx="50" cy="65" rx="12" ry="9" fill="#d9b48c"/>${EYES}${MOUTH}`) },
  { id: "fox", name: "여우", svg: FACE("#f08a24",
    `<polygon points="24,38 34,4 52,26" fill="#f08a24"/><polygon points="76,38 66,4 48,26" fill="#f08a24"/>
     <circle cx="50" cy="56" r="32" fill="#f08a24"/><path d="M28 68 Q50 92 72 68 Q50 78 28 68" fill="#fff" opacity="0.85"/>${EYES}${MOUTH}`) },
  { id: "panda", name: "판다", svg: FACE("#f4f4f4",
    `<circle cx="26" cy="28" r="11" fill="#333"/><circle cx="74" cy="28" r="11" fill="#333"/>
     <circle cx="50" cy="56" r="32" fill="#f7f7f7" stroke="#ddd"/>
     <ellipse cx="38" cy="53" rx="7" ry="10" fill="#333" transform="rotate(-15 38 53)"/>
     <ellipse cx="62" cy="53" rx="7" ry="10" fill="#333" transform="rotate(15 62 53)"/>
     <circle cx="38" cy="52" r="2.6" fill="#fff"/><circle cx="62" cy="52" r="2.6" fill="#fff"/>${MOUTH}`) },
  { id: "frog", name: "개구리", svg: FACE("#58c472",
    `<circle cx="31" cy="27" r="11" fill="#58c472"/><circle cx="69" cy="27" r="11" fill="#58c472"/>
     <circle cx="31" cy="26" r="6.5" fill="#fff"/><circle cx="69" cy="26" r="6.5" fill="#fff"/>
     <circle cx="31" cy="26" r="3.2" fill="#26221f"/><circle cx="69" cy="26" r="3.2" fill="#26221f"/>
     <circle cx="50" cy="58" r="31" fill="#58c472"/>
     <path d="M35 62 Q50 72 65 62" stroke="#26221f" stroke-width="2.5" fill="none" stroke-linecap="round"/>`) },
  { id: "owl", name: "부엉이", svg: FACE("#8a6fc9",
    `<polygon points="24,30 30,8 44,24" fill="#8a6fc9"/><polygon points="76,30 70,8 56,24" fill="#8a6fc9"/>
     <circle cx="50" cy="55" r="33" fill="#8a6fc9"/>
     <circle cx="38" cy="51" r="9.5" fill="#fff"/><circle cx="62" cy="51" r="9.5" fill="#fff"/>
     <circle cx="38" cy="51" r="4.5" fill="#26221f"/><circle cx="62" cy="51" r="4.5" fill="#26221f"/>
     <polygon points="50,58 43,65 57,65" fill="#f5a623"/>
     <ellipse cx="50" cy="76" rx="14" ry="9" fill="#ffffff" opacity="0.35"/>`) },
];
const PRESET_MAP = Object.fromEntries(PRESETS.map(p => [p.id, p]));

const ITEM_NAMES = { shake: "흔들기", freeze: "동결", hide: "가리기", flip: "뒤집기", shield: "실드", hint: "힌트" };
const OFFENSIVE = ["shake", "freeze", "hide", "flip"];

// ------------------------------------------------------------ 상태
let ws = null, wsReady = null;
let myToken = localStorage.getItem("qb_token") || null;
let myId = null, myRoom = null, isHost = false;
let myCharacter = { kind: "preset", id: "cat" };
let pendingCustomImage = null; // dataURL (입장 직후 업로드)
let questions = [], myProgress = 0, totalQ = 20;
let inventory = [], armedItem = null;
let answeredThis = false, pendingChoice = null;
let frozenUntil = 0;
let playersCache = [];

// ------------------------------------------------------------ 사운드 (WebAudio)
let audioCtx = null;
function ensureAudio() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { /* 무시 */ }
  }
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
}
document.addEventListener("pointerdown", ensureAudio, { once: false });
function beep(freq, dur = 0.12, type = "sine", delay = 0) {
  if (!audioCtx) return;
  const t0 = audioCtx.currentTime + delay;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type; osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.15, t0);
  gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
  osc.connect(gain).connect(audioCtx.destination);
  osc.start(t0); osc.stop(t0 + dur + 0.02);
}
const sndCorrect = () => { beep(660, 0.1); beep(880, 0.14, "sine", 0.09); };
const sndWrong = () => beep(170, 0.22, "sawtooth");
const sndHit = () => { beep(120, 0.25, "square"); beep(90, 0.3, "square", 0.05); };
const sndItem = () => beep(1250, 0.1, "triangle");

// ------------------------------------------------------------ 유틸
const $ = id => document.getElementById(id);
function showScreen(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  $("screen-" + name).classList.add("active");
}
let toastTimer = null;
function toast(text, ms = 2200) {
  const el = $("toast");
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), ms);
}
function avatarHTML(character) {
  if (character && character.kind === "custom" && character.src) {
    return `<img src="${character.src}" alt="캐릭터">`;
  }
  const id = character && character.id ? character.id : "cat";
  return (PRESET_MAP[id] || PRESET_MAP.cat).svg;
}

// ------------------------------------------------------------ WebSocket
function connect() {
  if (wsReady) return wsReady;
  wsReady = new Promise(resolve => {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onopen = () => {
      if (myToken) send({ type: "rejoin", token: myToken });
      resolve();
    };
    ws.onmessage = ev => handleMessage(JSON.parse(ev.data));
    ws.onclose = () => { wsReady = null; ws = null; };
  });
  return wsReady;
}
function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }

function handleMessage(m) {
  switch (m.type) {
    case "error":
      toast(m.message);
      if (m.message.includes("세션")) { localStorage.removeItem("qb_token"); myToken = null; showScreen("join"); }
      break;
    case "room_created":
    case "joined":
      myToken = m.token; myId = m.player_id; myRoom = m.room_code;
      isHost = m.type === "room_created";
      localStorage.setItem("qb_token", myToken);
      localStorage.setItem("qb_room", myRoom);
      if (pendingCustomImage) { send({ type: "upload_character", image: pendingCustomImage }); }
      showScreen("lobby");
      break;
    case "rejoined":
      myId = m.player_id; myRoom = m.room_code; isHost = m.is_host;
      if (m.state === "lobby") showScreen("lobby");
      break;
    case "lobby_update":
      playersCache = m.players;
      renderLobby(m);
      if (m.state === "lobby") showScreen("lobby");
      break;
    case "character_updated":
      myCharacter = m.character;
      break;
    case "game_started":
      questions = m.questions; totalQ = m.total; myProgress = 0;
      inventory = []; armedItem = null;
      showScreen("game");
      renderQuestion();
      toast("게임 시작!", 1200);
      break;
    case "game_state": // 재접속 복원
      questions = m.questions; totalQ = m.total;
      myProgress = m.you.progress; inventory = m.you.inventory || [];
      showScreen("game");
      renderInventory(); renderQuestion(true);
      break;
    case "progress":
      playersCache = m.players;
      renderPlayersBar(m.players);
      break;
    case "answer_result":
      onAnswerResult(m);
      break;
    case "hint":
      if (m.question_index === myProgress) {
        const btns = document.querySelectorAll(".choice");
        if (btns[m.choice_index]) btns[m.choice_index].classList.add("hint-off");
        toast("힌트: 오답 하나를 지웠어요");
      }
      break;
    case "item_effect":
      applyEffect(m);
      break;
    case "shield_blocked":
      toast(`${m.from}의 공격을 실드로 막았어요!`);
      sndItem();
      break;
    case "item_used":
      removeFromInventory(m.item);
      if (m.blocked) toast("상대의 실드에 막혔어요");
      break;
    case "game_over":
      renderResults(m.results);
      showScreen("result");
      break;
  }
}

// ------------------------------------------------------------ 입장 화면
function renderCharGrid() {
  const grid = $("char-grid");
  grid.innerHTML = "";
  PRESETS.forEach(p => {
    const cell = document.createElement("div");
    cell.className = "char-cell" + (myCharacter.kind === "preset" && myCharacter.id === p.id ? " selected" : "");
    cell.innerHTML = p.svg + `<span class="char-name">${p.name}</span>`;
    cell.onclick = () => {
      myCharacter = { kind: "preset", id: p.id };
      pendingCustomImage = null;
      $("custom-status").textContent = "";
      renderCharGrid();
    };
    grid.appendChild(cell);
  });
}

$("photo-input").addEventListener("change", ev => {
  const file = ev.target.files[0];
  if (!file) return;
  const img = new Image();
  img.onload = () => {
    const size = 256;
    const canvas = document.createElement("canvas");
    canvas.width = size; canvas.height = size;
    const ctx = canvas.getContext("2d");
    const side = Math.min(img.width, img.height);
    ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
    pendingCustomImage = canvas.toDataURL("image/jpeg", 0.85);
    myCharacter = { kind: "preset", id: myCharacter.id }; // 서버에는 업로드 후 custom으로 교체됨
    $("custom-status").textContent = "사진 준비됨 (입장하면 적용)";
    URL.revokeObjectURL(img.src);
  };
  img.src = URL.createObjectURL(file);
});

$("btn-create").addEventListener("click", async () => {
  ensureAudio();
  await connect();
  send({ type: "create_room", nickname: $("nickname").value, character: myCharacter });
});
$("btn-join").addEventListener("click", async () => {
  ensureAudio();
  const code = $("room-code").value.trim().toUpperCase();
  if (code.length !== 4) { toast("방 코드 4자를 입력하세요"); return; }
  await connect();
  send({ type: "join_room", room_code: code, nickname: $("nickname").value, character: myCharacter });
});
$("btn-session-reset").addEventListener("click", () => {
  localStorage.removeItem("qb_token"); localStorage.removeItem("qb_room");
  myToken = null; location.reload();
});

// ------------------------------------------------------------ 대기실
function renderLobby(m) {
  $("lobby-code").textContent = m.room_code;
  const ul = $("lobby-players");
  ul.innerHTML = "";
  m.players.forEach(p => {
    const li = document.createElement("li");
    if (!p.connected) li.className = "off";
    li.innerHTML = `${avatarHTML(p.character)}<span>${escapeHtml(p.nickname)}</span>` +
      (p.id === m.host_id ? `<span class="host-tag">방장</span>` : "") +
      (p.id === myId ? `<span class="host-tag">나</span>` : "");
    ul.appendChild(li);
  });
  const amHost = m.host_id === myId;
  $("host-controls").classList.toggle("hidden", !amHost);
  $("wait-text").classList.toggle("hidden", amHost);
}
$("btn-start").addEventListener("click", () => {
  send({ type: "start_game", subject: $("subject-select").value });
});

// ------------------------------------------------------------ 게임 화면
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderPlayersBar(players) {
  const bar = $("players-bar");
  bar.innerHTML = "";
  players.forEach(p => {
    const row = document.createElement("div");
    row.className = "pbar" + (p.id === myId ? " me" : "");
    if (armedItem && p.id !== myId && !p.finished) row.classList.add("targetable");
    const pct = Math.min(100, (p.progress / (p.total || totalQ)) * 100);
    row.innerHTML = `${avatarHTML(p.character)}<span class="pname">${escapeHtml(p.nickname)}</span>` +
      `<span class="track"><span class="fill" style="width:${pct}%"></span></span>` +
      (p.shield ? `<span class="shield-tag">실드</span>` : "") +
      (p.finished ? `<span class="fin-tag">완주</span>` : "") +
      `<span class="pscore">${p.score}</span>`;
    row.onclick = () => {
      if (armedItem && p.id !== myId && !p.finished) {
        send({ type: "use_item", item: armedItem, target_id: p.id });
        armedItem = null;
        renderInventory(); renderPlayersBar(playersCache);
      }
    };
    bar.appendChild(row);
  });
}

function renderQuestion(restored = false) {
  answeredThis = false; pendingChoice = null;
  if (myProgress >= questions.length) {
    $("q-text").textContent = "완주! 다른 플레이어를 기다리는 중…";
    $("choices").innerHTML = "";
    return;
  }
  const q = questions[myProgress];
  $("my-progress").textContent = `${myProgress + 1} / ${totalQ} 문제`;
  $("q-text").textContent = q.question;
  const box = $("choices");
  box.innerHTML = "";
  q.choices.forEach((c, i) => {
    const btn = document.createElement("button");
    btn.className = "choice";
    btn.textContent = c;
    btn.onclick = () => {
      if (answeredThis) return;
      if (Date.now() < frozenUntil) { toast("동결 중!"); return; }
      answeredThis = true; pendingChoice = i;
      send({ type: "answer", choice: i });
    };
    box.appendChild(btn);
  });
  if (!restored) renderInventory();
}

function onAnswerResult(m) {
  const btns = document.querySelectorAll(".choice");
  if (pendingChoice !== null && btns[pendingChoice]) {
    btns[pendingChoice].classList.add(m.correct ? "correct" : "wrong");
  }
  if (!m.correct && btns[m.correct_index]) btns[m.correct_index].classList.add("correct");
  if (m.correct) { sndCorrect(); document.body.classList.add("flash-correct"); setTimeout(() => document.body.classList.remove("flash-correct"), 420); }
  else sndWrong();
  $("my-score").textContent = `${m.score}점`;
  $("my-streak").textContent = m.streak >= 2 ? `${m.streak}연속 정답` : "";
  inventory = m.inventory || inventory;
  if (m.item_gained) { sndItem(); toast(`아이템 획득: ${ITEM_NAMES[m.item_gained]}`); }
  renderInventory();
  setTimeout(() => {
    myProgress = m.progress;
    if (m.finished) {
      $("q-text").textContent = "완주! 다른 플레이어를 기다리는 중…";
      $("choices").innerHTML = "";
      $("my-progress").textContent = `${totalQ} / ${totalQ} 문제`;
    } else {
      renderQuestion();
    }
  }, 700);
}

function renderInventory() {
  const box = $("inventory");
  box.innerHTML = "";
  if (!inventory.length) {
    box.innerHTML = `<span class="inv-empty">아직 아이템 없음 (3연속 정답마다 1개)</span>`;
    return;
  }
  const counts = {};
  inventory.forEach(it => counts[it] = (counts[it] || 0) + 1);
  Object.keys(counts).forEach(it => {
    const chip = document.createElement("button");
    chip.className = "item-chip" + (armedItem === it ? " armed" : "");
    chip.textContent = `${ITEM_NAMES[it]} ×${counts[it]}`;
    chip.onclick = () => {
      if (OFFENSIVE.includes(it)) {
        armedItem = armedItem === it ? null : it;
        if (armedItem) toast("공격할 상대를 위에서 탭하세요");
        renderInventory(); renderPlayersBar(playersCache);
      } else {
        send({ type: "use_item", item: it, target_id: myId });
      }
    };
    box.appendChild(chip);
  });
}
function removeFromInventory(item) {
  const i = inventory.indexOf(item);
  if (i >= 0) inventory.splice(i, 1);
  renderInventory();
}

function applyEffect(m) {
  sndHit();
  document.body.classList.add("hit-flash");
  setTimeout(() => document.body.classList.remove("hit-flash"), 480);
  toast(`${m.from}의 ${ITEM_NAMES[m.effect]} 공격!`, 1600);
  const dur = m.duration_ms || 3000;
  if (m.effect === "shake") {
    document.body.classList.add("shaking");
    setTimeout(() => document.body.classList.remove("shaking"), dur);
  } else if (m.effect === "flip") {
    $("flip-wrap").classList.add("flipped");
    setTimeout(() => $("flip-wrap").classList.remove("flipped"), dur);
  } else if (m.effect === "freeze") {
    frozenUntil = Date.now() + dur;
    $("freeze-overlay").classList.remove("hidden");
    setTimeout(() => $("freeze-overlay").classList.add("hidden"), dur);
  } else if (m.effect === "hide") {
    if (m.question_index === myProgress) {
      const btns = document.querySelectorAll(".choice");
      if (btns[m.choice_index]) {
        btns[m.choice_index].classList.add("hidden-choice");
        setTimeout(() => btns[m.choice_index] && btns[m.choice_index].classList.remove("hidden-choice"), dur);
      }
    }
  }
}

// ------------------------------------------------------------ 결과/랭킹
function renderResults(results) {
  const ol = $("result-list");
  ol.innerHTML = "";
  results.forEach(r => {
    const li = document.createElement("li");
    if (r.winner) li.className = "winner";
    li.innerHTML = `${avatarHTML(r.character)}<span>${r.rank}위 ${escapeHtml(r.nickname)}</span>` +
      `<span>정답 ${r.correct}/${r.total}</span><span class="r-score">${r.score}점</span>`;
    ol.appendChild(li);
  });
  $("btn-rematch").classList.toggle("hidden", !isHost);
  $("rematch-wait").classList.toggle("hidden", isHost);
}
$("btn-rematch").addEventListener("click", () => send({ type: "rematch" }));

async function showRanking() {
  try {
    const res = await fetch("/api/ranking");
    const data = await res.json();
    const ol = $("ranking-list");
    ol.innerHTML = data.ranking.length
      ? data.ranking.map(r => `<li>${escapeHtml(r.player_name)} — ${r.wins}승 / ${r.games}판 · 누적 ${r.total_score}점</li>`).join("")
      : "<li>아직 기록이 없습니다</li>";
  } catch (e) {
    $("ranking-list").innerHTML = "<li>랭킹을 불러오지 못했습니다</li>";
  }
  $("ranking-modal").classList.remove("hidden");
}
$("btn-ranking").addEventListener("click", showRanking);
$("btn-result-ranking").addEventListener("click", showRanking);
$("btn-ranking-close").addEventListener("click", () => $("ranking-modal").classList.add("hidden"));

// ------------------------------------------------------------ 초기화
$("join-url").textContent = location.origin + "/";
if (myToken) {
  $("btn-session-reset").classList.remove("hidden");
  connect(); // 저장된 세션으로 재접속 시도
}
renderCharGrid();
