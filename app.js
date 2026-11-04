/* 굿모닝 노동법! — 주제 고르기 · 진행 · 채점 · 하트 · 레벨 · 결과 · 공유
 *
 * 계산은 전부 여기서 끝난다. 서버는 부르지 않는다.
 * 원본 데이터는 이 앱에 들어오지 않는다 — topics/*.json 에 정답과 근거만 있다.
 */

const $ = (id) => document.getElementById(id);
const views = { home: $("view-home"), quiz: $("view-quiz"), result: $("view-result") };

let INDEX = null;     // topics.json
let PACK = null;      // 지금 푸는 주제
let idx = 0;
let answers = [];

const DONE_KEY = "gam-test-done";

/* 푼 주제를 기억한다. 이 브라우저 안에만 남고 서버로 가지 않는다.
   시크릿 창이나 저장소 차단 환경에서는 읽기·쓰기가 막히므로 감싼다. */
function doneMap() {
  try { return JSON.parse(localStorage.getItem(DONE_KEY) || "{}"); }
  catch { return {}; }
}
function markDone(id, score) {
  try {
    const m = doneMap();
    m[id] = Math.max(score, m[id] ?? 0);
    localStorage.setItem(DONE_KEY, JSON.stringify(m));
  } catch { /* 저장이 막혀 있어도 앱은 그대로 돈다 */ }
}

/* 문항마다 한 번이라도 맞혔는지 — «틀린 문제만 다시 풀기»가 여기서 고른다. { 주제: { 문항 id: true | false } }
   자리(몇 번째) 대신 문항 id 로 적어, 스테이지 안 문항 순서를 바꿔도 기록이 어긋나지 않는다 */
const HITS_KEY = "gam-test-hits-by-id";
const FREEPASS_KEY = "gam-test-freepass";     // 출근 완료 프리패스권을 썼는지
const SOUND_KEY = "gam-test-sound";           // "off" 면 빵빠레를 울리지 않는다
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* 저장이 막혀 있어도 앱은 그대로 돈다 */ } },
};
/* 이번 결과를 더한다(한 번 맞힌 문항은 맞힌 채로 남는다).
   그 주제의 맞힌 문항 수와, 이번에 틀림 → 맞힘으로 바뀌었는지를 돌려준다 */
function addHit(id, qid, hit) {
  const m = store.get(HITS_KEY, {});
  const row = m[id] ?? {};
  const flipped = row[qid] === false && hit;
  row[qid] = row[qid] === true || hit;
  m[id] = row;
  store.set(HITS_KEY, m);
  return { count: Object.values(row).filter(Boolean).length, flipped };
}
/* 다시 풀 틀린 문항 — 스테이지 순서, 그 안에서는 문항 순서대로. 아직 한 번도 못 맞힌 문항만 */
function wrongList() {
  const m = store.get(HITS_KEY, {});
  return INDEX.topics.flatMap((t) =>
    (t.qids ?? []).filter((q) => m[t.id]?.[q] === false).map((qid) => ({ id: t.id, qid })));
}

/* ── 하트 · 레벨 ─────────────────────────────────────
 * 한 문항에 하트 1개 — 택1은 맞히면, 슬라이더는 오차 20% 안이면.
 * 주제마다 «한 번이라도 맞힌 문항 수»(최대 5)를 하트로 남기고, 그 합으로 레벨을 정한다.
 * 틀린 문항을 다시 풀어 맞히면 그 주제의 하트가 채워진다.
 */
const HEART_KEY = "gam-test-hearts";
const HEART_PCT = 20;
const PER_LEVEL = 5;
// 하트 5개마다 한 직급 — 12스테이지 × 5문제 = 하트 60개로 마지막 직급(13번째)에 닿게 13개로 맞춘다
const RANKS = ["인턴", "수습사원", "사원", "주임", "대리", "과장", "차장",
               "부장", "이사", "상무", "전무", "사장", "대표이사"];
let stageHits = [];

