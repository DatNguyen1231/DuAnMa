// ==================================================================
// Texas Hold'em Poker Online Client - app.js
// ==================================================================

const SEAT_POSITIONS = [
  { left: "50%", top: "97%" },   // Seat 1 (Bottom Center)
  { left: "18%", top: "91%" },   // Seat 2 (Bottom Left)
  { left: "1%",  top: "66%" },   // Seat 3 (Mid-Low Left)
  { left: "1%",  top: "32%" },   // Seat 4 (Mid-High Left)
  { left: "20%", top: "5%"  },   // Seat 5 (Top Left)
  { left: "50%", top: "1%"  },   // Seat 6 (Top Center)
  { left: "80%", top: "5%"  },   // Seat 7 (Top Right)
  { left: "99%", top: "32%" },   // Seat 8 (Mid-High Right)
  { left: "99%", top: "66%" },   // Seat 9 (Mid-Low Right)
  { left: "82%", top: "91%" },   // Seat 10 (Bottom Right)
];

const AVATAR_LIST = ["😎", "🤠", "🦊", "🐯", "🦁", "🐼", "🐸", "🦄", "🐲", "👑", "💎", "🃏"];

let socket = null;
let roomState = null;
let soundEnabled = true;
let themeMode = localStorage.getItem("poker_theme") || "dark";
let mySavedName = localStorage.getItem("poker_player_name") || "Người chơi 1";
let mySavedAvatar = localStorage.getItem("poker_player_avatar") || "😎";
let modalSelectedAvatar = mySavedAvatar;
let audioCtx = null;

// Animation diff state so only newly dealt/flipped cards animate smoothly
const cardAnimTracker = {
  handNumber: 0,
  boardCount: 0,
  rabbitCount: 0,
  seatCardState: {}, // playerId -> "empty" | "hidden" | "faceup"
  myHandDealtNo: 0,
  celebratedHandNo: 0,
};

// Pre-Action Queue State (while waiting for turn)
const preActionState = {
  selected: null, // "check_fold" | "check" | "call_any" | null
  handNumber: 0,
  street: "",
  executing: false,
};

// Live Turn Countdown Timer State
const turnTimerState = {
  active: false,
  turnSeq: 0,
  remainingMs: 0,
  totalMs: 20000,
  syncedAt: 0,
  isMyTurn: false,
  turnPlayerName: "",
  lastTickSec: -1,
};

// ------------------------------------------------------------------
// DOM Elements
// ------------------------------------------------------------------
const statusDot = document.getElementById("statusDot");
const connectionStatus = document.getElementById("connectionStatus");
const toastEl = document.getElementById("toast");

const headerAvatarIcon = document.getElementById("headerAvatarIcon");
const headerPlayerNameLabel = document.getElementById("headerPlayerNameLabel");
const btnLobbyAvatarPick = document.getElementById("btnLobbyAvatarPick");

const lobbyScreen = document.getElementById("lobbyScreen");
const gameScreen = document.getElementById("gameScreen");

const playerNameInput = document.getElementById("playerNameInput");
const initBuyInInput = document.getElementById("initBuyInInput");
const initBlindSelect = document.getElementById("initBlindSelect");
const roomCodeInput = document.getElementById("roomCodeInput");
const roomListContainer = document.getElementById("roomListContainer");

// In-Game Top Nav
const roomCodeDisplay = document.getElementById("roomCodeDisplay");
const blindsDisplay = document.getElementById("blindsDisplay");
const handNumberDisplay = document.getElementById("handNumberDisplay");
const totalTableChipsDisplay = document.getElementById("totalTableChipsDisplay");
const myIdentityText = document.getElementById("myIdentityText");
const myRoleBadge = document.getElementById("myRoleBadge");
const btnSitDownSelf = document.getElementById("btnSitDownSelf");
const btnAddBotQuick = document.getElementById("btnAddBotQuick");
const btnLeaveRoomNav = document.getElementById("btnLeaveRoomNav");

// Game Arena
const turnStatusText = document.getElementById("turnStatusText");
const centerPotAmount = document.getElementById("centerPotAmount");
const allInRunoutBanner = document.getElementById("allInRunoutBanner");
const communityCardsRow = document.getElementById("communityCardsRow");
const showdownSummaryBanner = document.getElementById("showdownSummaryBanner");
const centerCurrentBetPill = document.getElementById("centerCurrentBetPill");
const sidePotsContainer = document.getElementById("sidePotsContainer");
const tableSeatsLayer = document.getElementById("tableSeatsLayer");
const reactionOverlay = document.getElementById("reactionOverlay");
const btnStartHandCenter = document.getElementById("btnStartHandCenter");

// Betting Deck & Hole cards
const bettingDeck = document.getElementById("bettingDeck");
const actorNameBadge = document.getElementById("actorNameBadge");
const actorStackInfo = document.getElementById("actorStackInfo");
const myDeckCardsContainer = document.getElementById("myDeckCardsContainer");
const myHandOwnerLabel = document.getElementById("myHandOwnerLabel");
const myLiveHandRankText = document.getElementById("myLiveHandRankText");
const myDrawHintBadge = document.getElementById("myDrawHintBadge");
const btnRevealCard0 = document.getElementById("btnRevealCard0");
const btnRevealCard1 = document.getElementById("btnRevealCard1");
const btnRevealMyCards = document.getElementById("btnRevealMyCards");

const deckTimerBox = document.getElementById("deckTimerBox");
const deckTimerBadge = document.getElementById("deckTimerBadge");
const deckTimerSecText = document.getElementById("deckTimerSecText");
const deckTimerBarFill = document.getElementById("deckTimerBarFill");

const preActionBar = document.getElementById("preActionBar");
const btnActFold = document.getElementById("btnActFold");
const btnActCheckCall = document.getElementById("btnActCheckCall");
const lblCheckCall = document.getElementById("lblCheckCall");
const subCheckCall = document.getElementById("subCheckCall");
const btnActRaise = document.getElementById("btnActRaise");
const lblRaise = document.getElementById("lblRaise");
const subRaise = document.getElementById("subRaise");
const btnActAllIn = document.getElementById("btnActAllIn");
const subAllIn = document.getElementById("subAllIn");
const minRaiseHintText = document.getElementById("minRaiseHintText");
const raiseSlider = document.getElementById("raiseSlider");
const raiseNumberInput = document.getElementById("raiseNumberInput");

// Sidebar & Logs
const playerCountLabel = document.getElementById("playerCountLabel");
const sidebarPlayerList = document.getElementById("sidebarPlayerList");
const actionLogContainer = document.getElementById("actionLogContainer");
const logCountBadge = document.getElementById("logCountBadge");
const handHistoryContainer = document.getElementById("handHistoryContainer");

// Victory & Loss Modal
const victoryModal = document.getElementById("victoryModal");
const victoryCardNode = document.getElementById("victoryCardNode");
const victoryTrophyIcon = document.getElementById("victoryTrophyIcon");
const victoryModalTitle = document.getElementById("victoryModalTitle");
const victoryPotAmount = document.getElementById("victoryPotAmount");
const victoryHandBadge = document.getElementById("victoryHandBadge");
const victoryNetDelta = document.getElementById("victoryNetDelta");
const btnVictoryPlayAgain = document.getElementById("btnVictoryPlayAgain");
const btnCloseVictoryModal = document.getElementById("btnCloseVictoryModal");
const btnOpenHandReview = document.getElementById("btnOpenHandReview");
const btnReviewHandCenter = document.getElementById("btnReviewHandCenter");

// Hand Review Modal
const handReviewModal = document.getElementById("handReviewModal");
const handReviewHeaderTxt = document.getElementById("handReviewHeaderTxt");
const btnCloseHandReview = document.getElementById("btnCloseHandReview");
const btnCloseHandReviewFooter = document.getElementById("btnCloseHandReviewFooter");
const btnHandReviewReady = document.getElementById("btnHandReviewReady");
const reviewBoardCards = document.getElementById("reviewBoardCards");
const reviewReason = document.getElementById("reviewReason");
const reviewWinnersList = document.getElementById("reviewWinnersList");
const reviewLosersList = document.getElementById("reviewLosersList");

// Other Modals
const renamePlayerModal = document.getElementById("renamePlayerModal");
const modalPlayerNameInput = document.getElementById("modalPlayerNameInput");
const modalAvatarGrid = document.getElementById("modalAvatarGrid");

const ledgerModal = document.getElementById("ledgerModal");
const ledgerOverviewBody = document.getElementById("ledgerOverviewBody");
const settlementListContainer = document.getElementById("settlementListContainer");
const rebuyPlayerSelect = document.getElementById("rebuyPlayerSelect");
const rebuyAmountInput = document.getElementById("rebuyAmountInput");
const adjustStackInput = document.getElementById("adjustStackInput");
const adjustUpdateBuyInCheck = document.getElementById("adjustUpdateBuyInCheck");
const hostAdjustBox = document.getElementById("hostAdjustBox");
const transferFromSelect = document.getElementById("transferFromSelect");
const transferToSelect = document.getElementById("transferToSelect");
const transferAmountInput = document.getElementById("transferAmountInput");
const transferNoteInput = document.getElementById("transferNoteInput");
const ledgerAuditContainer = document.getElementById("ledgerAuditContainer");

const settingsModal = document.getElementById("settingsModal");
const setSmallBlind = document.getElementById("setSmallBlind");
const setBigBlind = document.getElementById("setBigBlind");
const setAnte = document.getElementById("setAnte");
const setDefaultBuyIn = document.getElementById("setDefaultBuyIn");
const setTurnTimeout = document.getElementById("setTurnTimeout");
const setCurrency = document.getElementById("setCurrency");

// ------------------------------------------------------------------
// Player Name & Avatar Persistence
// ------------------------------------------------------------------
function syncIdentityUI() {
  playerNameInput.value = mySavedName;
  headerAvatarIcon.textContent = mySavedAvatar;
  headerPlayerNameLabel.textContent = mySavedName;
  btnLobbyAvatarPick.textContent = mySavedAvatar;
}

playerNameInput.addEventListener("input", () => {
  const val = playerNameInput.value.trim();
  if (val) {
    mySavedName = val.slice(0, 22);
    localStorage.setItem("poker_player_name", mySavedName);
    headerPlayerNameLabel.textContent = mySavedName;
  }
});

