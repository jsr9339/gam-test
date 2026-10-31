/* 굿모닝 노동법! — 주제 고르기 · 진행 · 채점 · 하트 · 레벨 · 결과 · 공유
 *
 * 계산은 전부 여기서 끝난다. 서버는 촌평 한 줄을 받을 때만 부른다.
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

/* ── 하트 · 레벨 ─────────────────────────────────────
 * 한 문항에 하트 1개 — 택1은 맞히면, 슬라이더는 오차 20% 안이면.
 * 주제마다 «가장 많이 받은 하트»만 남기고, 그 합으로 레벨을 정한다.
 * 같은 주제를 다시 풀어 하트를 불릴 수는 없다.
 */
const HEART_KEY = "gam-test-hearts";
const HEART_PCT = 20;
const PER_LEVEL = 5;
const RANKS = ["인턴", "수습사원", "사원", "주임", "대리", "과장", "차장",
               "부장", "이사", "상무", "전무", "부사장", "사장", "노동법 마스터"];
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
function renderStageHearts() {
  $("stage-hearts").innerHTML = PACK.questions
    .map((_, i) => heartSvg(stageHits[i] === true)).join("");
}
function toast(hit) {
  const t = $("toast");
  t.className = "toast " + (hit ? "good" : "bad");
  t.innerHTML = hit ? `${heartSvg(true)} +1` : "MISS";
  t.hidden = false;
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
/* 받침이 있으면 을, 없으면 를 */
function josa(w) {
  const c = String(w).trim().slice(-1).charCodeAt(0);
  if (c < 0xac00 || c > 0xd7a3) return "을";
  return (c - 0xac00) % 28 ? "을" : "를";
}
/* Gemini 에게는 숫자가 아니라 방향만 보낸다 */
function directionOf(q, mine) {
  if (q.type === "choice") return mine === q.answer ? "맞힘" : "틀림";
  const d = (mine - q.answer) / Math.abs(q.answer);
  if (Math.abs(d) <= 0.08) return "비슷";
  return d > 0 ? "높게" : "낮게";
}

/* 제목의 줄바꿈(\n)은 스테이지 카드에서만 쓴다. 공유 문구 · 촌평 요청에는 한 줄로 */
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
  // 제목의 '감' 한 글자에 형광펜을 칠한다
  $("title").innerHTML = INDEX.title.replace("감", "<mark>감</mark>");
  $("subtitle").textContent = INDEX.subtitle;

  const p = new URLSearchParams(location.search);
  if (p.has("s")) {
    const g = p.get("g") || "";
    const t = INDEX.topics.find((x) => x.id === p.get("t"));
    $("shared-banner").innerHTML =
      `친구가 ${t ? `<b>${t.emoji} ${t.title}</b> 에서 ` : ""}` +
      `<b>${Number(p.get("s"))}점 · ${g}</b>${josa(g || "점")} 받았습니다. 당신은요?`;
    $("shared-banner").hidden = false;
  }

  renderHud();
  renderGrid();
  $("hud-home-slot").appendChild($("hud"));       // 처음 보이는 화면이 첫 화면이라 레벨 줄을 노선도 위로
  $("lu-ok").onclick = () => ($("levelup").hidden = true);
  $("arrive-ok").onclick = () => ($("arrive").hidden = true);
  $("btn-next").onclick = next;
  $("btn-back").onclick = () => show("home");
  $("btn-more").onclick = () => { renderGrid(); show("home"); };
  $("btn-share").onclick = share;
  if (p.has("t")) {
    const t = INDEX.topics.find((x) => x.id === p.get("t"));
    if (t && !p.has("s")) start(t.id);
  }
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
}

/* ── 출근길 노선도 — 스테이지 하나를 끝낼 때마다 한 정거장씩 집에서 회사로 ── */
const STOPS = ["집", "연차", "퇴직", "수당", "안전", "보험", "회사"];
const COMMUTE_KEY = "gam-test-commute-stage";      // 지난번 자리(끝낸 스테이지 수) — 하트로 세던 예전 값과 섞이지 않게 새 이름

