import { makeReader, write, connectWallet, activeAccount, balanceOf, short, toGen, GEN, fmtErr }
  from "../shared/genlayer-lite.js";

const CONTRACT = "0xC2602425c2324f577754fdb17cae714Ce30b6Af5";
const { read } = makeReader(CONTRACT);
const C_FUNDING = 0, C_FUNDED = 1, C_COMPLETED = 2, C_FAILED = 3;
const M_LOCKED = 0, M_SUBMITTED = 1, M_RELEASED = 2, M_REJECTED = 3;
const CSTAT = ["Funding", "In progress", "Completed", "Failed"];
const CCLS = ["cs-funding", "cs-funded", "cs-completed", "cs-failed"];
let account = null, campaigns = [];
const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

$("contractLink").textContent = "Contract " + short(CONTRACT) + " \u2197";

function toast(msg, kind = "", title = "relay") {
  const el = document.createElement("div"); el.className = "toast " + kind;
  el.innerHTML = `<span class="tt">${title}</span>`; el.appendChild(document.createTextNode(msg));
  $("log").appendChild(el); setTimeout(() => el.remove(), kind === "err" ? 15000 : 5000);
}

async function refreshWallet() {
  account = await activeAccount();
  const slot = $("walletslot");
  if (account) { let bal = 0n; try { bal = await balanceOf(account); } catch (_) {} slot.innerHTML = `<span class="mono" style="font-size:13px;color:var(--grey)">${short(account)} \u00b7 ${toGen(bal)} GEN</span>`; }
  else { slot.innerHTML = `<button class="btn ghost sm" id="connectBtn">Connect</button>`; $("connectBtn").onclick = doConnect; }
}
async function doConnect() { try { account = await connectWallet(); toast("Connected on studionet.", "ok"); await refreshWallet(); } catch (e) { toast(fmtErr(e), "err"); } }
async function ensureWallet() { if (!account) account = await connectWallet(); await refreshWallet(); }

async function load() {
  try {
    const count = Number(await read("get_campaign_count"));
    const out = [];
    for (let i = 0; i < count; i++) {
      const c = { id: i, ...(await read("get_campaign", [i])) };
      const total = Number(c.ms_total); c.milestones = [];
      for (let k = 0; k < total; k++) c.milestones.push(await read("get_milestone", [i, k]));
      out.push(c);
    }
    campaigns = out; renderList();
    $("stTotal").textContent = count;
    const raised = out.reduce((a, c) => a + BigInt(c.raised), 0n);
    const released = out.reduce((a, c) => a + BigInt(c.released), 0n);
    $("stRaised").textContent = toGen(raised.toString());
    $("stReleased").textContent = toGen(released.toString());
  } catch (e) { $("campList").innerHTML = `<div class="c-empty">Could not reach the chain. ${fmtErr(e)}</div>`; }
}

function checkRow(m) {
  const st = Number(m.status);
  const cls = st === M_RELEASED ? "done" : st === M_REJECTED ? "rejected" : st === M_SUBMITTED ? "submitted" : "";
  const mark = st === M_RELEASED ? "\u2713" : st === M_REJECTED ? "\u2715" : st === M_SUBMITTED ? "\u22ef" : "";
  return `<div class="check ${st === M_RELEASED ? "done" : ""}"><span class="check-box ${cls}">${mark}</span><span class="check-txt">${esc(m.description)}</span><span class="check-amt">${toGen(m.amount)} GEN</span></div>`;
}