function openRenameModal() {
  const myPlayer = roomState?.table?.players?.find((x) => x.id === roomState.myPlayerId);
  const currentName = myPlayer ? myPlayer.name : (playerNameInput.value.trim() || mySavedName);
  modalSelectedAvatar = myPlayer ? myPlayer.avatar : mySavedAvatar;
  modalPlayerNameInput.value = currentName;
  renderAvatarGrid();
  renamePlayerModal.classList.add("open");
  setTimeout(() => modalPlayerNameInput.focus(), 60);
}

function renderAvatarGrid() {
  modalAvatarGrid.innerHTML = AVATAR_LIST.map((av) => `
    <button type="button" class="avatar-option-btn ${av === modalSelectedAvatar ? 'selected' : ''}" onclick="selectModalAvatar('${av}')">
      ${av}
    </button>
  `).join("");
}

window.selectModalAvatar = function(av) {
  modalSelectedAvatar = av;
  renderAvatarGrid();
};

function saveRenameModal() {
  const newName = (modalPlayerNameInput.value || "").trim().slice(0, 22);
  if (!newName) {
    showToast("Vui lòng nhập tên người chơi!");
    return;
  }
  mySavedName = newName;
  mySavedAvatar = modalSelectedAvatar || "😎";
  localStorage.setItem("poker_player_name", mySavedName);
  localStorage.setItem("poker_player_avatar", mySavedAvatar);
  syncIdentityUI();

  if (roomState && roomState.room) {
    send({
      type: "rename_player",
      name: mySavedName,
      avatar: mySavedAvatar,
    });
  } else {
    showToast(`✏️ Đã lưu tên hiển thị: ${mySavedAvatar} ${mySavedName}`);
  }
  renamePlayerModal.classList.remove("open");
}

document.getElementById("btnOpenRename").addEventListener("click", openRenameModal);
btnLobbyAvatarPick.addEventListener("click", openRenameModal);
document.getElementById("btnRenameInRoom").addEventListener("click", openRenameModal);
document.getElementById("btnCloseRenameModal").addEventListener("click", () => renamePlayerModal.classList.remove("open"));
document.getElementById("btnCancelRenameModal").addEventListener("click", () => renamePlayerModal.classList.remove("open"));
document.getElementById("btnSaveRenameModal").addEventListener("click", saveRenameModal);
modalPlayerNameInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") saveRenameModal();
});

// ------------------------------------------------------------------
// Playing Card HTML Renderer (Deal / Flip / Rabbit)
// ------------------------------------------------------------------
function renderCardHtml(cardObj, isMini = false, isWinning = false, animClass = "", delayMs = 0, isRabbit = false) {
  const sizeClass = isMini ? "mini" : "";
  const winClass = isWinning ? "winning-glow" : "";
  const rabbitClass = isRabbit ? "rabbit-card" : "";
  const styleAttr = delayMs > 0 ? `style="animation-delay: ${delayMs}ms;"` : "";
  if (!cardObj || cardObj.hidden) {
    return `<div class="playing-card card-back ${sizeClass} ${animClass}" ${styleAttr} title="Bài úp bí mật">🂠</div>`;
  }
  const colorClass = cardObj.color === "red" ? "red" : "black";
  const rabbitBadge = isRabbit ? `<span class="rabbit-ribbon">🐇 SĂN THỎ</span>` : "";
  return `
    <div class="playing-card ${colorClass} ${sizeClass} ${winClass} ${rabbitClass} ${animClass}" ${styleAttr}>
      ${rabbitBadge}
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <span class="c-rank">${escapeHtml(cardObj.rank)}</span>
        <span class="c-suit-sm">${escapeHtml(cardObj.suitSymbol)}</span>
      </div>
      <div class="c-suit-big">${escapeHtml(cardObj.suitSymbol)}</div>
    </div>
  `;
}

// ------------------------------------------------------------------
// Sound Synthesizer & Formatting
// ------------------------------------------------------------------
function fmt(n) {
  const num = Number(n) || 0;
  return num.toLocaleString("en-US");
}

function showToast(msg) {
  if (!msg) return;
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toastEl.classList.remove("show"), 2600);
}

function initAudio() {
  if (!audioCtx) {
    const AudioClass = window.AudioContext || window.webkitAudioContext;
    if (AudioClass) audioCtx = new AudioClass();
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume();
  }
}

function playSound(type = "chip") {
  if (!soundEnabled) return;
  initAudio();
  if (!audioCtx) return;

  const now = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);

  if (type === "chip") {
    osc.type = "sine";
    osc.frequency.setValueAtTime(1450, now);
    osc.frequency.exponentialRampToValueAtTime(2200, now + 0.06);
    gain.gain.setValueAtTime(0.28, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
    osc.start(now);
    osc.stop(now + 0.08);
  } else if (type === "check") {
    osc.type = "triangle";
    osc.frequency.setValueAtTime(260, now);
    osc.frequency.exponentialRampToValueAtTime(110, now + 0.09);
    gain.gain.setValueAtTime(0.35, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.09);
    osc.start(now);
    osc.stop(now + 0.09);
  } else if (type === "fold") {
    osc.type = "sine";
    osc.frequency.setValueAtTime(320, now);
    osc.frequency.exponentialRampToValueAtTime(90, now + 0.14);
    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);
    osc.start(now);
    osc.stop(now + 0.14);
  } else if (type === "allin") {
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(440, now);
    osc.frequency.setValueAtTime(659.25, now + 0.08);
    osc.frequency.setValueAtTime(880, now + 0.16);
    gain.gain.setValueAtTime(0.22, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.start(now);
    osc.stop(now + 0.35);
  } else if (type === "tick") {
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, now);
    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.045);
    osc.start(now);
    osc.stop(now + 0.045);
  } else if (type === "win" || type === "deal") {
    osc.type = "triangle";
    osc.frequency.setValueAtTime(523.25, now);
    osc.frequency.setValueAtTime(659.25, now + 0.08);
    osc.frequency.setValueAtTime(783.99, now + 0.16);
    osc.frequency.setValueAtTime(1046.5, now + 0.24);
    gain.gain.setValueAtTime(0.32, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
    osc.start(now);
    osc.stop(now + 0.45);
  }
}

// ------------------------------------------------------------------
// Live Turn Countdown Timer Loop (100ms)
// ------------------------------------------------------------------
function syncTurnTimerFromTable(t) {
  const hasTurn = (
    t &&
    t.street !== "idle" &&
    t.street !== "showdown" &&
    !t.allInRunout &&
    t.turnSeat !== null &&
    t.turnSeat !== undefined &&
    t.turnRemainingMs !== null &&
    t.turnRemainingMs !== undefined
  );

  if (!hasTurn) {
    turnTimerState.active = false;
    turnTimerState.lastTickSec = -1;
    deckTimerBox.classList.remove("show");
    return;
  }

  turnTimerState.active = true;
  turnTimerState.turnSeq = t.turnSeq || 0;
  turnTimerState.remainingMs = Math.max(0, Number(t.turnRemainingMs) || 0);
  turnTimerState.totalMs = Math.max(1000, Number(t.turnTotalMs) || (Number(t.turnTimeoutSec || 20) * 1000));
  turnTimerState.syncedAt = performance.now();
  turnTimerState.isMyTurn = Boolean(t.isMyTurn);
  turnTimerState.turnPlayerName = t.turnPlayerName || "";
  deckTimerBox.classList.add("show");
  updateTurnTimerTick();
}

function updateTurnTimerTick() {
  if (!turnTimerState.active) return;
  const elapsed = performance.now() - turnTimerState.syncedAt;
  const remMs = Math.max(0, turnTimerState.remainingMs - elapsed);
  const pct = Math.max(0, Math.min(100, (remMs / turnTimerState.totalMs) * 100));
  const secLeft = Math.ceil(remMs / 1000);

  const isWarn = secLeft <= 8 && secLeft > 5;
  const isDanger = secLeft <= 5;

  const whoText = turnTimerState.isMyTurn
    ? "⏱️ LƯỢT BẠN CÒN:"
    : `⏱️ Lượt ${turnTimerState.turnPlayerName}:`;
  deckTimerBadge.className = `deck-timer-badge ${isDanger ? "danger" : ""}`;
  deckTimerBadge.innerHTML = `
    <span>${escapeHtml(whoText)}</span>
    <span id="deckTimerSecText">${secLeft}s</span>
    <span style="font-size: 11px; font-weight: 600; opacity: 0.85;">(Tự động Bỏ bài)</span>
  `;
  deckTimerBarFill.style.width = `${pct.toFixed(1)}%`;
  deckTimerBarFill.className = `seat-timer-fill ${isDanger ? "danger" : isWarn ? "warn" : ""}`;

  document.querySelectorAll(".live-seat-timer-fill").forEach((bar) => {
    bar.style.width = `${pct.toFixed(1)}%`;
    bar.className = `seat-timer-fill live-seat-timer-fill ${isDanger ? "danger" : isWarn ? "warn" : ""}`;
  });
  document.querySelectorAll(".live-seat-timer-sec").forEach((lbl) => {
    lbl.textContent = `${secLeft}s`;
    lbl.className = `seat-timer-sec live-seat-timer-sec ${isDanger ? "danger" : ""}`;
  });

  if (turnTimerState.isMyTurn && secLeft <= 5 && secLeft >= 1 && turnTimerState.lastTickSec !== secLeft) {
    turnTimerState.lastTickSec = secLeft;
    playSound("tick");
  }
}

setInterval(updateTurnTimerTick, 100);

// ------------------------------------------------------------------
// Theme Setup
// ------------------------------------------------------------------
function applyTheme() {
  const themeIcon = document.getElementById("themeIcon");
  const themeLabel = document.getElementById("themeLabel");
  if (themeMode === "dark") {
    document.body.classList.add("dark-theme");
    themeIcon.textContent = "☀️";
    themeLabel.textContent = "Sáng";
  } else {
    document.body.classList.remove("dark-theme");
    themeIcon.textContent = "🌙";
    themeLabel.textContent = "Tối";
  }
  localStorage.setItem("poker_theme", themeMode);
}

document.getElementById("btnToggleTheme").addEventListener("click", () => {
  themeMode = themeMode === "dark" ? "light" : "dark";
  applyTheme();
});