function heartMap() {
  try { return JSON.parse(localStorage.getItem(HEART_KEY) || "{}"); }
  catch { return {}; }
}
function saveHearts(id, n) {
  try {
    const m = heartMap();
    m[id] = Math.max(n, m[id] ?? 0);
    localStorage.setItem(HEART_KEY, JSON.stringify(m));
  } catch { /* 저장이 막혀 있어도 앱은 그대로 돈다 */ }
}
/* 지금 목록에 있는 주제의 하트만 센다 — 합치거나 뺀 주제의 하트가 레벨에 남지 않게 */
function totalHearts(m = heartMap()) {
  return INDEX.topics.reduce((a, t) => a + (m[t.id] ?? 0), 0);
}
function levelOf(total) {
  const lv = Math.min(RANKS.length, Math.floor(total / PER_LEVEL) + 1);
  const into = lv === RANKS.length ? PER_LEVEL : total - (lv - 1) * PER_LEVEL;
  return { lv, rank: RANKS[lv - 1], pct: into / PER_LEVEL * 100 };
}
function isHit(q, mine) {
  return q.type === "choice" ? mine === q.answer : errPct(q, mine) <= HEART_PCT;
}
const heartSvg = (full) =>
  `<svg class="hp${full ? "" : " off"}"><use href="#px-heart${full ? "" : "-empty"}"/></svg>`;

function renderHud() {
  const total = totalHearts();
  const L = levelOf(total);
  $("hud-lv").textContent = `LV ${L.lv}`;
  $("hud-title").textContent = L.rank;
  $("hud-xp").style.width = `${L.pct}%`;
  $("hud-total").textContent = total;
}
/* 승진 창 — 마지막 직급(대표이사)에 오르면 «다음 승진»이 없으니 문구를 바꾼다 */
function showLevelup(from, to) {
  const top = to === RANKS.length;
  $("lu-sub").textContent = top ? "축하합니다! 최고 직급에 올랐어요" : "축하합니다! 승진했어요";
  $("lu-lv").textContent = `LV ${from} ▶ LV ${to}`;
  $("lu-title").textContent = RANKS[to - 1];
  $("lu-ok").textContent = top ? "대표이사로 취임하기 ▶" : "다음 승진 도전 ▶";
  $("lu-confetti").innerHTML = "";
  $("levelup").hidden = false;
  fitOverlays();
  $("lu-ok").focus();                              // 뜨자마자 Enter 로 닫을 수 있게
  if (top) { confetti($("lu-confetti")); fanfare(); }   // 대표이사 취임은 출근 완료처럼 꽃가루 · 빵빠레
}
function renderStageHearts() {
  $("stage-hearts").innerHTML = PACK.questions
    .map((_, i) => heartSvg(stageHits[i] === true)).join("");
}
function toast(hit) {
  const t = $("toast");
  t.className = "toast " + (hit ? "good" : "bad");
  t.innerHTML = hit ? `${heartSvg(true)} +1` : "MISS";
  t.hidden = false;
  fitOverlays();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 750);
}

/* ── 채점 ────────────────────────────────────────────
 * 택1     맞으면 100, 틀리면 0
 * 슬라이더 오차율 × 200 만큼 깎는다 (10% 빗나가면 80점)
 */
function scoreOne(q, mine) {
  if (q.type === "choice") return mine === q.answer ? 100 : 0;
  const err = Math.abs(mine - q.answer) / Math.abs(q.answer);
  return Math.max(0, Math.round(100 - err * 200));
}
function errPct(q, mine) {
  if (q.type === "choice") return mine === q.answer ? 0 : 100;
  return Math.abs(mine - q.answer) / Math.abs(q.answer) * 100;
}
function gradeOf(s) {
  return INDEX.grades.find((g) => s >= g.min) || INDEX.grades.at(-1);
}
function reactionOf(q, mine, pct) {
  if (q.type === "choice") {
    return mine === q.answer ? INDEX.reactions_choice.hit
                             : INDEX.reactions_choice.miss;
  }
  return (INDEX.reactions.find((r) => pct <= r.max) || { text: "" }).text;
}
/* 제목의 줄바꿈(\n)은 스테이지 카드에서만 쓴다. 공유 문구에는 한 줄로 */
const oneLine = (s) => s.replace(/\s*\n\s*/g, " ");

/* 문항 문장(text)의 \n 은 의미 단위 경계다. 단위마다 줄 안에서 쪼개지지 않는 덩어리로 감싸,
   한 줄에 들어가는 만큼 붙이고 넘칠 때만 단위 사이에서 줄을 넘긴다.
   해설 · 근거 · 한계처럼 긴 글은 단위로 묶지 않고 낱말 사이(keep-all)에서 넘겨 줄 끝까지 채운다 */
