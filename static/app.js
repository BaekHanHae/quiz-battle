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

// ------------------------------------------------------------ 사운드 (WebAudio 합성)
// 음원 파일 없이 코드로 소리를 만든다. 마스터 게인 하나로 전체 음소거를 건다.
let audioCtx = null, masterGain = null;
let soundOn = localStorage.getItem("qb_sound") !== "off";
function ensureAudio() {
  if (!audioCtx) {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      masterGain = audioCtx.createGain();
      masterGain.gain.value = soundOn ? 1 : 0;
      masterGain.connect(audioCtx.destination);
    } catch (e) { /* 무시 */ }
  }
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
}
document.addEventListener("pointerdown", ensureAudio, { once: false });
function beep(freq, dur = 0.12, type = "sine", delay = 0, vol = 0.15) {
  if (!audioCtx || !soundOn) return;
  const t0 = audioCtx.currentTime + delay;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type; osc.frequency.value = freq;
  gain.gain.setValueAtTime(vol, t0);
  gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
  osc.connect(gain).connect(masterGain);
  osc.start(t0); osc.stop(t0 + dur + 0.02);
}
function sweep(from, to, dur = 0.25, type = "sine", delay = 0, vol = 0.15) {
  if (!audioCtx || !soundOn) return;
  const t0 = audioCtx.currentTime + delay;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(from, t0);
  osc.frequency.exponentialRampToValueAtTime(Math.max(to, 1), t0 + dur);
  gain.gain.setValueAtTime(vol, t0);
  gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
  osc.connect(gain).connect(masterGain);
  osc.start(t0); osc.stop(t0 + dur + 0.02);
}
// 정답: 콤보가 쌓일수록 음정이 반음씩 올라간다
const sndCorrect = (streak = 1) => {
  const shift = Math.pow(2, Math.min(streak - 1, 8) / 12);
  [523, 659, 784].forEach((f, i) => beep(f * shift, 0.11, "sine", i * 0.055));
};
const sndWrong = () => { beep(196, 0.16, "sawtooth", 0, 0.1); beep(147, 0.24, "sawtooth", 0.1, 0.1); };
const sndHit = () => { beep(120, 0.25, "square"); beep(90, 0.3, "square", 0.05); };
const sndItem = () => { [880, 1174, 1568].forEach((f, i) => beep(f, 0.1, "triangle", i * 0.06)); };
const sndCount = (go) => {
  if (go) { [523, 659, 784, 1046].forEach(f => beep(f, 0.35, "triangle", 0, 0.14)); }
  else beep(440, 0.12, "sine", 0, 0.14);
};
const sndFanfare = (win) => {
  if (win) [523, 659, 784, 1046, 784, 1046, 1318].forEach((f, i) => beep(f, 0.22, "triangle", i * 0.13, 0.16));
  else [392, 523, 659].forEach((f, i) => beep(f, 0.2, "triangle", i * 0.13, 0.12));
};
// 아이템 종류별 소리
const sndUseItem = (item) => {
  if (item === "shake") { for (let i = 0; i < 4; i++) beep(i % 2 ? 90 : 150, 0.07, "square", i * 0.07, 0.12); }
  else if (item === "freeze") sweep(1200, 280, 0.35, "sine", 0, 0.14);
  else if (item === "flip") sweep(300, 920, 0.28, "sine", 0, 0.13);
  else if (item === "hide") beep(220, 0.18, "sine", 0, 0.1);
  else if (item === "shield") { beep(392, 0.2, "triangle"); beep(523, 0.25, "triangle", 0.02); }
  else if (item === "hint") { beep(1318, 0.1, "sine", 0, 0.1); beep(1568, 0.14, "sine", 0.09, 0.1); }
};
// ------------------------------------------------------------ BGM (짧은 칩튠 루프)
const BGM_MELODY = [659, 784, 880, 784, 659, 587, 659, 0, 587, 659, 784, 880, 1046, 880, 784, 659];
const BGM_BASS = [262, 196, 220, 196];
let bgmTimer = null, bgmStep = 0, bgmNextTime = 0;
function bgmNote(freq, t0, dur, type, vol) {
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type; osc.frequency.value = freq;
  gain.gain.setValueAtTime(vol, t0);
  gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
  osc.connect(gain).connect(masterGain);
  osc.start(t0); osc.stop(t0 + dur + 0.02);
}
function startBGM() {
  ensureAudio();
  if (!audioCtx || bgmTimer) return;
  bgmStep = 0; bgmNextTime = audioCtx.currentTime + 0.06;
  bgmTimer = setInterval(() => {
    if (!soundOn) return;
    while (bgmNextTime < audioCtx.currentTime + 0.3) {
      const stepDur = 0.21;
      const f = BGM_MELODY[bgmStep % BGM_MELODY.length];
      if (f) bgmNote(f, bgmNextTime, stepDur * 0.95, "triangle", 0.035);
      if (bgmStep % 4 === 0) bgmNote(BGM_BASS[(bgmStep / 4) % BGM_BASS.length], bgmNextTime, stepDur * 3.4, "sine", 0.05);
      bgmNextTime += stepDur;
      bgmStep++;
    }
  }, 120);
}
function stopBGM() { if (bgmTimer) { clearInterval(bgmTimer); bgmTimer = null; } }

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
  if (character && (character.kind === "custom" || character.kind === "local") && character.src) {
    return `<img src="${character.src}" alt="キャラ">`;
  }
  const id = character && character.id ? character.id : "cat";
  return (PRESET_MAP[id] || PRESET_MAP.cat).svg;
}