document.getElementById("btnToggleSound").addEventListener("click", () => {
  soundEnabled = !soundEnabled;
  document.getElementById("soundIcon").textContent = soundEnabled ? "🔊" : "🔇";
  showToast(soundEnabled ? "Đã bật âm thanh" : "Đã tắt âm thanh");
});

// ------------------------------------------------------------------
// WebSocket Communication
// ------------------------------------------------------------------
function send(payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  } else {
    showToast("Chưa kết nối tới máy chủ!");
  }
}

function connect() {
  const isSecure = window.location.protocol === "https:";
  let host = window.location.host;
  if (!host || host === "" || window.location.protocol === "file:") {
    host = "localhost:8004";
  }
  const wsUrl = `${isSecure ? "wss:" : "ws:"}//${host}/ws`;

  connectionStatus.textContent = "Đang kết nối...";
  statusDot.className = "status-dot connecting";

  try {
    socket = new WebSocket(wsUrl);
  } catch (err) {
    console.error("Lỗi khởi tạo WebSocket:", err);
    connectionStatus.textContent = "Lỗi kết nối";
    statusDot.className = "status-dot error";
    setTimeout(connect, 3000);
    return;
  }

  socket.addEventListener("open", () => {
    connectionStatus.textContent = "Đã kết nối";
    statusDot.className = "status-dot connected";
    send({ type: "get_rooms" });
  });

  socket.addEventListener("message", (event) => {
    try {
      const data = JSON.parse(event.data);
      handleServerMessage(data);
    } catch (err) {
      console.error("WS parse error:", err);
    }
  });

  socket.addEventListener("error", (err) => {
    console.warn("WebSocket error event:", err);
    connectionStatus.textContent = "Lỗi kết nối";
    statusDot.className = "status-dot error";
  });

  socket.addEventListener("close", () => {
    connectionStatus.textContent = "Mất kết nối";
    statusDot.className = "status-dot error";
    setTimeout(connect, 2500);
  });
}

function handleServerMessage(data) {
  if (data.type === "room_list") {
    renderRoomList(data.rooms || []);
    return;
  }

  if (data.type === "room_created" || data.type === "joined") {
    setInRoomMode(true);
    showToast(
      data.mode === "bot"
        ? "🤖 Đã mở bàn đấu với 3 Bot AI! Bắt đầu ngay!"
        : `Đã vào phòng Poker #${data.room}`
    );
    return;
  }

  if (data.type === "left_room") {
    roomState = null;
    turnTimerState.active = false;
    deckTimerBox.classList.remove("show");
    closeVictoryPopup();
    setInRoomMode(false);
    send({ type: "get_rooms" });
    return;
  }

  if (data.type === "state") {
    roomState = data;
    setInRoomMode(true);
    if (data.sound) playSound(data.sound);
    if (data.toast) showToast(data.toast);
    renderAll();
    return;
  }

  if (data.type === "chat_message") {
    showFloatingReaction(data);
    return;
  }

  if (data.type === "throw_item") {
    showFlyingProp(data);
    return;
  }

  if (data.type === "error") {
    showToast("⚠️ " + (data.message || "Có lỗi xảy ra"));
  }
}

// ------------------------------------------------------------------
// VIEW MODE TOGGLE (CHỈ HIỂN THỊ PHÒNG KHI Ở SẢNH, VÀO CHƠI MỚI HIỂN THỊ BÀN)
// ------------------------------------------------------------------
function setInRoomMode(inRoom) {
  if (inRoom) {
    lobbyScreen.style.display = "none";
    gameScreen.style.display = "block";
  } else {
    lobbyScreen.style.display = "block";
    gameScreen.style.display = "none";
    closeVictoryPopup();
  }
}

// ------------------------------------------------------------------
// Room Creation & Joining Actions
// ------------------------------------------------------------------
function getCurrentNameAndAvatar() {
  const name = (playerNameInput.value || "").trim() || mySavedName || "Người chơi";
  mySavedName = name.slice(0, 22);
  localStorage.setItem("poker_player_name", mySavedName);
  syncIdentityUI();
  return { name: mySavedName, avatar: mySavedAvatar };
}

function getInitConfig(cmdType) {
  const [sb, bb] = (initBlindSelect.value || "1000:2000").split(":").map(Number);
  const buyIn = parseInt(initBuyInInput.value, 10) || 100000;
  const { name, avatar } = getCurrentNameAndAvatar();
  return {
    type: cmdType,
    name,
    avatar,
    buyIn,
    smallBlind: sb,
    bigBlind: bb,
    turnTimeout: 20,
    currency: "VNĐ",
  };
}

document.getElementById("btnCreateBotRoom").addEventListener("click", () => {
  send(getInitConfig("create_bot_room"));
});

document.getElementById("btnCreateRoom").addEventListener("click", () => {
  send(getInitConfig("create_room"));
});

document.getElementById("btnQuickMatch").addEventListener("click", () => {
  send(getInitConfig("quick_match"));
});

document.getElementById("btnJoinRoom").addEventListener("click", () => {
  const code = roomCodeInput.value.trim();
  if (!code) {
    showToast("Vui lòng nhập mã phòng 6 số!");
    return;
  }
  const { name, avatar } = getCurrentNameAndAvatar();
  send({
    type: "join_room",
    room: code,
    name,
    avatar,
    buyIn: parseInt(initBuyInInput.value, 10) || 100000,
  });
});

btnSitDownSelf.addEventListener("click", () => {
  const { name, avatar } = getCurrentNameAndAvatar();
  send({
    type: "sit_down",
    name,
    avatar,
    buyIn: roomState?.table?.settings?.defaultBuyIn || 100000,
  });
});

btnAddBotQuick.addEventListener("click", () => {
  send({ type: "add_bot" });
});

btnLeaveRoomNav.addEventListener("click", () => {
  send({ type: "leave_room" });
});

document.getElementById("btnRefreshRooms").addEventListener("click", () => {
  send({ type: "get_rooms" });
  showToast("Đã làm mới danh sách phòng!");
});

document.getElementById("roomCodeChip").addEventListener("click", () => {
  if (roomState?.room) {
    navigator.clipboard.writeText(roomState.room);
    showToast("Đã sao chép mã phòng: " + roomState.room);
  }
});