const units = (s) => s.split("\n").map((u) => `<span class="unit">${u}</span>`).join(" ");

function show(name) {
  Object.entries(views).forEach(([k, el]) => (el.hidden = k !== name));
  // 첫 화면에서는 레벨 줄을 노선도 바로 위로 — 둘 다 모은 하트로 정해지는 진행이라 붙여 둔다
  const hud = $("hud");
  if (name === "home") $("hud-home-slot").appendChild(hud);
  else views.home.before(hud);
  window.scrollTo({ top: 0 });
}

/* ── 시작 ────────────────────────────────────────── */
async function boot() {
  INDEX = await (await fetch("topics.json")).json();
  $("title").textContent = INDEX.title;
  $("subtitle").textContent = INDEX.subtitle;
  $("as-of").textContent = INDEX.as_of || "";

  const p = new URLSearchParams(location.search);
  if (p.has("s")) {
    const g = p.get("g") || "";
    const t = INDEX.topics.find((x) => x.id === p.get("t"));
    $("shared-banner").innerHTML =
      `친구가 ${t ? `<b>${t.emoji} ${t.title}</b> 에서 ` : ""}` +
      `<b>${Number(p.get("s"))}점</b>` + (g ? `, <b>${g}</b> 등급을` : "을") + ` 받았어요.` +
      (p.has("r") ? ` 지금 직급은 <b>${p.get("r")}</b>, ` +
        (Number(p.get("st")) ? `회사까지 <b>${Number(p.get("st"))}정거장</b> 남았어요.` : `<b>출근 완료!</b>`) : "") +
      ` 당신은요?`;
    $("shared-banner").hidden = false;
  }

  renderHud();
  renderGrid();
  $("hud-home-slot").appendChild($("hud"));       // 처음 보이는 화면이 첫 화면이라 레벨 줄을 노선도 위로
  $("lu-ok").onclick = () => ($("levelup").hidden = true);
  $("arrive-ok").onclick = () => ($("arrive").hidden = true);
  // Esc 로도 떠 있는 축하 · 승진 창을 닫는다(Enter 는 포커스가 간 버튼이 받는다)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") ["levelup", "arrive"].forEach((id) => ($(id).hidden = true));
  });
  $("btn-next").onclick = next;
  $("btn-back").onclick = () => show("home");
  $("btn-more").onclick = () => { renderGrid(); show("home"); };
  $("btn-share").onclick = share;
  $("btn-retry").onclick = startRetry;
  $("btn-pass").onclick = usePass;
  $("btn-sound").onclick = () => { store.set(SOUND_KEY, soundOn() ? "off" : "on"); renderSound(); };
  renderSound();
  if (p.has("t")) {
    const t = INDEX.topics.find((x) => x.id === p.get("t"));
    if (t && !p.has("s")) start(t.id);
  }
  // ?celebrate — 12개를 다 풀지 않아도 출근 완료 축하를 미리 본다(진행 기록은 그대로)
  if (p.has("celebrate")) setTimeout(celebrate, 600);
  // ?levelup — 마지막 승진(대표이사) 창을 미리 본다(진행 기록은 그대로)
  if (p.has("levelup")) showLevelup(RANKS.length - 1, RANKS.length);
}

function renderGrid() {
  const done = doneMap();
  const hearts = heartMap();
  $("topic-grid").innerHTML = "";
  INDEX.topics.forEach((t, i) => {
    const b = document.createElement("button");
    b.className = "tcard" + (t.id in done ? " done" : "");
    b.innerHTML =
      `<span class="tstage">STAGE ${i + 1}</span>` +
      `<span class="temoji">${t.emoji}</span>` +
      `<span class="ttitle">${t.title}</span>` +
      (t.id in done
        ? `<span class="thearts">${[0, 1, 2, 3, 4]
            .map((k) => heartSvg(k < (hearts[t.id] ?? 0))).join("")}</span>` +
          `<span class="tscore">${done[t.id]}점</span>`
        : "") +
      `<span class="tstart">START</span>`;
    b.onclick = () => start(t.id);
    $("topic-grid").appendChild(b);
  });
  renderCommute();
  renderTools();
}