function renderCommute() {
  const done = doneMap();
  const max = INDEX.topics.length;
  const got = INDEX.topics.filter((t) => t.id in done).length;
  const at = (n) => (n / max) * 100;
  let prev = got;                                   // 지난번에 서 있던 자리 — 거기서 걸어온다
  try { prev = Math.min(Number(localStorage.getItem(COMMUTE_KEY) ?? got), got); } catch { /* 저장이 막혀 있으면 걷지 않는다 */ }

  const left = max - got;                           // 남은 정거장 = 아직 끝내지 않은 스테이지 수
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

/* 출근 완료 축하 — 픽셀 꽃가루 + 8비트 빵빠레 */
function celebrate() {
  const colors = ["#e8352e", "#f9e04b", "#7fd05a", "#3d6fb0", "#ffffff", "#e8972e"];
  $("confetti").innerHTML = Array.from({ length: 48 }, (_, i) =>
    `<i style="left:${Math.random() * 100}%;background:${colors[i % colors.length]};` +
    `animation-delay:${(Math.random() * 1.2).toFixed(2)}s;animation-duration:${(2.2 + Math.random() * 1.6).toFixed(2)}s"></i>`
  ).join("");
  $("arrive").hidden = false;
  fanfare();
}

function fanfare() {
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
  markDone(PACK.id, total);

  const got = PACK.questions.filter((q, i) => isHit(q, answers[i])).length;
  const before = levelOf(totalHearts());
  const best = heartMap()[PACK.id] ?? 0;
  saveHearts(PACK.id, got);
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
    `<span class="hg-text">하트 ${got}개 획득` +
    (got > best ? (best ? ` · 최고 기록 갱신 (+${got - best})` : "") : best ? ` · 최고 기록 ${best}개` : "") +
    `</span>`;
  if (after.lv > before.lv) {
    setTimeout(() => {
      $("lu-lv").textContent = `LV ${before.lv} ▶ LV ${after.lv}`;
      $("lu-title").textContent = after.rank;
      $("levelup").hidden = false;
    }, PACK.questions.length * 180 + 500);
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
        q.limit ? `<p class="basis">⚠️ 한계 · ${q.limit}</p>` : ""}</details>`;
    box.appendChild(el);
  });

  $("caveat").hidden = !PACK.caveat;
  if (PACK.caveat) $("caveat").innerHTML = `<b>이 데이터의 한계</b><br>${PACK.caveat}`;
  $("source").innerHTML =
    `출처 <a href="${PACK.source_url}" target="_blank" rel="noopener">${PACK.source}</a>`;

  requestAnimationFrame(() => setTimeout(animate, 60));
  askComment(total, g.name);
}

function choiceBody(q, mine) {
  const label = (o) => {
    const cls = o === q.answer && o === mine ? "both"
      : o === q.answer ? "real" : o === mine ? "mine" : "";
    const tag = o === q.answer && o === mine ? " 실제 · 내 답"
      : o === q.answer ? " 실제" : o === mine ? " 내 답" : "";
    return `<span class="pill ${cls}">${o}${tag}</span>`;
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

/* ── 촌평 — 없어도 앱은 그대로 돈다 ──────────────── */
async function askComment(total, grade) {
  const el = $("ai-comment");
  el.hidden = false;
  el.innerHTML = `<span class="tag">촌평을 받아오는 중…</span>`;
  const directions = PACK.questions.map((q, i) => directionOf(q, answers[i]));
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 3000);
    const r = await fetch("/api/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score: total, grade, directions, topic: oneLine(PACK.title) }),
      signal: ctl.signal,
    });
    clearTimeout(timer);
    const j = await r.json();
    if (!j || !j.comment) { el.hidden = true; return; }
    el.innerHTML = `<span class="tag">한 줄 촌평</span><br>${j.comment}` +
      (j.nickname ? `<br><span class="nick">${j.nickname}</span>` : "");
  } catch {
    el.hidden = true;
  }
}

/* ── 공유 ────────────────────────────────────────── */
async function share() {
  const total = $("score").textContent.replace(/[^0-9]/g, "");
  const grade = $("grade").textContent;
  const url = `${location.origin}${location.pathname}` +
    `?t=${encodeURIComponent(PACK.id)}&s=${total}&g=${encodeURIComponent(grade)}`;
  const text = `${INDEX.title} · ${oneLine(PACK.title)} ${total}점 · ${grade}`;
  try {
    if (navigator.share) { await navigator.share({ title: INDEX.title, text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`);
    $("btn-share").textContent = "링크를 복사했습니다";
    setTimeout(() => ($("btn-share").textContent = "동료에게 알려주기"), 1800);
  } catch { /* 사용자가 취소한 경우 */ }
}

boot();