// ------------------------------------------------------------------
// Render Lobby Room List
// ------------------------------------------------------------------
function renderRoomList(rooms) {
  if (!rooms || rooms.length === 0) {
    roomListContainer.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 24px; font-size: 13.5px; grid-column: 1 / -1;">
        Chưa có phòng nào đang mở.<br>Hãy bấm <b>➕ Tạo Phòng Mới</b> hoặc <b>🤖 Đấu Với Bot AI</b> để bắt đầu chơi ngay!
      </div>
    `;
    return;
  }

  roomListContainer.innerHTML = rooms.map((r) => `
    <div class="room-card">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong class="mono" style="font-size: 14.5px;">#${r.code} · ${escapeHtml(r.name)}</strong>
        <span style="font-size: 11.5px; font-weight: 800; color: var(--primary);">${r.playerCount}/10 ghế</span>
      </div>
      <div style="font-size: 12px; color: var(--text-muted); display: flex; justify-content: space-between;">
        <span>Blinds: <b>${fmt(r.smallBlind)}/${fmt(r.bigBlind)}</b></span>
        <span>Pot: <b>${fmt(r.pot)} ${escapeHtml(r.currency)}</b></span>
      </div>
      <button class="btn-primary" style="min-height: 34px; font-size: 12.5px;" onclick="joinRoomByCode('${r.code}')">
        Vào Bàn Chơi
      </button>
    </div>
  `).join("");
}

window.joinRoomByCode = function(code) {
  const { name, avatar } = getCurrentNameAndAvatar();
  send({
    type: "join_room",
    room: code,
    name,
    avatar,
    buyIn: parseInt(initBuyInInput.value, 10) || 100000,
  });
};

// ------------------------------------------------------------------
// Render Full Game State
// ------------------------------------------------------------------
function renderAll() {
  if (!roomState || !roomState.table) return;
  const t = roomState.table;
  const s = t.settings;
  const myPlayer = t.players.find((x) => x.id === roomState.myPlayerId);

  // Identity & Header Nav
  if (myPlayer) {
    mySavedName = myPlayer.name;
    mySavedAvatar = myPlayer.avatar;
    syncIdentityUI();
    myIdentityText.innerHTML = `${escapeHtml(myPlayer.avatar)} Bạn: <b>${escapeHtml(myPlayer.name)}</b> (#${myPlayer.seat + 1})`;
    btnSitDownSelf.style.display = "none";
  } else {
    myIdentityText.innerHTML = `👀 Bạn đang xem (Chưa ngồi ghế)`;
    btnSitDownSelf.style.display = t.players.length < 10 ? "inline-flex" : "none";
  }
  myRoleBadge.textContent = roomState.isHost ? "👑 Chủ bàn" : "";
  btnAddBotQuick.style.display = roomState.isHost ? "inline-flex" : "none";

  roomCodeDisplay.textContent = roomState.room;
  blindsDisplay.textContent = `${fmt(s.smallBlind)}/${fmt(s.bigBlind)}`;
  handNumberDisplay.textContent = `#${t.handNumber}`;
  totalTableChipsDisplay.textContent = `${fmt(t.summary.totalChipsOnTable)} ${s.currency}`;
  playerCountLabel.textContent = t.players.length;

  // Street Pills
  document.querySelectorAll(".street-pill").forEach((el) => {
    el.classList.toggle("active", el.dataset.street === t.street);
  });

  // All-in Smooth Runout Banner & Turn Status
  if (t.allInRunout) {
    allInRunoutBanner.style.display = "block";
    const streetMap = {
      preflop: "Đã lật bài tẩy! Chuẩn bị chia 3 lá Flop...",
      flop: "Đã chia Flop (3 lá)! Chuẩn bị mở lá thứ 4 (Turn)...",
      turn: "Đã mở Turn (4 lá)! Chuẩn bị mở lá cuối (River)...",
      river: "Đã đủ 5 lá bài chung! Đang chấm bài trao Pot...",
    };
    allInRunoutBanner.textContent = `🔥 ALL-IN SHOWDOWN! ${streetMap[t.street] || "Đang mở bài từ từ..."}`;
    turnStatusText.innerHTML = `🔥 <span style="color: #fbbf24; font-weight: 900;">ALL-IN! Đang mở bài chung từ từ từng vòng...</span>`;
  } else {
    allInRunoutBanner.style.display = "none";
    if (t.street === "idle") {
      turnStatusText.innerHTML = `<span style="color: var(--text-muted);">Đang chờ bắt đầu ván mới (${t.players.length} người tại bàn)</span>`;
    } else if (t.street === "showdown") {
      turnStatusText.innerHTML = `<span style="color: #fbbf24; font-weight: 900;">🏆 KẾT THÚC VÁN #${t.handNumber}!</span>`;
    } else if (t.isMyTurn) {
      turnStatusText.innerHTML = `🔥 <span style="color: #10b981; font-weight: 900;">ĐẾN LƯỢT CỦA BẠN! (${s.turnTimeout || 20}s)</span>`;
    } else if (t.turnPlayerName) {
      const botTag = t.turnPlayerIsBot ? " (🤖 Bot...)" : "";
      turnStatusText.innerHTML = `⏳ Đang chờ lượt của: <span style="color: #fbbf24;">${escapeHtml(t.turnPlayerName)}${botTag}</span>`;
    }
  }

  // Turn Countdown Timer
  syncTurnTimerFromTable(t);

  // Pot & Center
  const displayPot = (t.street === "showdown" && t.lastHandResult) ? t.lastHandResult.totalPot : t.pot;
  centerPotAmount.textContent = `${fmt(displayPot)} ${s.currency}`;
  centerCurrentBetPill.innerHTML = t.street === "showdown"
    ? `Trạng thái: <strong style="color: #fbbf24;">Ván #${t.handNumber} đã hoàn tất</strong>`
    : `Mức cược vòng này: <strong class="mono">${fmt(t.currentBet)} ${s.currency}</strong>`;

  // Render 5 Community Cards (+ Rabbit Cards)
  renderCommunityCards(t);

  // Showdown summary message
  if (t.lastShowdownSummary && (t.street === "showdown" || t.street === "idle")) {
    showdownSummaryBanner.style.display = "block";
    showdownSummaryBanner.textContent = t.lastShowdownSummary;
  } else {
    showdownSummaryBanner.style.display = "none";
  }

  // Side Pots
  if (t.pots && t.pots.length > 1) {
    sidePotsContainer.innerHTML = t.pots.map((p) => `
      <span class="side-pot-chip" title="Đủ điều kiện ăn: ${escapeHtml(p.eligiblePlayerNames.join(', '))}">
        ${escapeHtml(p.name)}: ${fmt(p.amount)}
      </span>
    `).join("");
  } else {
    sidePotsContainer.innerHTML = "";
  }

  // Center Start Next Hand Button (Optional on table felt)
  const canDealNext = (t.street === "idle" || t.street === "showdown") && !t.allInRunout;
  btnStartHandCenter.style.display = canDealNext ? "inline-flex" : "none";
  btnReviewHandCenter.style.display = (canDealNext && t.lastHandResult) ? "inline-flex" : "none";

  const isMeReady = Boolean(myPlayer?.readyNext);
  const readyCount = t.readyCount || 0;
  const readyTotal = t.readyTotal || 0;

  if (canDealNext) {
    if (isMeReady) {
      btnStartHandCenter.textContent = `⏳ ĐÃ SẴN SÀNG (${readyCount}/${readyTotal})`;
      btnStartHandCenter.classList.add("is-waiting");
    } else {
      btnStartHandCenter.textContent = t.handNumber > 0
        ? `▶️ SẴN SÀNG (${readyCount}/${readyTotal})`
        : `▶️ BẮT ĐẦU VÁN ĐẤU (${readyCount}/${readyTotal})`;
      btnStartHandCenter.classList.remove("is-waiting");
    }

    if (victoryModal.classList.contains("open")) {
      updateVictoryModalReadyStatus(t);
    }
    if (handReviewModal.classList.contains("open")) {
      updateHandReviewReadyStatus(t);
    }
  }

  // CLEAN VICTORY / LOSS POPUP
  if (
    t.street === "showdown" &&
    !t.allInRunout &&
    t.lastHandResult &&
    t.lastHandResult.handNumber > 0
  ) {
    if (cardAnimTracker.celebratedHandNo !== t.lastHandResult.handNumber) {
      cardAnimTracker.celebratedHandNo = t.lastHandResult.handNumber;
      showVictoryPopup(t.lastHandResult, t);
    }
  } else if (t.street !== "showdown" && t.street !== "idle") {
    closeVictoryPopup();
    closeHandReviewModal();
  }

  renderTableSeats(t);
  renderSidebarPlayers(t);
  renderMyHoleCardsBox(t);
  renderBettingDeck(t);
  renderLogsAndHistory(t);

  cardAnimTracker.handNumber = t.handNumber;

  if (ledgerModal.classList.contains("open")) {
    renderLedgerModalContent();
  }
}

// ------------------------------------------------------------------
// POPUP CHIẾN THẮNG & THUA CUỘC & SẴN SÀNG VÁN MỚI
// ------------------------------------------------------------------
function showVictoryPopup(res, t) {
  if (!res) return;
  const currency = res.currency || t?.settings?.currency || "VNĐ";
  const myPlayerId = roomState?.myPlayerId;
  const winners = res.winners || [];
  const losers = res.losers || [];
  const topWinner = winners[0];

  const myWinner = winners.find((w) => w.id === myPlayerId);
  const myLoser = losers.find((l) => l.id === myPlayerId);
  const amIWinner = Boolean(myWinner);

  if (amIWinner) {
    victoryCardNode?.classList.remove("is-loss");
    victoryPotAmount.className = "victory-pot-amount win";
    victoryTrophyIcon.textContent = "🏆";
    victoryModalTitle.textContent = "CHÚC MỪNG BẠN ĐÃ THẮNG!";
    victoryPotAmount.textContent = `+${fmt(myWinner.wonAmount)} ${currency}`;
    const handName = myWinner.handName || (res.endedBy === "fold" ? "Đối thủ đã Bỏ bài (Fold)" : "Thắng Pot");
    victoryHandBadge.textContent = `🃏 ${handName}`;
    const netGain = myWinner.netDelta;
    victoryNetDelta.textContent = `Lời ròng ván này: +${fmt(netGain)} ${currency}`;
    playSound("win");
    launchVictoryConfetti();
  } else if (myLoser) {
    victoryCardNode?.classList.add("is-loss");
    victoryPotAmount.className = "victory-pot-amount loss";
    victoryTrophyIcon.textContent = "💔";
    victoryModalTitle.textContent = "BẠN ĐÃ THUA VÁN NÀY";
    const lostAmt = myLoser.lostAmount || 0;
    victoryPotAmount.textContent = lostAmt > 0 ? `-${fmt(lostAmt)} ${currency}` : `0 ${currency}`;
    const topHand = topWinner?.handName || (res.endedBy === "fold" ? "Đối thủ đã Fold" : "Thắng Pot");
    victoryHandBadge.textContent = topWinner ? `👑 ${topWinner.name} thắng với ${topHand}` : "Ván đấu kết thúc";
    victoryNetDelta.textContent = lostAmt > 0
      ? `Số chip bị trừ: -${fmt(lostAmt)} ${currency} (Còn lại: ${fmt(myLoser.stackAfter)} ${currency})`
      : `Bạn đã Bỏ bài (Fold) sớm mà không mất thêm chip (Còn lại: ${fmt(myLoser.stackAfter)} ${currency})`;
    playSound("deal");
  } else {
    victoryCardNode?.classList.remove("is-loss");
    victoryPotAmount.className = "victory-pot-amount neutral";
    victoryTrophyIcon.textContent = "👀";
    victoryModalTitle.textContent = topWinner ? `${topWinner.name} CHIẾN THẮNG!` : "KẾT THÚC VÁN ĐẤU";
    victoryPotAmount.textContent = topWinner ? `+${fmt(topWinner.wonAmount)} ${currency}` : `${fmt(res.totalPot)} ${currency}`;
    victoryHandBadge.textContent = topWinner ? `🃏 ${topWinner.handName || 'Thắng Pot'}` : "Đang theo dõi";
    victoryNetDelta.textContent = "Bạn không tham gia ván này (Đang quan sát)";
    playSound("deal");
  }

  updateVictoryModalReadyStatus(t);
  victoryModal.classList.add("open");
}

function updateVictoryModalReadyStatus(t) {
  const myPlayer = t?.players?.find((x) => x.id === roomState?.myPlayerId);
  const isMeReady = Boolean(myPlayer?.readyNext);
  const readyCount = t?.readyCount || 0;
  const readyTotal = t?.readyTotal || 0;

  if (isMeReady) {
    btnVictoryPlayAgain.textContent = `⏳ ĐÃ SẴN SÀNG (${readyCount}/${readyTotal}) - CHỜ NGƯỜI KHÁC`;
    btnVictoryPlayAgain.classList.add("is-waiting");
    btnVictoryPlayAgain.disabled = true;
  } else {
    btnVictoryPlayAgain.textContent = `▶️ SẴN SÀNG CHƠI TIẾP (${readyCount}/${readyTotal})`;
    btnVictoryPlayAgain.classList.remove("is-waiting");
    btnVictoryPlayAgain.disabled = false;
  }
}

function closeVictoryPopup() {
  victoryModal.classList.remove("open");
}
window.closeVictoryPopup = closeVictoryPopup;

function openHandReviewModal(res, t) {
  if (!res) res = roomState?.table?.lastHandResult;
  if (!res) {
    showToast("Chưa có dữ liệu ván đấu vừa qua!");
    return;
  }
  const curTable = t || roomState?.table || {};
  const currency = res.currency || curTable.settings?.currency || "VNĐ";

  handReviewHeaderTxt.textContent = `Chi Tiết Ván Đấu #${res.handNumber}`;

  // Board cards
  const board = res.boardCards || [];
  const rabbit = (res.rabbitRevealed && res.rabbitCards) ? res.rabbitCards : [];
  if (board.length === 0) {
    reviewBoardCards.innerHTML = `<span style="color:#94a3b8; font-size:13px; font-style:italic;">(Ván kết thúc trước khi chia bài chung)</span>`;
  } else {
    let html = board.map(c => renderCardHtml(c)).join("");
    if (rabbit.length > 0) {
      html += `<div style="display:inline-flex; align-items:center; gap:4px; margin-left:8px; border-left:1px dashed #64748b; padding-left:8px;" title="Rabbit Hunt (Bài giả định)">` +
        rabbit.map(c => renderCardHtml(c, false, false, "", 0, true)).join("") + `</div>`;
    }
    reviewBoardCards.innerHTML = html;
  }

  reviewReason.textContent = `Tổng Pot: ${fmt(res.totalPot)} ${currency} • Diễn biến: ${res.reason || res.endReason || 'Kết thúc ván'}`;

  // Winners list
  const winners = res.winners || [];
  if (winners.length === 0) {
    reviewWinnersList.innerHTML = `<div style="color:#94a3b8; font-size:13px; padding:6px 0;">Không có thông tin người thắng.</div>`;
  } else {
    reviewWinnersList.innerHTML = winners.map(w => {
      const cardsHtml = (w.holeCards || []).map(c => renderCardHtml(c, true)).join("");
      return `
        <div class="review-player-row is-winner">
          <div class="review-player-info">
            <span style="font-size: 22px;">${w.avatar || '👤'}</span>
            <div>
              <div class="review-player-name">${escapeHtml(w.name)} ${w.isMe ? '<span style="color:#34d399;font-size:11.5px;font-weight:800;">(BẠN)</span>' : ''}</div>
              <div class="review-hand-desc">🃏 ${escapeHtml(w.handName || 'Thắng Pot')}</div>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:10px;">
            <div class="review-player-cards">${cardsHtml}</div>
            <div class="review-player-delta positive">+${fmt(w.wonAmount)} ${currency}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  // Losers list
  const losers = res.losers || [];
  if (losers.length === 0) {
    reviewLosersList.innerHTML = `<div style="color:#94a3b8; font-size:13px; padding:6px 0;">Không có ai chịu lỗ thêm trong ván.</div>`;
  } else {
    reviewLosersList.innerHTML = losers.map(l => {
      const cardsHtml = (l.holeCards || []).map(c => renderCardHtml(c, true)).join("");
      return `
        <div class="review-player-row is-loser">
          <div class="review-player-info">
            <span style="font-size: 22px;">${l.avatar || '👤'}</span>
            <div>
              <div class="review-player-name">${escapeHtml(l.name)} ${l.isMe ? '<span style="color:#ef4444;font-size:11.5px;font-weight:800;">(BẠN)</span>' : ''}</div>
              <div class="review-hand-desc">${escapeHtml(l.handName || 'Đã Thua')}</div>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:10px;">
            <div class="review-player-cards">${cardsHtml}</div>
            <div class="review-player-delta negative">-${fmt(l.lostAmount)} ${currency}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  updateHandReviewReadyStatus(curTable);
  handReviewModal.classList.add("open");
}

function updateHandReviewReadyStatus(t) {
  const myPlayer = t?.players?.find((x) => x.id === roomState?.myPlayerId);
  const isMeReady = Boolean(myPlayer?.readyNext);
  const readyCount = t?.readyCount || 0;
  const readyTotal = t?.readyTotal || 0;

  if (isMeReady) {
    btnHandReviewReady.textContent = `⏳ Đã Sẵn Sàng (${readyCount}/${readyTotal})`;
    btnHandReviewReady.disabled = true;
  } else {
    btnHandReviewReady.textContent = `▶️ Sẵn Sàng Ván Mới (${readyCount}/${readyTotal})`;
    btnHandReviewReady.disabled = false;
  }
}

function closeHandReviewModal() {
  handReviewModal.classList.remove("open");
}
window.closeHandReviewModal = closeHandReviewModal;

btnVictoryPlayAgain.addEventListener("click", () => {
  send({ type: "ready_next", ready: true });
});

btnOpenHandReview.addEventListener("click", () => {
  openHandReviewModal(roomState?.table?.lastHandResult, roomState?.table);
});

btnReviewHandCenter.addEventListener("click", () => {
  openHandReviewModal(roomState?.table?.lastHandResult, roomState?.table);
});

btnCloseVictoryModal.addEventListener("click", closeVictoryPopup);
btnCloseHandReview.addEventListener("click", closeHandReviewModal);
btnCloseHandReviewFooter.addEventListener("click", closeHandReviewModal);

// Close modals when clicking the darkened backdrop outside the card
victoryModal.addEventListener("click", (e) => {
  if (e.target === victoryModal) {
    closeVictoryPopup();
  }
});
handReviewModal.addEventListener("click", (e) => {
  if (e.target === handReviewModal) {
    closeHandReviewModal();
  }
});

// Close modals when pressing the Escape key
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeVictoryPopup();
    closeHandReviewModal();
  }
});

btnHandReviewReady.addEventListener("click", () => {
  send({ type: "ready_next", ready: true });
});

btnStartHandCenter.addEventListener("click", () => {
  send({ type: "ready_next", ready: true });
});

function launchVictoryConfetti() {
  const tableArena = document.getElementById("pokerArena");
  if (!tableArena) return;
  const icons = ["🪙", "💰", "✨", "🏆", "💎"];
  for (let i = 0; i < 18; i++) {
    const el = document.createElement("div");
    el.className = "confetti-coin";
    el.textContent = icons[i % icons.length];
    el.style.left = `${15 + Math.random() * 70}%`;
    el.style.top = `${15 + Math.random() * 30}%`;
    el.style.animationDelay = `${i * 40}ms`;
    tableArena.appendChild(el);
    setTimeout(() => el.remove(), 1800 + i * 40);
  }
}

// ------------------------------------------------------------------
// Community Cards
// ------------------------------------------------------------------
function renderCommunityCards(t) {
  const board = t.boardCards || [];
  const rabbit = (t.rabbitRevealed && t.rabbitCards) ? t.rabbitCards : [];
  const winSet = new Set(t.winningCards || []);
  const isNewHand = t.handNumber !== cardAnimTracker.handNumber;
  const prevCount = isNewHand ? 0 : cardAnimTracker.boardCount;
  const prevRabbitCount = isNewHand ? 0 : cardAnimTracker.rabbitCount;

  const slots = [];
  for (let i = 0; i < 5; i++) {
    if (i < board.length) {
      const c = board[i];
      const isNewlyDealt = i >= prevCount;
      const animClass = isNewlyDealt ? "animate-deal" : "";
      const delayMs = isNewlyDealt ? (i - prevCount) * 145 : 0;
      slots.push(renderCardHtml(c, false, winSet.has(c.code), animClass, delayMs, false));
    } else if (i - board.length < rabbit.length) {
      const rIdx = i - board.length;
      const rc = rabbit[rIdx];
      const isNewlyRabbit = rIdx >= prevRabbitCount;
      const animClass = isNewlyRabbit ? "animate-flip" : "";
      const delayMs = isNewlyRabbit ? rIdx * 150 : 0;
      slots.push(renderCardHtml(rc, false, false, animClass, delayMs, true));
    } else {
      slots.push(`<div class="playing-card card-slot-empty">♠</div>`);
    }
  }
  cardAnimTracker.boardCount = board.length;
  cardAnimTracker.rabbitCount = rabbit.length;
  communityCardsRow.innerHTML = slots.join("");
}

// ------------------------------------------------------------------
// Table Seats
// ------------------------------------------------------------------
function renderTableSeats(t) {
  const winSet = new Set(t.winningCards || []);
  const isNewHand = t.handNumber !== cardAnimTracker.handNumber;
  const isPostHand = (t.street === "showdown" || t.street === "idle") && !t.allInRunout && t.handNumber > 0;

  // Session MVP
  let mvpPlayerId = null;
  let maxProfit = 0;
  t.players.forEach((pl) => {
    if (pl.netProfit > maxProfit) {
      maxProfit = pl.netProfit;
      mvpPlayerId = pl.id;
    }
  });

  tableSeatsLayer.innerHTML = t.players.map((p) => {
    const pos = SEAT_POSITIONS[p.seat % SEAT_POSITIONS.length];
    const isMe = p.id === roomState.myPlayerId;
    const classes = ["seat-node"];
    if (p.isTurn) classes.push("is-turn");

    let outcomeBadgeHtml = "";
    if (isPostHand) {
      if (p.lastHandOutcome === "winner" || p.lastWonAmount > 0) {
        classes.push("is-winner");
        outcomeBadgeHtml = `<div class="seat-outcome-badge badge-win">🏆 THẮNG +${fmt(p.lastWonAmount)}</div>`;
      } else if (p.lastHandOutcome === "loser_showdown") {
        classes.push("is-loser-showdown");
        const lostAmt = Math.abs(p.lastHandDelta || p.lastHandBet || 0);
        outcomeBadgeHtml = `<div class="seat-outcome-badge badge-loss">💔 THUA -${fmt(lostAmt)}</div>`;
      } else if (p.lastHandOutcome === "loser_folded") {
        classes.push("is-folded");
        const lostAmt = Math.abs(p.lastHandDelta || p.lastHandBet || 0);
        outcomeBadgeHtml = `<div class="seat-outcome-badge badge-fold">🏳️ FOLD${lostAmt > 0 ? ' -' + fmt(lostAmt) : ''}</div>`;
      }
    } else {
      if (p.status === "folded" || p.status === "out") classes.push("is-folded");
      if (p.status === "all_in") classes.push("is-allin");
    }
    if (isMe) classes.push("is-me");

    const badges = [];
    if (isMe) badges.push(`<span class="badge-role" style="background:#10b981;color:#fff;">BẠN</span>`);
    if (p.id === mvpPlayerId) badges.push(`<span class="badge-role" style="background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff;" title="Dẫn đầu lợi nhuận">👑 MVP</span>`);
    if (p.isDealer) badges.push(`<span class="badge-role badge-d" title="Dealer Button">D</span>`);
    if (p.isSB) badges.push(`<span class="badge-role badge-sb" title="Small Blind">SB</span>`);
    if (p.isBB) badges.push(`<span class="badge-role badge-bb" title="Big Blind">BB</span>`);

    let holeCardsHtml = "";
    const prevState = isNewHand ? "empty" : (cardAnimTracker.seatCardState[p.id] || "empty");
    if (p.holeCards && p.holeCards.length === 2) {
      const curState = (p.holeCards[0].hidden && p.holeCards[1].hidden) ? "hidden" : "faceup";
      let animClass = "";
      if (prevState === "empty") animClass = "animate-deal";
      else if (prevState === "hidden" && curState === "faceup") animClass = "animate-flip";
      cardAnimTracker.seatCardState[p.id] = curState;

      holeCardsHtml = `
        <div class="seat-hole-cards">
          ${p.holeCards.map((c, idx) => renderCardHtml(c, true, !c.hidden && winSet.has(c.code), animClass, animClass ? idx * 90 : 0)).join("")}
        </div>
      `;
    } else {
      cardAnimTracker.seatCardState[p.id] = "empty";
    }

    let evalTag = "";
    if (p.handEval && p.handEval.name && p.status !== "folded") {
      evalTag = `<div class="seat-hand-eval-tag">${escapeHtml(p.handEval.name)}</div>`;
    }

    let equityPillHtml = "";
    if (p.equityPct !== null && p.equityPct !== undefined && (t.allInRunout || t.street === "showdown")) {
      equityPillHtml = `<div class="seat-equity-pill">🎯 Thắng: ${p.equityPct}%</div>`;
    }

    let timerRowHtml = "";
    if (p.isTurn && turnTimerState.active && !t.allInRunout) {
      const secLeft = Math.ceil(turnTimerState.remainingMs / 1000);
      const pct = Math.max(0, Math.min(100, (turnTimerState.remainingMs / turnTimerState.totalMs) * 100));
      timerRowHtml = `
        <div class="seat-timer-row">
          <div class="seat-timer-track">
            <div class="seat-timer-fill live-seat-timer-fill" style="width: ${pct.toFixed(1)}%;"></div>
          </div>
          <span class="seat-timer-sec live-seat-timer-sec">${secLeft}s</span>
        </div>
      `;
    }

    const betBubble = p.currentBet > 0
      ? `<div class="seat-bet-bubble">🪙 ${fmt(p.currentBet)}</div>`
      : "";

    let readyPillHtml = "";
    if (isPostHand || t.street === "idle") {
      if (p.stack > 0 && !p.sittingOut) {
        if (p.readyNext) {
          readyPillHtml = `<div class="seat-ready-pill is-ready">✅ Sẵn sàng</div>`;
        } else {
          readyPillHtml = `<div class="seat-ready-pill is-waiting">⏳ Chưa sẵn sàng</div>`;
        }
      }
    }

    return `
      <div class="${classes.join(' ')}" style="left: ${pos.left}; top: ${pos.top}; transform: translate(-50%, -50%);" onclick="onSeatNodeClick('${p.id}')">
        ${outcomeBadgeHtml}
        ${readyPillHtml}
        ${holeCardsHtml}
        <div class="seat-top-row">
          <div class="seat-name-wrap">
            <span>${escapeHtml(p.avatar)}</span>
            <span title="Ghế #${p.seat + 1}: ${escapeHtml(p.name)}">${escapeHtml(p.name)}</span>
          </div>
          <div class="role-badges">${badges.join("")}</div>
        </div>
        <div class="seat-stack-row">
          <span>${fmt(p.stack)}</span>
          <span style="font-size: 10px; color: #94a3b8;">#${p.seat + 1}</span>
        </div>
        <div class="seat-action-tag">${escapeHtml(p.lastAction || "Sẵn sàng")}</div>
        ${equityPillHtml}
        ${timerRowHtml}
        ${evalTag}
        ${betBubble}
      </div>
    `;
  }).join("");
}

window.onSeatNodeClick = function(playerId) {
  openLedgerModal("tabOverview", playerId);
};

// ------------------------------------------------------------------
// Private Hole Cards Box
// ------------------------------------------------------------------
function renderMyHoleCardsBox(t) {
  const myPlayer = roomState.myPlayerId
    ? t.players.find((x) => x.id === roomState.myPlayerId)
    : null;

  if (!myPlayer) {
    myDeckCardsContainer.innerHTML = `
      <div class="playing-card mini card-slot-empty">♠</div>
      <div class="playing-card mini card-slot-empty">♥</div>
    `;
    myHandOwnerLabel.textContent = "👀 Chế độ Khán giả:";
    myLiveHandRankText.textContent = "Bấm 'Ngồi Vào Bàn' để nhận bài";
    myDrawHintBadge.style.display = "none";
    btnRevealCard0.disabled = true;
    btnRevealCard1.disabled = true;
    btnRevealMyCards.disabled = true;
    return;
  }

  if (!myPlayer.holeCards || myPlayer.holeCards.length === 0) {
    myDeckCardsContainer.innerHTML = `
      <div class="playing-card mini card-slot-empty">♠</div>
      <div class="playing-card mini card-slot-empty">♥</div>
    `;
    myHandOwnerLabel.textContent = `🔒 Bài tẩy của bạn (${myPlayer.name} - Ghế #${myPlayer.seat + 1}):`;
    myLiveHandRankText.textContent = "Chưa chia bài";
    myDrawHintBadge.style.display = "none";
    btnRevealCard0.disabled = true;
    btnRevealCard1.disabled = true;
    btnRevealMyCards.disabled = true;
    return;
  }

  const winSet = new Set(t.winningCards || []);
  const isNewDeal = cardAnimTracker.myHandDealtNo !== t.handNumber;
  cardAnimTracker.myHandDealtNo = t.handNumber;
  const animClass = isNewDeal ? "animate-deal" : "";

  myDeckCardsContainer.innerHTML = myPlayer.holeCards
    .map((c, idx) => renderCardHtml(c, false, !c.hidden && winSet.has(c.code), animClass, isNewDeal ? idx * 120 : 0))
    .join("");
  myHandOwnerLabel.textContent = `🔒 Bài tẩy của bạn (${myPlayer.name} - Ghế #${myPlayer.seat + 1}):`;
  myLiveHandRankText.textContent = myPlayer.handEval?.name || "Đang tính điểm...";

  const drawHint = myPlayer.handEval?.drawHint || "";
  if (drawHint && t.street !== "showdown" && t.street !== "idle") {
    myDrawHintBadge.style.display = "inline-block";
    myDrawHintBadge.textContent = drawHint;
  } else {
    myDrawHintBadge.style.display = "none";
  }

  const mask = myPlayer.revealedMask || [false, false];
  btnRevealCard0.disabled = Boolean(mask[0] || myPlayer.revealed);
  btnRevealCard1.disabled = Boolean(mask[1] || myPlayer.revealed);
  btnRevealMyCards.disabled = Boolean((mask[0] && mask[1]) || myPlayer.revealed);
}

btnRevealCard0.addEventListener("click", () => {
  if (roomState?.myPlayerId) send({ type: "reveal_cards", cardIndex: 0 });
});

btnRevealCard1.addEventListener("click", () => {
  if (roomState?.myPlayerId) send({ type: "reveal_cards", cardIndex: 1 });
});

btnRevealMyCards.addEventListener("click", () => {
  if (roomState?.myPlayerId) send({ type: "reveal_cards" });
});

// ------------------------------------------------------------------
// Pre-Action Queue Logic
// ------------------------------------------------------------------
function syncPreActionUI(t, myPlayer, isMyTurn) {
  if (
    !myPlayer ||
    myPlayer.status !== "active" ||
    t.street === "idle" ||
    t.street === "showdown" ||
    t.allInRunout
  ) {
    preActionState.selected = null;
    preActionBar.classList.remove("show");
    return;
  }

  if (preActionState.handNumber !== t.handNumber || preActionState.street !== t.street) {
    preActionState.selected = null;
    preActionState.handNumber = t.handNumber;
    preActionState.street = t.street;
  }

  if (isMyTurn) {
    preActionBar.classList.remove("show");
    if (preActionState.selected && !preActionState.executing && t.turnConstraints) {
      const chosen = preActionState.selected;
      const tc = t.turnConstraints;
      preActionState.selected = null;
      preActionState.executing = true;
      updatePreActionButtonsUI();
      setTimeout(() => {
        preActionState.executing = false;
        if (!roomState?.table?.isMyTurn) return;
        if (chosen === "check_fold") {
          send({ type: "player_action", action: tc.canCheck ? "check" : "fold" });
        } else if (chosen === "check") {
          if (tc.canCheck) {
            send({ type: "player_action", action: "check" });
          } else {
            showToast("⚠️ Có người đã tố thêm — hãy tự chọn Theo hoặc Bỏ bài!");
          }
        } else if (chosen === "call_any") {
          send({ type: "player_action", action: tc.canCheck ? "check" : "call" });
        }
      }, 220);
    }
    return;
  }

  preActionBar.classList.add("show");
  updatePreActionButtonsUI();
}

function updatePreActionButtonsUI() {
  document.querySelectorAll("#preActionBar .pre-action-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.pre === preActionState.selected);
  });
}