/* 노선도 진행 — 끝낸 스테이지 수, 프리패스권을 썼으면 회사 */
function commute() {
  const max = INDEX.topics.length;
  const done = doneMap();
  const got = store.get(FREEPASS_KEY, false) ? max : INDEX.topics.filter((t) => t.id in done).length;
  return { max, got, left: max - got };
}

/* ── 맨 아래 두 칸 ─────────────────────────────────── */
function renderTools() {
  const wrong = wrongList().length;
  const r = $("btn-retry");
  r.classList.toggle("off", !wrong);
  r.innerHTML =
    `<span class="tstage">REVIEW</span><span class="temoji"><svg class="temoji-px"><use href="#px-review"/></svg></span>` +
    `<span class="ttitle">틀린 문제만\n다시 풀기</span>` +
    `<span class="tnote">${wrong ? `틀린 문제 ${wrong}개 · 5개씩` : "다시 풀 문제가 없어요"}</span>` +
    `<span class="tstart">${wrong ? "START" : "CLEAR"}</span>`;

  const arrived = commute().left === 0;
  $("btn-pass").innerHTML = arrived
    ? `<span class="tstage">RESTART</span><span class="temoji">🏠</span>` +
      `<span class="ttitle">처음부터\n다시 출근하기</span>` +
      `<span class="tnote">하트 · 직급 · 노선도를 지우고 집에서 출발</span>` +
      `<span class="tstart">RESET</span>`
    : `<span class="tstage">FREE PASS</span><span class="temoji">🎫</span>` +
      `<span class="ttitle">출근 완료\n프리패스권</span>` +
      `<span class="tnote">문제를 건너뛰고 바로 회사로</span>` +
      `<span class="tstart">USE</span>`;
}

function usePass() {
  if (commute().left === 0) {
    if (!confirm("처음부터 다시 출근할까요?\n하트 · 직급 · 노선도 · 점수 기록이 모두 지워져요.")) return;
    [DONE_KEY, HEART_KEY, HITS_KEY, FREEPASS_KEY, COMMUTE_KEY].forEach((k) => {
      try { localStorage.removeItem(k); } catch { /* 저장이 막혀 있어도 앱은 그대로 돈다 */ }
    });
    renderHud();
    renderGrid();
    return;
  }
  store.set(FREEPASS_KEY, true);
  renderGrid();                                   // 회사원이 회사까지 걸어가고 출근 완료 축하가 터진다
}

/* 틀린 문항을 5개씩 모아 한 판으로 푼다 — 맞히면 원래 주제의 하트가 채워진다 */
async function startRetry() {
  const list = wrongList().slice(0, 5);
  if (!list.length) return;
  const packs = {};
  for (const { id } of list) packs[id] ??= await (await fetch(`topics/${id}.json`)).json();
  PACK = {
    id: "retry", retry: true, emoji: "📝", title: "틀린 문제 다시 풀기", caveat: "",
    questions: list.map(({ id, qid }) => ({ ...packs[id].questions.find((q) => q.id === qid), _stage: id })),
  };
  idx = 0; answers = []; stageHits = [];
  $("topic-name").textContent = `${PACK.emoji} ${PACK.title}`;
  renderStageHearts();
  renderQ();
  show("quiz");
}

/* ── 소리 켜기 · 끄기 ───────────────────────────────── */
function soundOn() { return store.get(SOUND_KEY, "on") !== "off"; }
function renderSound() {
  $("btn-sound").textContent = soundOn() ? "🔊 소리 켜짐" : "🔇 소리 꺼짐";
  $("btn-sound").setAttribute("aria-pressed", String(soundOn()));
}

/* ── 출근길 노선도 — 스테이지 하나를 끝낼 때마다 한 정거장씩 집에서 회사로 ── */
const STOPS = ["집", "근로", "월급", "휴가", "보험", "노무", "출근"];
const STOP_END = [0, 2, 3, 5, 8, 11, 12];            // 각 정거장에 닿는 스테이지 수 — 근로 1~2 · 월급 3 · 휴가 4~5 · 보험 6~8 · 노무 9~11 · 출근 12
const COMMUTE_KEY = "gam-test-commute-stage";      // 지난번 자리(끝낸 스테이지 수) — 하트로 세던 예전 값과 섞이지 않게 새 이름

