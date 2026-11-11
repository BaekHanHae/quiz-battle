"use strict";

// ------------------------------------------------------------ 캐릭터 (인라인 SVG)
const FACE = (color, inner) =>
  `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;
const EYES = `<circle cx="38" cy="54" r="4.5" fill="#26221f"/><circle cx="62" cy="54" r="4.5" fill="#26221f"/>`;
const MOUTH = `<path d="M44 66 Q50 71 56 66" stroke="#26221f" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;

const PRESETS = [
  { id: "cat", name: "ねこ", svg: FACE("#f7b731",
    `<polygon points="27,36 36,8 50,28" fill="#f7b731"/><polygon points="73,36 64,8 50,28" fill="#f7b731"/>
     <circle cx="50" cy="56" r="32" fill="#f7b731"/>${EYES}${MOUTH}`) },
  { id: "dog", name: "いぬ", svg: FACE("#c98d5e",
    `<ellipse cx="20" cy="46" rx="9" ry="19" fill="#9a6a3e"/><ellipse cx="80" cy="46" rx="9" ry="19" fill="#9a6a3e"/>
     <circle cx="50" cy="56" r="32" fill="#c98d5e"/><ellipse cx="50" cy="66" rx="13" ry="9" fill="#ffffff" opacity="0.5"/>${EYES}${MOUTH}`) },
  { id: "rabbit", name: "うさぎ", svg: FACE("#f2a7c3",
    `<ellipse cx="35" cy="15" rx="7" ry="16" fill="#f2a7c3"/><ellipse cx="65" cy="15" rx="7" ry="16" fill="#f2a7c3"/>
     <ellipse cx="35" cy="16" rx="3.5" ry="10" fill="#ffd9e6"/><ellipse cx="65" cy="16" rx="3.5" ry="10" fill="#ffd9e6"/>
     <circle cx="50" cy="58" r="30" fill="#fdfdfd" stroke="#e5e5e5"/>${EYES}${MOUTH}`) },
  { id: "bear", name: "くま", svg: FACE("#a9744f",
    `<circle cx="26" cy="28" r="11" fill="#a9744f"/><circle cx="74" cy="28" r="11" fill="#a9744f"/>
     <circle cx="26" cy="28" r="5" fill="#7d5433"/><circle cx="74" cy="28" r="5" fill="#7d5433"/>
     <circle cx="50" cy="56" r="32" fill="#a9744f"/><ellipse cx="50" cy="65" rx="12" ry="9" fill="#d9b48c"/>${EYES}${MOUTH}`) },
  { id: "fox", name: "きつね", svg: FACE("#f08a24",
    `<polygon points="24,38 34,4 52,26" fill="#f08a24"/><polygon points="76,38 66,4 48,26" fill="#f08a24"/>
     <circle cx="50" cy="56" r="32" fill="#f08a24"/><path d="M28 68 Q50 92 72 68 Q50 78 28 68" fill="#fff" opacity="0.85"/>${EYES}${MOUTH}`) },
  { id: "panda", name: "パンダ", svg: FACE("#f4f4f4",
    `<circle cx="26" cy="28" r="11" fill="#333"/><circle cx="74" cy="28" r="11" fill="#333"/>
     <circle cx="50" cy="56" r="32" fill="#f7f7f7" stroke="#ddd"/>
     <ellipse cx="38" cy="53" rx="7" ry="10" fill="#333" transform="rotate(-15 38 53)"/>
     <ellipse cx="62" cy="53" rx="7" ry="10" fill="#333" transform="rotate(15 62 53)"/>
     <circle cx="38" cy="52" r="2.6" fill="#fff"/><circle cx="62" cy="52" r="2.6" fill="#fff"/>${MOUTH}`) },
  { id: "frog", name: "かえる", svg: FACE("#58c472",
    `<circle cx="31" cy="27" r="11" fill="#58c472"/><circle cx="69" cy="27" r="11" fill="#58c472"/>
     <circle cx="31" cy="26" r="6.5" fill="#fff"/><circle cx="69" cy="26" r="6.5" fill="#fff"/>
     <circle cx="31" cy="26" r="3.2" fill="#26221f"/><circle cx="69" cy="26" r="3.2" fill="#26221f"/>
     <circle cx="50" cy="58" r="31" fill="#58c472"/>
     <path d="M35 62 Q50 72 65 62" stroke="#26221f" stroke-width="2.5" fill="none" stroke-linecap="round"/>`) },
  { id: "owl", name: "ふくろう", svg: FACE("#8a6fc9",
    `<polygon points="24,30 30,8 44,24" fill="#8a6fc9"/><polygon points="76,30 70,8 56,24" fill="#8a6fc9"/>
     <circle cx="50" cy="55" r="33" fill="#8a6fc9"/>
     <circle cx="38" cy="51" r="9.5" fill="#fff"/><circle cx="62" cy="51" r="9.5" fill="#fff"/>
     <circle cx="38" cy="51" r="4.5" fill="#26221f"/><circle cx="62" cy="51" r="4.5" fill="#26221f"/>
     <polygon points="50,58 43,65 57,65" fill="#f5a623"/>
     <ellipse cx="50" cy="76" rx="14" ry="9" fill="#ffffff" opacity="0.35"/>`) },
];
const PRESET_MAP = Object.fromEntries(PRESETS.map(p => [p.id, p]));