document.querySelectorAll("#preActionBar .pre-action-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const val = btn.dataset.pre;
    preActionState.selected = preActionState.selected === val ? null : val;
    updatePreActionButtonsUI();
  });
});

// ------------------------------------------------------------------
// Betting Controls Deck
// ------------------------------------------------------------------
function renderBettingDeck(t) {
  const c = t.turnConstraints;
  const s = t.settings;
  const myPlayer = t.players.find((x) => x.id === roomState.myPlayerId);

  const isMyTurn = Boolean(c && t.isMyTurn && c.playerId === roomState.myPlayerId);
  syncPreActionUI(t, myPlayer, isMyTurn);

  if (t.allInRunout) {
    bettingDeck.classList.remove("active-deck");
    actorNameBadge.textContent = "🔥 ALL-IN! Đang mở bài chung từ từ...";
    actorStackInfo.textContent = "Tất cả người chơi đã All-in!";
    btnActFold.disabled = true;
    btnActCheckCall.disabled = true;
    btnActRaise.disabled = true;
    btnActAllIn.disabled = true;
    raiseSlider.disabled = true;
    raiseNumberInput.disabled = true;
    document.querySelectorAll(".btn-preset").forEach((b) => (b.disabled = true));
    return;
  }

  if (!c || t.street === "idle" || t.street === "showdown") {
    bettingDeck.classList.remove("active-deck");
    actorNameBadge.textContent = t.street === "showdown" ? "🏆 Đã lật bài Showdown!" : "Chưa trong vòng cược";
    actorStackInfo.textContent = myPlayer
      ? `Số dư của bạn: ${fmt(myPlayer.stack)} ${s.currency}`
      : "Sẵn sàng ván mới";
    btnActFold.disabled = true;
    btnActCheckCall.disabled = true;
    btnActRaise.disabled = true;
    btnActAllIn.disabled = true;
    raiseSlider.disabled = true;
    raiseNumberInput.disabled = true;
    document.querySelectorAll(".btn-preset").forEach((b) => (b.disabled = true));
    return;
  }

  if (!isMyTurn) {
    bettingDeck.classList.remove("active-deck");
    actorNameBadge.textContent = `⏳ Đang chờ lượt của ${c.playerName} (Ghế #${c.seat + 1})${c.isBot ? ' · 🤖 Bot...' : ''}`;
    actorStackInfo.textContent = myPlayer
      ? `Số dư: ${fmt(myPlayer.stack)} ${s.currency} | Đã cược vòng này: ${fmt(myPlayer.currentBet)}`
      : `Đang chờ ${c.playerName}...`;

    btnActFold.disabled = true;
    btnActCheckCall.disabled = true;
    btnActRaise.disabled = true;
    btnActAllIn.disabled = true;
    raiseSlider.disabled = true;
    raiseNumberInput.disabled = true;
    document.querySelectorAll(".btn-preset").forEach((b) => (b.disabled = true));
    minRaiseHintText.textContent = `Chưa đến lượt của bạn`;
    return;
  }

  // It is this player's turn!
  bettingDeck.classList.add("active-deck");
  actorNameBadge.textContent = `🔥 ĐẾN LƯỢT BẠN (${c.playerName} - Ghế #${c.seat + 1})`;
  actorStackInfo.textContent = `Số dư: ${fmt(c.stack)} ${s.currency} | Đã đóng: ${fmt(c.currentBet)} ${s.currency}`;

  btnActFold.disabled = false;
  btnActCheckCall.disabled = false;
  btnActAllIn.disabled = c.stack <= 0;

  if (c.canCheck) {
    lblCheckCall.textContent = "✔️ CHECK";
    subCheckCall.textContent = "Xem bài (0)";
  } else {
    lblCheckCall.textContent = c.toCall >= c.stack ? "📞 CALL ALL-IN" : "📞 CALL (THEO)";
    subCheckCall.textContent = `+${fmt(c.toCall)} (Lên ${fmt(c.currentBet + c.toCall)})`;
  }

  subAllIn.textContent = `Tất tay (${fmt(c.maxRaiseTarget)})`;

  if (c.canRaise) {
    btnActRaise.disabled = false;
    raiseSlider.disabled = false;
    raiseNumberInput.disabled = false;
    document.querySelectorAll(".btn-preset").forEach((b) => (b.disabled = false));

    const step = Math.max(1, Math.floor(s.smallBlind / 2));
    raiseSlider.min = c.minRaiseTarget;
    raiseSlider.max = c.maxRaiseTarget;
    raiseSlider.step = step;

    let currentVal = parseInt(raiseNumberInput.value, 10) || c.minRaiseTarget;
    if (currentVal < c.minRaiseTarget || currentVal > c.maxRaiseTarget || raiseSlider.dataset.turnPlayer !== c.playerId) {
      currentVal = c.minRaiseTarget;
      raiseSlider.dataset.turnPlayer = c.playerId;
    }
    setRaiseTargetValue(currentVal);
    minRaiseHintText.textContent = `Tố tối thiểu lên: ${fmt(c.minRaiseTarget)} | Tối đa: ${fmt(c.maxRaiseTarget)} ${s.currency}`;
  } else {
    btnActRaise.disabled = true;
    raiseSlider.disabled = true;
    raiseNumberInput.disabled = true;
    document.querySelectorAll(".btn-preset").forEach((b) => (b.disabled = true));
    lblRaise.textContent = "🚀 RAISE";
    subRaise.textContent = "Không đủ chip tố";
  }
}