function renderCommute() {
  const { max, got, left } = commute();
  // 정거장은 같은 간격 — 스테이지 수가 정거장 사이에 있으면 그만큼만 걸어간다
  const at = (n) => {
    const j = Math.max(1, STOP_END.findIndex((e) => n <= e));
    const f = (Math.min(n, STOP_END[j]) - STOP_END[j - 1]) / (STOP_END[j] - STOP_END[j - 1]);
    return ((j - 1 + f) / (STOPS.length - 1)) * 100;
  };
  let prev = got;                                   // 지난번에 서 있던 자리 — 거기서 걸어온다
  try { prev = Math.min(Number(localStorage.getItem(COMMUTE_KEY) ?? got), got); } catch { /* 저장이 막혀 있으면 걷지 않는다 */ }

  // 남은 정거장 = 아직 끝내지 않은 스테이지 수(프리패스권을 썼으면 0)
  $("commute-note").textContent = left ? `회사까지 ${left}정거장` : "출근 완료!";
  $("metro").setAttribute("aria-label", `출근길 ${got} / ${max}`);
  $("metro").innerHTML =
    `<span class="rail"></span><span class="rail-done" style="width:${at(got)}%"></span>` +
    STOPS.map((name, i) => {
      const p = (i / (STOPS.length - 1)) * 100;
      const end = i === 0 ? "home" : i === STOPS.length - 1 ? "office" : "";
      return `<span class="stn${p <= at(got) ? " passed" : ""}${end ? " " + end : ""}" style="left:${p}%">` +
        (end ? `<svg><use href="#px-${end}"/></svg>` : "<i></i>") + `<b>${name}</b></span>`;
    }).join("") +
    `<svg class="rider" style="left:${at(prev)}%"><use href="#px-me"/></svg>`;

  if (prev !== got) {
    const r = $("metro").querySelector(".rider");
    r.classList.add("walking");
    requestAnimationFrame(() => requestAnimationFrame(() => { r.style.left = `${at(got)}%`; }));
    r.addEventListener("transitionend", () => r.classList.remove("walking"), { once: true });
  }
  // 이번에 막 회사에 닿았으면 회사원이 다 걸어간 뒤(1.2초) 한 번 축하한다
  if (prev < max && got === max) setTimeout(celebrate, 1300);
  try { localStorage.setItem(COMMUTE_KEY, String(got)); } catch { /* 저장이 막혀 있어도 앱은 그대로 돈다 */ }
}

/* 축하 창 · «♥ +1» 을 지금 눈에 보이는 화면에 맞춘다 — 폰 브라우저는 가끔 position: fixed 의 기준(레이아웃 뷰포트)을
   실제 화면보다 넓거나 짧게 잡아서, inset: 0 · left: 50% 만으로는 창이 옆으로 밀리고 꽃가루가 화면 중간에 쌓인다 */
function fitOverlays() {
  const v = window.visualViewport;
  if (!v) return;
  document.querySelectorAll(".levelup").forEach((o) => Object.assign(o.style, {
    left: `${v.offsetLeft}px`, top: `${v.offsetTop}px`, right: "auto", bottom: "auto",
    width: `${v.width}px`, height: `${v.height}px`,
  }));
  document.documentElement.style.setProperty("--fall", `${v.height}px`);   // 꽃가루가 창 바닥까지 떨어지게
  Object.assign($("toast").style, { left: `${v.offsetLeft + v.width / 2}px`, top: `${v.offsetTop + v.height * .38}px` });
}
window.visualViewport?.addEventListener("resize", fitOverlays);
window.visualViewport?.addEventListener("scroll", fitOverlays);

/* 픽셀 꽃가루 — 출근 완료 · 대표이사 취임 창이 같이 쓴다 */
function confetti(box) {
  const colors = ["#e8352e", "#f9e04b", "#7fd05a", "#3d6fb0", "#ffffff", "#e8972e"];
  box.innerHTML = Array.from({ length: 48 }, (_, i) =>
    `<i style="left:${Math.random() * 100}%;background:${colors[i % colors.length]};` +
    `animation-delay:${(Math.random() * 1.2).toFixed(2)}s;animation-duration:${(2.2 + Math.random() * 1.6).toFixed(2)}s"></i>`
  ).join("");
}