function renderList() {
  const el = $("campList");
  if (!campaigns.length) { el.innerHTML = `<div class="c-empty">No campaigns yet. Start the first one.</div>`; return; }
  el.innerHTML = "";
  [...campaigns].reverse().forEach((c) => {
    const st = Number(c.status);
    const goal = Number(toGen(c.goal)), raised = Number(toGen(c.raised)), released = Number(toGen(c.released));
    const pct = goal > 0 ? Math.min(100, (raised / goal) * 100) : 0;
    const card = document.createElement("div"); card.className = "camp";
    card.innerHTML = `
      <div class="camp-top"><span class="camp-title">${esc(c.title)}</span><span class="cstatus ${CCLS[st]}">${CSTAT[st]}</span></div>
      <div class="camp-sum">${esc(c.summary)}</div>
      <div class="bar"><div class="bar-fill ${released > 0 && released < goal ? "partial" : ""}" style="width:${pct}%"></div></div>
      <div class="bar-meta"><span><b>${raised}</b> / ${goal} GEN pledged</span><span><b>${released}</b> GEN released</span></div>
      <div class="checklist">${c.milestones.map(checkRow).join("")}</div>`;
    card.onclick = () => openDetail(c.id);
    el.appendChild(card);
  });
}

function openDrawer() { $("scrim").classList.add("on"); $("drawer").classList.add("on"); }
function closeDrawer() { $("scrim").classList.remove("on"); $("drawer").classList.remove("on"); }

function msRow(desc = "", amt = "") {
  return `<div class="ms-row"><input class="ms-desc" placeholder="Milestone description" value="${esc(desc)}" /><input class="ms-amt" type="number" min="0" step="0.5" placeholder="GEN" value="${amt}" /><span class="ms-del" title="Remove">\u2715</span></div>`;
}

function openNew() {
  $("drawerTitle").textContent = "New campaign";
  $("drawerBody").innerHTML = `
    <p>Break your goal into milestones. Each one holds its own tranche, released only when its proof is verified on-chain.</p>
    <label>Title</label><input id="nTitle" maxlength="90" placeholder="Open-source GenLayer explorer" />
    <label>Summary</label><textarea id="nSummary" placeholder="What you're building and why it matters."></textarea>
    <label>Milestones</label><div id="msList">${msRow("", "")}${msRow("", "")}</div>
    <span class="add-ms" id="addMs"><i class="ph-bold ph-plus"></i> Add milestone</span>
    <button class="btn primary block" id="createBtn"><i class="ph-bold ph-rocket-launch"></i> Launch campaign</button>`;
  $("addMs").onclick = () => { $("msList").insertAdjacentHTML("beforeend", msRow("", "")); bindDel(); };
  bindDel();
  $("createBtn").onclick = doCreate; openDrawer();
}
function bindDel() {
  document.querySelectorAll(".ms-del").forEach((d) => d.onclick = (e) => {
    if (document.querySelectorAll(".ms-row").length > 1) e.target.closest(".ms-row").remove();
  });
}