function setRaiseTargetValue(val) {
  const c = roomState?.table?.turnConstraints;
  if (!c) return;
  const clamped = Math.max(c.minRaiseTarget, Math.min(c.maxRaiseTarget, Math.round(Number(val) || c.minRaiseTarget)));
  raiseSlider.value = clamped;
  raiseNumberInput.value = clamped;
  const verb = c.tableCurrentBet === 0 ? "BET LÊN" : "RAISE LÊN";
  const added = Math.max(0, clamped - c.currentBet);
  lblRaise.textContent = clamped >= c.maxRaiseTarget ? "🔥 ALL-IN" : `🚀 ${verb}`;
  subRaise.textContent = `${fmt(clamped)} (+${fmt(added)})`;
}

raiseSlider.addEventListener("input", (e) => setRaiseTargetValue(e.target.value));

raiseNumberInput.addEventListener("input", (e) => {
  const val = parseInt(e.target.value, 10);
  if (!isNaN(val)) {
    const c = roomState?.table?.turnConstraints;
    if (c) {
      const added = Math.max(0, val - c.currentBet);
      lblRaise.textContent = val >= c.maxRaiseTarget ? "🔥 ALL-IN" : `🚀 ${c.tableCurrentBet === 0 ? 'BET LÊN' : 'RAISE LÊN'}`;
      subRaise.textContent = `${fmt(val)} (+${fmt(added)})`;
    }
  }
});