/* 출근 완료 축하 — 픽셀 꽃가루 + 8비트 빵빠레 */
function celebrate() {
  confetti($("confetti"));
  $("arrive").hidden = false;
  fitOverlays();
  $("arrive-ok").focus();
  fanfare();
}

function fanfare() {
  if (!soundOn()) return;
  try {
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    // 빠 · 바 · 바 · 밤! — 도 · 미 · 솔 · 높은 도, 마지막은 길게
    [[523, 0, .12], [659, .13, .12], [784, .26, .12], [1047, .39, .55], [784, .98, .1], [1047, 1.1, .7]]
      .forEach(([hz, at, len]) => {
        const o = ac.createOscillator(), g = ac.createGain();
        o.type = "square"; o.frequency.value = hz;
        g.gain.setValueAtTime(.08, ac.currentTime + at);
        g.gain.exponentialRampToValueAtTime(.001, ac.currentTime + at + len);
        o.connect(g).connect(ac.destination);
        o.start(ac.currentTime + at); o.stop(ac.currentTime + at + len);
      });
  } catch { /* 소리를 낼 수 없는 환경이면 꽃가루만 */ }
}

async function start(id) {
  PACK = await (await fetch(`topics/${id}.json`)).json();
  idx = 0; answers = []; stageHits = [];
  $("topic-name").textContent = `${PACK.emoji} ${PACK.title}`;
  renderStageHearts();
  renderQ();
  show("quiz");
}

/* ── 문항 ────────────────────────────────────────── */
function renderQ() {
  const q = PACK.questions[idx];
  $("progress-bar").style.width = `${(idx / PACK.questions.length) * 100}%`;
  $("q-count").textContent = `${idx + 1} / ${PACK.questions.length}`;
  $("q-text").innerHTML = units(q.text);
  $("btn-next").textContent =
    idx === PACK.questions.length - 1 ? "결과 보기" : "다음 업무 ▶";

  const isChoice = q.type === "choice";
  $("q-choice").hidden = !isChoice;
  $("q-slider").hidden = isChoice;

  if (isChoice) {
    answers[idx] = null;
    $("btn-next").disabled = true;
    $("q-choice").innerHTML = "";
    q.options.forEach((opt) => {
      const b = document.createElement("button");
      b.className = "choice";
      b.type = "button";
      b.textContent = opt;
      b.setAttribute("aria-pressed", "false");
      b.onclick = () => {
        answers[idx] = opt;
        [...$("q-choice").children].forEach((c) =>
          c.setAttribute("aria-pressed", String(c === b)));
        $("btn-next").disabled = false;
      };
      $("q-choice").appendChild(b);
    });
  } else {
    const s = $("slider");
    s.min = q.min; s.max = q.max; s.step = q.step;
    // 기본값을 한가운데에서 한 칸 비켜 둔다 — 가운데면 생각 없이 맞는다
    s.value = Math.round(((q.min + q.max) / 2 + q.step) / q.step) * q.step;
    $("slider-min").textContent = `${q.min}${q.unit}`;
    $("slider-max").textContent = `${q.max}${q.unit}`;
    const paint = () => {
      answers[idx] = Number(s.value);
      $("slider-out").textContent = `${s.value}${q.unit}`;
    };
    s.oninput = paint;
    paint();
    $("btn-next").disabled = false;
  }
}

function next() {
  // 답을 넘길 때마다 하트를 얻었는지만 알려 준다. 정답 숫자는 결과 화면에서
  stageHits[idx] = isHit(PACK.questions[idx], answers[idx]);
  renderStageHearts();
  toast(stageHits[idx]);
  if (idx < PACK.questions.length - 1) { idx++; renderQ(); return; }
  renderResult();
  show("result");
}

/* ── 결과 ────────────────────────────────────────── */
function pos(q, v) {
  return Math.max(0, Math.min(100, ((v - q.min) / (q.max - q.min)) * 100));
}