// ------------------------------------------------------------ 종이꽃가루 (캔버스)
const confetti = { parts: [], raf: null };
function confettiCanvas() { return $("confetti"); }
function confettiResize() {
  const c = confettiCanvas();
  c.width = innerWidth; c.height = innerHeight;
}
addEventListener("resize", confettiResize);
function confettiSpawn(x, y, n, spread) {
  const colors = ["#ffd166", "#5b5bd6", "#8be09a", "#f2a7c3", "#58c472", "#f08a24"];
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2, v = (Math.random() * 0.7 + 0.3) * spread;
    confetti.parts.push({
      x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - spread * 0.35,
      w: 5 + Math.random() * 6, h: 3 + Math.random() * 5,
      rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
      color: colors[(Math.random() * colors.length) | 0], life: 1,
    });
  }
  if (!confetti.raf) confettiTick();
}
function confettiTick() {
  const c = confettiCanvas(), ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  confetti.parts = confetti.parts.filter(p => p.life > 0 && p.y < c.height + 30);
  for (const p of confetti.parts) {
    p.vy += 0.12; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.rot += p.vr; p.life -= 0.006;
    ctx.save();
    ctx.globalAlpha = Math.max(p.life, 0);
    ctx.translate(p.x, p.y); ctx.rotate(p.rot);
    ctx.fillStyle = p.color;
    ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
    ctx.restore();
  }
  confetti.raf = confetti.parts.length ? requestAnimationFrame(confettiTick) : null;
  if (!confetti.raf) ctx.clearRect(0, 0, c.width, c.height);
}
const confettiBurst = () => confettiSpawn(innerWidth / 2, innerHeight * 0.35, 45, 9);
const confettiRain = () => {
  let n = 0;
  const iv = setInterval(() => {
    confettiSpawn(Math.random() * innerWidth, -10, 14, 3);
    if (++n >= 12) clearInterval(iv);
  }, 160);
};