document.querySelectorAll(".btn-preset[data-preset]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const c = roomState?.table?.turnConstraints;
    if (!c || !c.presets) return;
    const p = btn.dataset.preset;
    if (p === "min") setRaiseTargetValue(c.presets.minRaise);
    else if (p === "half") setRaiseTargetValue(c.presets.halfPot);
    else if (p === "twothird") setRaiseTargetValue(c.presets.twoThirdPot);
    else if (p === "pot") setRaiseTargetValue(c.presets.fullPot);
    else if (p === "max") setRaiseTargetValue(c.presets.allIn);
  });
});

btnActFold.addEventListener("click", () => send({ type: "player_action", action: "fold" }));
btnActCheckCall.addEventListener("click", () => {
  const c = roomState?.table?.turnConstraints;
  if (!c) return;
  send({ type: "player_action", action: c.canCheck ? "check" : "call" });
});
btnActRaise.addEventListener("click", () => {
  const c = roomState?.table?.turnConstraints;
  if (!c) return;
  const targetAmount = parseInt(raiseNumberInput.value, 10) || c.minRaiseTarget;
  send({ type: "player_action", action: "raise", amount: targetAmount });
});
btnActAllIn.addEventListener("click", () => send({ type: "player_action", action: "all_in" }));

// ------------------------------------------------------------------
// In-Game Player List & Logs
// ------------------------------------------------------------------
function renderSidebarPlayers(t) {
  const currency = t.settings.currency;
  const isHost = Boolean(roomState.isHost);
  const myId = roomState.myPlayerId;

  sidebarPlayerList.innerHTML = t.players.map((p) => {
    const isMe = p.id === myId;
    const net = p.netProfit;
    const netClass = net > 0 ? "profit-pos" : net < 0 ? "profit-neg" : "profit-zero";
    const netStr = (net > 0 ? "+" : "") + fmt(net);
    const badges = [];
    if (isMe) badges.push(`<span class="badge-role" style="background:#10b981;color:#fff;">BẠN</span>`);
    if (p.isDealer) badges.push(`<span class="badge-role badge-d">D</span>`);
    if (p.isSB) badges.push(`<span class="badge-role badge-sb">SB</span>`);
    if (p.isBB) badges.push(`<span class="badge-role badge-bb">BB</span>`);

    const actionBtns = [];
    if (isMe || isHost) {
      actionBtns.push(`<button class="btn-mini" onclick="quickRebuyFor('${p.id}')">➕ Nạp</button>`);
    }
    if (isHost && (t.street === "idle" || t.street === "showdown")) {
      actionBtns.push(`<button class="btn-mini" onclick="setDealerSeat(${p.seat})" title="Đặt làm Dealer (D)">🔘 D</button>`);
    }
    if (isHost || isMe) {
      actionBtns.push(`<button class="btn-mini danger" onclick="removePlayer('${p.id}')" title="Xóa khỏi bàn">✕</button>`);
    }

    return `
      <div class="sidebar-player-item ${p.isTurn ? 'active-turn' : ''}">
        <div class="sidebar-player-top">
          <div class="sidebar-player-name">
            <span>${escapeHtml(p.avatar)}</span>
            <span>${escapeHtml(p.name)}</span>
            ${badges.join("")}
          </div>
          <div class="sidebar-player-stack">${fmt(p.stack)} ${escapeHtml(currency)}</div>
        </div>
        <div class="sidebar-player-meta">
          <span>Vốn: <b>${fmt(p.totalBuyIn)}</b></span>
          <span class="${netClass}">Lời: ${netStr}</span>
          ${(t.street === "idle" || t.street === "showdown") && p.stack > 0 && !p.sittingOut
            ? (p.readyNext ? '<span style="color:#34d399;font-size:11px;font-weight:700;">✅ Đã sẵn sàng</span>' : '<span style="color:#94a3b8;font-size:11px;">⏳ Chưa sẵn sàng</span>')
            : ''}
        </div>
        <div class="mini-actions">
          ${actionBtns.join("")}
        </div>
      </div>
    `;
  }).join("");
}

window.quickRebuyFor = function(playerId) {
  openLedgerModal("tabRebuy", playerId);
};

window.setDealerSeat = function(seat) {
  send({ type: "set_dealer", seat });
};

window.removePlayer = function(playerId) {
  const p = roomState?.table?.players?.find((x) => x.id === playerId);
  if (!p) return;
  if (confirm(`Rời khỏi ghế "${p.name}"?`)) {
    send({ type: "remove_player", playerId });
  }
};

function renderLogsAndHistory(t) {
  const logs = t.actionLog || [];
  logCountBadge.textContent = `${logs.length}`;
  if (logs.length === 0) {
    actionLogContainer.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 16px; font-size: 12px;">Chưa có hành động nào.</div>`;
  } else {
    actionLogContainer.innerHTML = [...logs].reverse().map((item) => `
      <div style="font-size: 12px; margin-bottom: 4px; padding: 3px 0; border-bottom: 1px dashed rgba(255,255,255,0.08);">
        <span style="color: var(--text-muted); font-family: monospace;">[${escapeHtml(item.time)}]</span>
        <span>${escapeHtml(item.text)}</span>
      </div>
    `).join("");
  }

  const hands = t.handHistory || [];
  if (hands.length === 0) {
    handHistoryContainer.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 14px; font-size: 12px;">Chưa có ván nào hoàn tất.</div>`;
  } else {
    handHistoryContainer.innerHTML = [...hands].reverse().map((h) => `
      <div style="font-size: 12px; margin-bottom: 6px; padding: 4px 6px; background: rgba(148,163,184,0.06); border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; font-weight: 800;">
          <span>Ván #${h.hand} (${escapeHtml(h.time)})</span>
          <span class="mono" style="color:#10b981;">+${fmt(h.totalPot)}</span>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(h.reason)}</div>
      </div>
    `).join("");
  }
}