const ITEM_NAMES = { shake: "シェイク", freeze: "フリーズ", hide: "かくす", flip: "さかさま", shield: "シールド", hint: "ヒント" };
const SUBJECT_NAMES = { math: "算数・数学", en: "英語", ja: "国語" };
const LEVEL_NAMES = { shou5: "小学5年", chuu1: "中学1年", ippan: "一般" };
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
    return `<img src="${character.src}" alt="キャラ">`;
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
      if (m.message.includes("セッション")) { localStorage.removeItem("qb_token"); myToken = null; showScreen("join"); }
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
      toast("ゲームスタート！", 1200);
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
        toast("ヒント：まちがいを1つ消したよ");
      }
      break;
    case "item_effect":
      applyEffect(m);
      break;
    case "shield_blocked":
      toast(`${m.from}の攻撃をシールドで防いだ！`);
      sndItem();
      break;
    case "item_used":
      removeFromInventory(m.item);
      if (m.blocked) toast("相手のシールドに防がれた");
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
    $("custom-status").textContent = "写真の準備ができたよ（参加すると反映）";
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
  if (code.length !== 4) { toast("ルームコード4文字を入力してね"); return; }
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
      (p.id === m.host_id ? `<span class="host-tag">ホスト</span>` : "") +
      (p.id === myId ? `<span class="host-tag">自分</span>` : "");
    ul.appendChild(li);
  });
  const amHost = m.host_id === myId;
  // レベルは1人ずつ違う。ホストは各プレイヤーの横で個別に変えられる
  ul.querySelectorAll("li").forEach((li, i) => {
    const p = m.players[i];
    if (amHost) {
      const sel = document.createElement("select");
      sel.className = "player-level";
      sel.innerHTML = Object.entries(LEVEL_NAMES)
        .map(([v, name]) => `<option value="${v}">${name}</option>`).join("");
      sel.value = p.level || "shou5";
      sel.addEventListener("change", () => {
        send({ type: "set_player_level", player_id: p.id, level: sel.value });
      });
      li.appendChild(sel);
    } else {
      const tag = document.createElement("span");
      tag.className = "host-tag";
      tag.textContent = LEVEL_NAMES[p.level] || "";
      li.appendChild(tag);
    }
  });
  $("host-controls").classList.toggle("hidden", !amHost);
  $("wait-text").classList.toggle("hidden", amHost);
  // 科目・レベルはホストの選択を全員に同期する
  if (m.subject) $("subject-select").value = m.subject;
  if (m.level) $("level-select").value = m.level;
  const settingsEl = $("lobby-settings");
  const me = m.players.find(p => p.id === myId);
  settingsEl.textContent = `科目：${SUBJECT_NAMES[m.subject] || ""}　あなたのレベル：${LEVEL_NAMES[(me && me.level) || m.level] || ""}`;
  settingsEl.classList.toggle("hidden", amHost);
}
$("subject-select").addEventListener("change", () => {
  send({ type: "set_subject", subject: $("subject-select").value });
});
$("level-select").addEventListener("change", () => {
  send({ type: "set_level", level: $("level-select").value });
});
$("btn-start").addEventListener("click", () => {
  // レベルはプレイヤーごとにサーバー側で保持しているので、ここでは科目だけ送る
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
      (p.shield ? `<span class="shield-tag">シールド</span>` : "") +
      (p.finished ? `<span class="fin-tag">ゴール</span>` : "") +
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
    $("q-text").textContent = "ゴール！ほかのプレイヤーを待っているよ…";
    $("choices").innerHTML = "";
    return;
  }
  const q = questions[myProgress];
  $("my-progress").textContent = `${myProgress + 1} / ${totalQ} 問題`;
  $("q-text").textContent = q.question;
  const box = $("choices");
  box.innerHTML = "";
  q.choices.forEach((c, i) => {
    const btn = document.createElement("button");
    btn.className = "choice";
    btn.textContent = c;
    btn.onclick = () => {
      if (answeredThis) return;
      if (Date.now() < frozenUntil) { toast("フリーズ中！"); return; }
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
  $("my-score").textContent = `${m.score}点`;
  $("my-streak").textContent = m.streak >= 2 ? `${m.streak}連続正解` : "";
  inventory = m.inventory || inventory;
  if (m.item_gained) { sndItem(); toast(`アイテムゲット：${ITEM_NAMES[m.item_gained]}`); }
  renderInventory();
  setTimeout(() => {
    myProgress = m.progress;
    if (m.finished) {
      $("q-text").textContent = "ゴール！ほかのプレイヤーを待っているよ…";
      $("choices").innerHTML = "";
      $("my-progress").textContent = `${totalQ} / ${totalQ} 問題`;
    } else {
      renderQuestion();
    }
  }, 700);
}

function renderInventory() {
  const box = $("inventory");
  box.innerHTML = "";
  if (!inventory.length) {
    box.innerHTML = `<span class="inv-empty">アイテムはまだないよ（3連続正解で1つ）</span>`;
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
        if (armedItem) toast("攻撃する相手を上でタップしてね");
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
  toast(`${m.from}の${ITEM_NAMES[m.effect]}攻撃！`, 1600);
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
    li.innerHTML = `${avatarHTML(r.character)}<span>${r.rank}位 ${escapeHtml(r.nickname)}</span>` +
      `<span>正解 ${r.correct}/${r.total}</span><span class="r-score">${r.score}点</span>`;
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
      ? data.ranking.map(r => `<li>${escapeHtml(r.player_name)} — ${r.wins}勝 / ${r.games}試合 · 累計${r.total_score}点</li>`).join("")
      : "<li>まだ記録がありません</li>";
  } catch (e) {
    $("ranking-list").innerHTML = "<li>ランキングを読み込めませんでした</li>";
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