function openDetail(id) {
  const c = campaigns.find((x) => x.id === id); if (!c) return;
  const st = Number(c.status);
  const isCreator = account && c.creator && account.toLowerCase() === c.creator.toLowerCase();
  $("drawerTitle").textContent = "Campaign #" + id;
  const nextIdx = Number(c.ms_done);
  const next = c.milestones[nextIdx];
  let actions = "";
  if (st === C_FUNDING) actions = `<label>Pledge amount (GEN)</label><input id="pAmount" type="number" min="0" step="1" value="5" /><button class="btn blue block" id="pledgeBtn"><i class="ph-bold ph-hand-coins"></i> Pledge</button>`;
  else if (st === C_FUNDED && next) {
    if (Number(next.status) === M_LOCKED) actions = `<div class="hint" style="margin-top:4px">Next milestone: <b style="color:var(--ink)">${esc(next.description)}</b></div><label>Proof URL ${isCreator ? "" : "(creator only)"}</label><input id="proofUrl" placeholder="https://github.com/you/proof" /><button class="btn primary block" id="submitBtn"><i class="ph-bold ph-upload-simple"></i> Submit milestone proof</button>`;
    else if (Number(next.status) === M_SUBMITTED) actions = `<div class="hint" style="margin-top:4px">Proof submitted for: <b style="color:var(--ink)">${esc(next.description)}</b></div><button class="btn primary block" id="verifyBtn"><i class="ph-bold ph-shield-check"></i> Run AI verification</button><div class="hint" style="text-align:center;margin-top:8px">Validators read the proof URL against the milestone. Calls a real LLM; passing releases the tranche.</div>`;
  } else if (st === C_FAILED) actions = `<button class="btn blue block" id="refundBtn"><i class="ph-bold ph-arrow-u-up-left"></i> Reclaim my pledge</button><div class="hint" style="text-align:center;margin-top:8px">Refunds your share of the unreleased funds.</div>`;

  const checks = c.milestones.map((m) => {
    const ms = Number(m.status);
    const tag = ms === M_RELEASED ? `<span style="color:var(--green)">Released</span>` : ms === M_REJECTED ? `<span style="color:var(--red)">Rejected</span>` : ms === M_SUBMITTED ? `<span style="color:var(--amber)">In review</span>` : `<span style="color:var(--faint)">Locked</span>`;
    return `<div class="d-check">${checkRow(m)}</div><div class="kv" style="border:none;padding:4px 0 10px"><span class="k">${tag}</span>${m.rationale ? `<span class="v" style="font-size:12.5px;color:var(--grey)">${esc(m.rationale)}</span>` : ""}</div>`;
  }).join("");

  $("drawerBody").innerHTML = `
    <div class="d-title">${esc(c.title)}</div>
    <div class="kv"><span class="k">Status</span><span class="v">${CSTAT[st]}</span></div>
    <div class="kv"><span class="k">Pledged / Goal</span><span class="v mono">${toGen(c.raised)} / ${toGen(c.goal)} GEN</span></div>
    <div class="kv"><span class="k">Released</span><span class="v mono">${toGen(c.released)} GEN</span></div>
    <div class="kv"><span class="k">Creator</span><span class="v mono">${short(c.creator)}</span></div>
    <div style="margin:16px 0 4px;font-weight:600;color:var(--ink);font-size:14px">Milestones</div>
    ${checks}
    <div style="margin-top:16px">${actions}</div>`;
  openDrawer();
  if (st === C_FUNDING) $("pledgeBtn").onclick = () => doPledge(id);
  else if (st === C_FUNDED && next) {
    if (Number(next.status) === M_LOCKED && $("submitBtn")) $("submitBtn").onclick = () => doSubmit(id);
    else if (Number(next.status) === M_SUBMITTED && $("verifyBtn")) $("verifyBtn").onclick = () => doVerify(id);
  } else if (st === C_FAILED && $("refundBtn")) $("refundBtn").onclick = () => doRefund(id);
}