// ------------------------------------------------------------------
// Ledger, Settings, Rebuy Modals
// ------------------------------------------------------------------
function openLedgerModal(defaultTab = "tabOverview", preselectPlayerId = null) {
  if (!roomState || !roomState.table) {
    showToast("Hãy vào phòng trước!");
    return;
  }
  switchLedgerTab(defaultTab);
  renderLedgerModalContent(preselectPlayerId);
  ledgerModal.classList.add("open");
}

function switchLedgerTab(tabId) {
  document.querySelectorAll("#ledgerModal .tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll("#ledgerModal .ledger-tab-pane").forEach((pane) => {
    pane.style.display = pane.id === tabId ? "block" : "none";
  });
}

document.querySelectorAll("#ledgerModal .tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchLedgerTab(btn.dataset.tab));
});

function renderLedgerModalContent(preselectPlayerId = null) {
  if (!roomState || !roomState.table) return;
  const t = roomState.table;
  const currency = t.settings.currency;
  const isHost = Boolean(roomState.isHost);

  hostAdjustBox.style.display = isHost ? "block" : "none";

  ledgerOverviewBody.innerHTML = t.players.map((p) => {
    const net = p.netProfit;
    const netClass = net > 0 ? "profit-pos" : net < 0 ? "profit-neg" : "profit-zero";
    const netStr = (net > 0 ? "+" : "") + fmt(net);
    const totalNow = p.stack + p.totalHandBet;
    const canRebuyThis = isHost || p.id === roomState.myPlayerId;
    return `
      <tr>
        <td><b>${escapeHtml(p.avatar)} ${escapeHtml(p.name)}</b></td>
        <td class="mono">${fmt(p.totalBuyIn)}</td>
        <td class="mono"><b>${fmt(totalNow)}</b></td>
        <td class="mono ${netClass}">${netStr} ${escapeHtml(currency)}</td>
        <td>
          ${canRebuyThis ? `<button class="btn-mini" onclick="openLedgerModal('tabRebuy', '${p.id}')">+ Nạp</button>` : `<span style="color:var(--text-muted);font-size:11px;">--</span>`}
        </td>
      </tr>
    `;
  }).join("");

  const settlements = t.settlement || [];
  if (settlements.length === 0) {
    settlementListContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 12.5px;">Tất cả người chơi đang hòa vốn hoặc chưa phát sinh chênh lệch.</span>`;
  } else {
    settlementListContainer.innerHTML = settlements.map((item) => `
      <div style="display: flex; align-items: center; justify-content: space-between; background: var(--bg-card); padding: 7px 11px; border-radius: 8px; border: 1px solid var(--border-color); font-size: 12.5px;">
        <span>💸 <b>${escapeHtml(item.from)}</b> chuyển trả <b>${escapeHtml(item.to)}</b></span>
        <strong class="mono" style="color: #f59e0b;">${fmt(item.amount)} ${escapeHtml(currency)}</strong>
      </div>
    `).join("");
  }

  const prevRebuyPid = preselectPlayerId || roomState.myPlayerId || rebuyPlayerSelect.value;
  const optionsHtml = t.players.map((p) => `
    <option value="${p.id}">${escapeHtml(p.avatar)} ${escapeHtml(p.name)} (Số dư: ${fmt(p.stack)})</option>
  `).join("");

  rebuyPlayerSelect.innerHTML = optionsHtml;
  transferFromSelect.innerHTML = optionsHtml;
  transferToSelect.innerHTML = optionsHtml;

  if (prevRebuyPid && t.players.some((p) => p.id === prevRebuyPid)) {
    rebuyPlayerSelect.value = prevRebuyPid;
  }
  if (roomState.myPlayerId && t.players.some((p) => p.id === roomState.myPlayerId)) {
    transferFromSelect.value = roomState.myPlayerId;
  }
  if (t.players.length > 1 && transferFromSelect.value === transferToSelect.value) {
    transferToSelect.selectedIndex = transferFromSelect.selectedIndex === 0 ? 1 : 0;
  }

  const selPlayer = t.players.find((p) => p.id === rebuyPlayerSelect.value);
  if (selPlayer) adjustStackInput.value = selPlayer.stack;
}

rebuyPlayerSelect.addEventListener("change", () => {
  const p = roomState?.table?.players?.find((x) => x.id === rebuyPlayerSelect.value);
  if (p) adjustStackInput.value = p.stack;
});

document.querySelectorAll(".rebuy-quick-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    rebuyAmountInput.value = btn.dataset.amt;
  });
});

document.getElementById("btnConfirmRebuy").addEventListener("click", () => {
  const pid = rebuyPlayerSelect.value;
  const amount = parseInt(rebuyAmountInput.value, 10) || 0;
  send({ type: "rebuy", playerId: pid, amount });
});

document.getElementById("btnConfirmAdjustStack").addEventListener("click", () => {
  const pid = rebuyPlayerSelect.value;
  const newStack = parseInt(adjustStackInput.value, 10) || 0;
  const updateBuyIn = adjustUpdateBuyInCheck.checked;
  send({ type: "adjust_stack", playerId: pid, newStack, updateBuyIn });
});

document.getElementById("btnConfirmTransfer").addEventListener("click", () => {
  send({
    type: "transfer_chips",
    fromId: transferFromSelect.value,
    toId: transferToSelect.value,
    amount: parseInt(transferAmountInput.value, 10) || 0,
    note: transferNoteInput.value.trim(),
  });
  transferNoteInput.value = "";
});

document.getElementById("btnOpenLedger").addEventListener("click", () => openLedgerModal("tabOverview"));
document.getElementById("btnQuickRebuyNav").addEventListener("click", () => openLedgerModal("tabRebuy", roomState?.myPlayerId));
document.getElementById("btnCloseLedgerModal").addEventListener("click", () => ledgerModal.classList.remove("open"));

// Table Settings Modal
document.getElementById("btnOpenSettings").addEventListener("click", () => {
  if (!roomState || !roomState.table) {
    showToast("Hãy vào phòng trước!");
    return;
  }
  const s = roomState.table.settings;
  setSmallBlind.value = s.smallBlind;
  setBigBlind.value = s.bigBlind;
  setAnte.value = s.ante;
  setDefaultBuyIn.value = s.defaultBuyIn;
  setTurnTimeout.value = String(s.turnTimeout || 20);
  setCurrency.value = s.currency;
  settingsModal.classList.add("open");
});

document.querySelectorAll(".blind-preset-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    setSmallBlind.value = btn.dataset.sb;
    setBigBlind.value = btn.dataset.bb;
    setDefaultBuyIn.value = btn.dataset.buyin;
  });
});

document.getElementById("btnCloseSettingsModal").addEventListener("click", () => settingsModal.classList.remove("open"));
document.getElementById("btnCancelSettings").addEventListener("click", () => settingsModal.classList.remove("open"));

document.getElementById("btnSaveSettings").addEventListener("click", () => {
  send({
    type: "update_settings",
    smallBlind: parseInt(setSmallBlind.value, 10) || 1000,
    bigBlind: parseInt(setBigBlind.value, 10) || 2000,
    ante: parseInt(setAnte.value, 10) || 0,
    defaultBuyIn: parseInt(setDefaultBuyIn.value, 10) || 100000,
    turnTimeout: parseInt(setTurnTimeout.value, 10) || 20,
    currency: setCurrency.value,
  });
  settingsModal.classList.remove("open");
});

// Interactive Props & Chat
document.querySelectorAll(".btn-emoji:not(.prop-throw-btn)").forEach((btn) => {
  btn.addEventListener("click", () => send({ type: "chat", emoji: btn.dataset.emoji }));
});

document.querySelectorAll(".prop-throw-btn").forEach((btn) => {
  btn.addEventListener("click", () => send({ type: "throw_item", emoji: btn.dataset.prop }));
});

document.getElementById("btnSendChat").addEventListener("click", sendChatText);
document.getElementById("chatTextInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendChatText();
});

function sendChatText() {
  const inp = document.getElementById("chatTextInput");
  const text = inp.value.trim();
  if (!text) return;
  send({ type: "chat", text });
  inp.value = "";
}

function showFloatingReaction(data) {
  const bubble = document.createElement("div");
  bubble.className = "reaction-bubble";
  const content = [data.emoji, data.text].filter(Boolean).join(" ");
  bubble.textContent = `${data.sender || "Người chơi"}: ${content}`;
  reactionOverlay.appendChild(bubble);
  playSound("check");
  setTimeout(() => bubble.remove(), 2400);
}

function showFlyingProp(data) {
  const tableArena = document.getElementById("pokerArena");
  if (!tableArena) return;
  const fromPos = SEAT_POSITIONS[(data.fromSeat || 0) % SEAT_POSITIONS.length] || { left: "50%", top: "90%" };
  const toPos = SEAT_POSITIONS[(data.toSeat || 0) % SEAT_POSITIONS.length] || { left: "50%", top: "10%" };

  const propEl = document.createElement("div");
  propEl.className = "flying-prop";
  propEl.textContent = data.emoji || "🍺";
  propEl.style.left = fromPos.left;
  propEl.style.top = fromPos.top;
  propEl.style.transform = "translate(-50%, -50%) scale(0.75) rotate(0deg)";
  tableArena.appendChild(propEl);

  playSound("chip");
  showToast(`${data.fromName || "Người chơi"} vừa ném ${data.emoji || "🍺"}!`);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      propEl.style.left = toPos.left;
      propEl.style.top = toPos.top;
      propEl.style.transform = "translate(-50%, -50%) scale(1.4) rotate(360deg)";
    });
  });

  setTimeout(() => {
    propEl.style.opacity = "0";
    propEl.style.transform = "translate(-50%, -50%) scale(2) rotate(420deg)";
  }, 650);
  setTimeout(() => propEl.remove(), 950);
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Boot
syncIdentityUI();
applyTheme();
setInRoomMode(false);
connect();