function renderResult() {
  const total = Math.round(
    PACK.questions.map((q, i) => scoreOne(q, answers[i]))
      .reduce((a, b) => a + b, 0) / PACK.questions.length);
  const g = gradeOf(total);
  if (!PACK.retry) markDone(PACK.id, total);       // 다시 풀기 판은 스테이지 기록이 아니다

  const hits = PACK.questions.map((q, i) => isHit(q, answers[i]));
  const got = hits.filter(Boolean).length;
  const before = levelOf(totalHearts());
  const best = PACK.retry ? 0 : heartMap()[PACK.id] ?? 0;
  // 맞힌 문항을 원래 주제에 더하고 그 주제의 하트를 올린다.
  // 다시 풀기에서 틀림 → 맞힘이 되면 원래 스테이지 하트를 하나 더한다(5개까지) — 예전 기록과 어긋나도 꼭 오르게
  PACK.questions.forEach((q, i) => {
    const id = PACK.retry ? q._stage : PACK.id;
    const { count, flipped } = addHit(id, q.id, hits[i]);
    const now = heartMap()[id] ?? 0;
    saveHearts(id, PACK.retry && flipped ? Math.min(5, Math.max(now + 1, count)) : count);
  });
  const after = levelOf(totalHearts());
  renderHud();

  $("result-topic").textContent = `${PACK.emoji} ${PACK.title}`;
  $("score").innerHTML = `${total}<span>점</span>`;
  $("grade").textContent = g.name;
  $("grade-emoji").textContent = g.emoji || "";
  $("heart-gain").innerHTML =
    `<span class="hg-row">${PACK.questions.map((q, i) =>
      `<span class="pop" style="animation-delay:${i * 0.18}s">${heartSvg(isHit(q, answers[i]))}</span>`
    ).join("")}</span>` +
    `<span class="hg-text">` + (PACK.retry
      ? `틀린 문제 ${PACK.questions.length}개 중 ${got}개를 맞혀 하트를 채웠어요`
      : `하트 ${got}개 획득` +
        (got > best ? (best ? ` · 최고 기록 갱신 (+${got - best})` : "") : best ? ` · 최고 기록 ${best}개` : "")) +
    `</span>`;
  if (after.lv > before.lv) {
    setTimeout(() => showLevelup(before.lv, after.lv), PACK.questions.length * 180 + 500);
  }

  const box = $("cards");
  box.innerHTML = "";
  PACK.questions.forEach((q, i) => {
    const mine = answers[i];
    const pct = errPct(q, mine);
    const hit = q.type === "choice" ? mine === q.answer : pct <= 5;
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <h3><span class="qmark">${heartSvg(isHit(q, mine))}</span><span>${units(q.text)}</span></h3>
      <p class="react ${hit ? "hit" : pct > 40 ? "miss" : ""}">${reactionOf(q, mine, pct)}</p>
      ${q.type === "choice" ? choiceBody(q, mine) : sliderBody(q, mine)}
      <p class="why">💡 ${q.why}</p>
      <details><summary>근거 보기</summary><p class="basis">${q.basis}</p>${
        q.limit ? `<p class="basis">⚠️ 한계 · ${q.limit}</p>` : ""}${
        (q.links || []).length ? `<p class="basis links">📜 원문 보기 · ${q.links.map((l) =>
          `<a href="${l.url}" target="_blank" rel="noopener">${l.label} ↗</a>`).join(" · ")}</p>` : ""}</details>`;
    box.appendChild(el);
  });

  $("caveat").hidden = !PACK.caveat;
  if (PACK.caveat) $("caveat").innerHTML = `<b>이 데이터의 한계</b><br>${PACK.caveat}`;
  $("source").innerHTML = PACK.retry ? "" :
    `출처 <a href="${PACK.source_url}" target="_blank" rel="noopener">${PACK.source}</a>`;

  requestAnimationFrame(() => setTimeout(animate, 60));
  renderNextStage();
}

/* 다음 스테이지 바로 가기 — 지금 스테이지 뒤에서 아직 안 끝낸 첫 스테이지(없으면 바로 다음 스테이지).
   마지막 스테이지(12)를 끝냈거나 모든 스테이지를 끝냈으면 틀린 문제 풀기로 넘어간다.
   다시 풀기 판이면 남은 틀린 문제를 더 푼다 */
function renderNextStage() {
  const b = $("btn-next-stage");
  const wrong = wrongList().length;
  if (PACK.retry) {
    b.hidden = !wrong;
    b.textContent = `틀린 문제 ${wrong}개 더 풀기 ▶`;
    b.onclick = startRetry;
    return;
  }
  const done = doneMap();
  const at = INDEX.topics.findIndex((t) => t.id === PACK.id);
  const last = at === INDEX.topics.length - 1;
  if (wrong && (last || INDEX.topics.every((t) => t.id in done))) {
    b.hidden = false;
    b.textContent = `틀린 문제 풀기 ▶ ${wrong}개 남았어요`;
    b.onclick = startRetry;
    return;
  }
  const after = INDEX.topics.slice(at + 1).concat(INDEX.topics.slice(0, at));
  const next = after.find((t) => !(t.id in done)) ?? INDEX.topics[at + 1];
  b.hidden = !next;
  if (!next) return;
  b.textContent = `다음 스테이지 ▶ STAGE ${INDEX.topics.indexOf(next) + 1} ${oneLine(next.title)}`;
  b.onclick = () => start(next.id);
}

function choiceBody(q, mine) {
  // 슬라이더 결과와 같은 약속 — 회사원 그림 = 내 답, 별 = 정답. 표시는 보기 앞에 두어 문장과 섞이지 않게
  const me = `<svg class="pi"><use href="#px-me"/></svg>`;
  const star = `<svg class="pi"><use href="#px-star"/></svg>`;
  const label = (o) => {
    const cls = o === q.answer && o === mine ? "both"
      : o === q.answer ? "real" : o === mine ? "mine" : "";
    const tag = o === q.answer && o === mine ? `${me}${star}<b class="lbl">내 답 · 정답</b>`
      : o === q.answer ? `${star}<b class="lbl">정답</b>`
      : o === mine ? `${me}<b class="lbl">내 답</b>` : "";
    return `<span class="pill ${cls}">${tag}<span>${o}</span></span>`;
  };
  return `<div class="pills">${q.options.map(label).join("")}</div>`;
}

function sliderBody(q, mine) {
  const rows = [["내 답", mine, "mine"]];
  rows.push(["실제", q.answer, "real"]);
  const max = Math.max(...rows.map((r) => Math.abs(Number(r[1])))) || 1;
  const bars = rows.map(([k, v, cls]) => `
      <div class="row">
        <span class="k">${k}</span>
        <span class="bar ${cls}"><i data-w="${Math.abs(Number(v)) / max * 100}"></i></span>
        <span class="v">${v}${q.unit}</span>
      </div>`).join("");
  return `
    <div class="track">
      <span class="line"></span>
      <svg class="ghost" style="left:${pos(q, mine)}%" aria-label="내 답"><use href="#px-me"/></svg>
      <svg class="live" data-left="${pos(q, q.answer)}" style="left:${pos(q, mine)}%" aria-label="실제"><use href="#px-star"/></svg>
    </div>
    <div class="rows">${bars}</div>`;
}

function animate() {
  document.querySelectorAll(".bar > i").forEach((b) => (b.style.width = b.dataset.w + "%"));
  document.querySelectorAll(".track .live").forEach((m) => (m.style.left = m.dataset.left + "%"));
}

/* ── 공유 ────────────────────────────────────────── */
async function share() {
  const total = $("score").textContent.replace(/[^0-9]/g, "");
  const grade = $("grade").textContent;
  const rank = levelOf(totalHearts()).rank;
  const { left } = commute();
  const url = `${location.origin}${location.pathname}` +
    `?t=${encodeURIComponent(PACK.id)}&s=${total}&g=${encodeURIComponent(grade)}` +
    `&r=${encodeURIComponent(rank)}&st=${left}`;
  const text = `${INDEX.title} · ${oneLine(PACK.title)} ${total}점 · ${grade} · ` +
    `지금 직급 ${rank} · ${left ? `회사까지 ${left}정거장` : "출근 완료!"}`;
  try {
    if (navigator.share) { await navigator.share({ title: INDEX.title, text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`);
    $("btn-share").textContent = "링크를 복사했어요";
    setTimeout(() => ($("btn-share").textContent = "동료에게 알려주기"), 1800);
  } catch { /* 사용자가 취소한 경우 */ }
}

boot();