async function doCreate() {
  const title = $("nTitle").value.trim(), summary = $("nSummary").value.trim();
  if (!title) return toast("Give the campaign a title.", "err");
  if (!summary) return toast("Add a short summary.", "err");
  const rows = [...document.querySelectorAll("#msList .ms-row")];
  const ms = [];
  for (const r of rows) {
    const d = r.querySelector(".ms-desc").value.trim();
    const a = parseFloat(r.querySelector(".ms-amt").value);
    if (!d || !(a > 0)) continue;
    ms.push({ desc: d, amount: GEN(a).toString() });
  }
  if (!ms.length) return toast("Add at least one milestone with an amount.", "err");
  const btn = $("createBtn"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> launching';
  try { await ensureWallet(); await write(CONTRACT, "open_campaign", [title, summary, JSON.stringify(ms)]); toast("Campaign launched.", "ok"); closeDrawer(); await load(); }
  catch (e) { toast(fmtErr(e), "err"); btn.disabled = false; btn.innerHTML = "Launch campaign"; }
}
async function doPledge(id) {
  const amount = parseFloat($("pAmount").value);
  if (!(amount > 0)) return toast("Pledge must be above zero.", "err");
  const btn = $("pledgeBtn"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> pledging';
  try { await ensureWallet(); await write(CONTRACT, "pledge", [id], GEN(amount)); toast("Pledged into escrow.", "ok"); closeDrawer(); await load(); }
  catch (e) { toast(fmtErr(e), "err"); btn.disabled = false; btn.textContent = "Pledge"; }
}
async function doSubmit(id) {
  const url = $("proofUrl").value.trim(); if (!url) return toast("Enter the proof URL.", "err");
  const btn = $("submitBtn"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> submitting';
  try { await ensureWallet(); await write(CONTRACT, "submit_milestone", [id, url]); toast("Proof submitted.", "ok"); closeDrawer(); await load(); }
  catch (e) { toast(fmtErr(e), "err"); btn.disabled = false; btn.textContent = "Submit milestone proof"; }
}
async function doVerify(id) {
  if (!confirm("Run AI verification? Validators read the proof URL against the milestone. Calls a real LLM; passing releases the tranche.")) return;
  const btn = $("verifyBtn"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> validators verifying';
  try { await ensureWallet(); toast("Validators reading the proof\u2026", "", "verify"); await write(CONTRACT, "verify_milestone", [id]); toast("Verified on-chain.", "ok"); closeDrawer(); await load(); }
  catch (e) { toast(fmtErr(e), "err"); if (btn) { btn.disabled = false; btn.textContent = "Run AI verification"; } }
}
async function doRefund(id) {
  const btn = $("refundBtn"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> refunding';
  try { await ensureWallet(); await write(CONTRACT, "refund", [id]); toast("Refund claimed.", "ok"); closeDrawer(); await load(); }
  catch (e) { toast(fmtErr(e), "err"); btn.disabled = false; btn.textContent = "Reclaim my pledge"; }
}

$("heroPostBtn").onclick = openNew;
$("ctaPostBtn").onclick = openNew;
$("navPostBtn").onclick = openNew;
$("refreshBtn").onclick = load;
$("closeDrawer").onclick = closeDrawer;
$("scrim").onclick = closeDrawer;
const _cb = $("connectBtn"); if (_cb) _cb.onclick = doConnect;
if (window.ethereum) window.ethereum.on?.("accountsChanged", refreshWallet);

refreshWallet();
load();

// ====== subtle floating tranche-blocks (Three.js, Notion-calm) ======
(function blocks() {
  const canvas = $("blocksCanvas"); if (!canvas || !window.THREE) return;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(0, 0, 13);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  function resize() { const w = canvas.clientWidth, h = canvas.clientHeight || 300; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }

  const COLORS = [0x2383e2, 0x0f7b6c, 0xcb7b1e, 0x9065b0, 0xe9e9e7];
  const cubes = [];
  for (let i = 0; i < 14; i++) {
    const s = 0.7 + Math.random() * 0.9;
    const geo = new THREE.BoxGeometry(s, s, s);
    const mat = new THREE.MeshStandardMaterial({ color: COLORS[i % COLORS.length], metalness: .1, roughness: .65, transparent: true, opacity: .9 });
    const m = new THREE.Mesh(geo, mat);
    m.position.set((Math.random() - .5) * 12, (Math.random() - .5) * 8, (Math.random() - .5) * 5);
    m.rotation.set(Math.random() * 3, Math.random() * 3, 0);
    m.userData = { ry: (Math.random() - .5) * .006, yb: .003 + Math.random() * .004, ph: Math.random() * 6 };
    scene.add(m); cubes.push(m);
  }
  scene.add(new THREE.AmbientLight(0xffffff, 0.85));
  const key = new THREE.DirectionalLight(0xffffff, 0.9); key.position.set(4, 6, 8); scene.add(key);
  const fill = new THREE.DirectionalLight(0xbcd4ff, 0.4); fill.position.set(-6, -2, 4); scene.add(fill);

  resize(); addEventListener("resize", resize);
  let t = 0, running = true;
  const vis = new IntersectionObserver((es) => { running = es[0].isIntersecting; if (running) loop(); }, { threshold: 0 });
  vis.observe(canvas);
  function loop() {
    if (!running) return;
    requestAnimationFrame(loop); t += 0.01;
    cubes.forEach((m) => { m.rotation.y += m.userData.ry; m.rotation.x += m.userData.ry * 0.6; m.position.y += Math.sin(t + m.userData.ph) * 0.004; });
    renderer.render(scene, camera);
  }
  loop();
})();