// ------------------------------------------------------------ 카운트다운 연출
function runCountdown(done) {
  const el = $("countdown");
  const steps = ["3", "2", "1", "GO!"];
  let i = 0;
  el.classList.remove("hidden");
  const tick = () => {
    if (i >= steps.length) { el.classList.add("hidden"); done(); return; }
    el.textContent = steps[i];
    el.classList.remove("cd-pop"); void el.offsetWidth; el.classList.add("cd-pop");
    sndCount(i === steps.length - 1);
    i++;
    setTimeout(tick, i === steps.length ? 550 : 600);
  };
  tick();
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
      $("my-score").textContent = "0点";
      $("my-streak").textContent = "";
      showScreen("game");
      startBGM();
      runCountdown(() => renderQuestion());
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
      sndUseItem(m.item);
      if (m.blocked) toast("相手のシールドに防がれた");
      break;
    case "game_over": {
      stopBGM();
      renderResults(m.results);
      showScreen("result");
      const mine = m.results.find(r => r.id === myId);
      const iWon = !!(mine && mine.winner);
      sndFanfare(iWon);
      if (iWon) confettiRain();
      break;
    }
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
      renderLocalGrid();
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
  const card = $("question-card");
  card.classList.remove("q-pop"); void card.offsetWidth; card.classList.add("q-pop");
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

function floatScore(text) {
  const card = $("question-card");
  const el = document.createElement("span");
  el.className = "float-score";
  el.textContent = text;
  card.appendChild(el);
  setTimeout(() => el.remove(), 950);
}

function onAnswerResult(m) {
  const btns = document.querySelectorAll(".choice");
  if (pendingChoice !== null && btns[pendingChoice]) {
    btns[pendingChoice].classList.add(m.correct ? "correct" : "wrong");
  }
  if (!m.correct && btns[m.correct_index]) btns[m.correct_index].classList.add("correct");
  if (m.correct) {
    sndCorrect(m.streak);
    document.body.classList.add("flash-correct");
    setTimeout(() => document.body.classList.remove("flash-correct"), 420);
    floatScore(`+${m.gained}`);
  } else sndWrong();
  $("my-score").textContent = `${m.score}点`;
  const streakEl = $("my-streak");
  if (m.streak >= 2) {
    streakEl.textContent = `🔥${m.streak}連続正解`;
    streakEl.classList.remove("combo-pop"); void streakEl.offsetWidth; streakEl.classList.add("combo-pop");
    streakEl.classList.toggle("combo-hot", m.streak >= 5);
  } else {
    streakEl.textContent = "";
    streakEl.classList.remove("combo-hot");
  }
  inventory = m.inventory || inventory;
  if (m.item_gained) {
    sndItem();
    toast(`アイテムゲット：${ITEM_NAMES[m.item_gained]}`);
    confettiBurst();
  }
  renderInventory();
  if (m.item_gained) $("inventory").classList.add("inv-pulse");
  setTimeout(() => $("inventory").classList.remove("inv-pulse"), 650);
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
  results.forEach((r, i) => {
    const li = document.createElement("li");
    if (r.winner) li.className = "winner";
    li.style.animationDelay = `${i * 0.18}s`;
    li.innerHTML = `${avatarHTML(r.character)}<span>${r.winner ? "🏆 " : ""}${r.rank}位 ${escapeHtml(r.nickname)}</span>` +
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

// ------------------------------------------------------------ 로컬 캐릭터 (PC 폴더)
let localChars = [];
function renderLocalGrid() {
  const grid = $("local-grid");
  grid.innerHTML = "";
  localChars.forEach(c => {
    const cell = document.createElement("div");
    cell.className = "char-cell" + (myCharacter.kind === "local" && myCharacter.src === c.src ? " selected" : "");
    cell.innerHTML = `<img src="${c.src}" alt="キャラ"><span class="char-name">${escapeHtml(c.name)}</span>`;
    cell.onclick = () => {
      myCharacter = { kind: "local", src: c.src };
      pendingCustomImage = null;
      $("custom-status").textContent = "";
      renderCharGrid();
      renderLocalGrid();
    };
    grid.appendChild(cell);
  });
  $("local-label").classList.toggle("hidden", !localChars.length);
}
async function loadLocalCharacters() {
  try {
    const res = await fetch("/api/local_characters");
    const data = await res.json();
    localChars = data.characters || [];
    renderLocalGrid();
  } catch (e) { /* 폴더가 비었거나 서버 오류면 조용히 넘어간다 */ }
}

// ------------------------------------------------------------ 초기화
$("join-url").textContent = location.origin + "/";
if (myToken) {
  $("btn-session-reset").classList.remove("hidden");
  connect(); // 저장된 세션으로 재접속 시도
}
renderCharGrid();
loadLocalCharacters();
confettiResize();

// 사운드 ON/OFF 토글
function syncSoundBtn() { $("btn-sound").textContent = soundOn ? "🔊" : "🔇"; }
$("btn-sound").addEventListener("click", () => {
  soundOn = !soundOn;
  localStorage.setItem("qb_sound", soundOn ? "on" : "off");
  ensureAudio();
  if (masterGain) masterGain.gain.value = soundOn ? 1 : 0;
  if (!soundOn) stopBGM();
  syncSoundBtn();
});
syncSoundBtn();
