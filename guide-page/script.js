const DATA = __DATA__;
const IND = DATA.industries;
const ROLE_KEYS = Object.keys(DATA.roles);
const LOCS = ["San Francisco Bay Area","New York","Los Angeles","Seattle","Boston","Washington DC","Chicago","Austin","Denver","Atlanta","Dallas","Remote","Anywhere"];
const CH = [["email","Email"],["imessage","iMessage"],["sheets","Google Sheets tracker"],["whatsapp","WhatsApp"],["slack","Slack"],["discord","Discord"],["push","Phone push"],["claude","Just in Claude"]];
const SRC = [["linkedin","LinkedIn job alerts"],["handshake","Handshake job alerts"],["cmg","CMG emails"],["cmgtool","CMG via the cmg tool (Mac)"]];
const KEY = "internship-radar-profile-v2";
const $ = id => document.getElementById(id);
const state = {industries: [], rolesOn: [], rolesOff: [], locs: ["San Francisco Bay Area", "Remote"], channels: ["email", "sheets"], sources: ["linkedin"]};
try { Object.assign(state, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
state.channels = state.channels.filter(c => CH.some(x => x[0] === c));

function chip(group, value, label, small, checked) {
  const l = document.createElement("label"); l.className = "chip";
  const i = document.createElement("input"); i.type = "checkbox"; i.value = value; i.id = group + "-" + value.replace(/[^a-z0-9]+/gi, "-"); i.checked = !!checked;
  const s = document.createElement("span"); s.textContent = label;
  if (small) { const m = document.createElement("small"); m.textContent = small; s.appendChild(m); }
  l.append(i, s); return l;
}
const autoCount = k => IND[k].companies.filter(c => c.ats !== "manual").length;
function render() {
  const ind = $("industries"); ind.replaceChildren(...Object.keys(IND).map(k => chip("ind", k, IND[k].label, String(autoCount(k)), state.industries.includes(k))));
  const roles = currentRoles();
  $("roles").replaceChildren(...ROLE_KEYS.map(r => chip("role", r, r, "", roles.includes(r))));
  $("locs").replaceChildren(...LOCS.map(l => chip("loc", l, l, "", state.locs.includes(l))));
  $("channels").replaceChildren(...CH.map(([k, l]) => chip("ch", k, l, "", state.channels.includes(k))));
  $("sources").replaceChildren(...SRC.map(([k, l]) => chip("src", k, l, "", state.sources.includes(k))));
  update();
}
function suggested() { return [...new Set(state.industries.flatMap(k => IND[k].roles))]; }
function currentRoles() {
  const s = suggested().filter(r => !state.rolesOff.includes(r));
  return ROLE_KEYS.filter(r => s.includes(r) || state.rolesOn.includes(r));
}
function checked(id) { return [...$(id).querySelectorAll("input:checked")].map(i => i.value); }
function hourLabel(h) { h = +h; return h === 12 ? "12 PM" : h > 12 ? (h - 12) + " PM" : h + " AM"; }
function dreamList() {
  return $("dream").value.split("\n").map(x => x.trim()).filter(Boolean).map(line => {
    const [name, site] = line.split(",").map(x => (x || "").trim());
    return {name, site: (site || "").replace(/^https?:\/\//, "").replace(/\/.*$/, "")};
  }).filter(d => d.name);
}
function build() {
  const roles = currentRoles();
  const words = roles.join(" ").toLowerCase();
  let avoid = [...new Set(state.industries.flatMap(k => IND[k].avoid))];
  if (words.includes("data")) avoid = avoid.filter(a => !a.startsWith("data"));
  if (words.includes("people") || words.includes("hr")) avoid = avoid.filter(a => a !== "recruiter");
  if (words.includes("deployment")) avoid = avoid.filter(a => a !== "engineer" && a !== "engineering");
  const seen = new Set(), companies = [];
  for (const k of state.industries) for (const c of IND[k].companies) {
    const n = c.name.toLowerCase(); if (!seen.has(n)) { seen.add(n); companies.push({...c}); }
  }
  const dreams = dreamList();
  for (const d of dreams) {
    const hit = companies.find(c => c.name.toLowerCase() === d.name.toLowerCase());
    if (hit) hit.dream = true;
    else companies.push({name: d.name, ats: "manual", url: d.site ? "https://" + d.site : "", dream: true});
  }
  const anywhere = state.locs.includes("Anywhere");
  const mailSrc = state.sources.filter(s => ["linkedin", "handshake", "cmg"].includes(s));
  const chans = state.channels.filter(c => c !== "claude");
  const days = $("days").value, h = $("time").value;
  const when = `${days === "weekdays" ? "weekdays" : "every day"} at ${hourLabel(h)} Pacific`;
  const prof = {
    name: $("name").value.trim(), program: $("program").value.trim(),
    looking_for: document.querySelector('input[name="kind"]:checked').value, term: $("term").value.trim(), degree: "MBA",
    industries: state.industries, roles, avoid, locations: anywhere ? [] : state.locs,
    needs_sponsorship: document.querySelector('input[name="visa"]:checked').value === "yes", min_score: 55,
    alerts: {channels: chans, schedule: chans.length ? when : "ask in Claude", timezone: "America/Los_Angeles", send_when_quiet: false},
    email_alerts: {enabled: mailSrc.length > 0, from: mailSrc.length ? mailSrc : ["linkedin", "handshake", "cmg"], days: 3, extra_senders: []},
    cmg_tool: state.sources.includes("cmgtool"),
    companies
  };
  const label = k => IND[k].label;
  const chanLabel = state.channels.map(c => CH.find(x => x[0] === c)[1]);
  const lines = ["Set up my internship radar."];
  if (prof.name) lines.push(`- Name: ${prof.name}`);
  lines.push(`- Looking for: ${prof.term} ${prof.looking_for}${prof.program ? " · " + prof.program : ""}`);
  lines.push(`- Industries: ${state.industries.length ? state.industries.map(k => `${label(k)} (${k})`).join(", ") : "not chosen yet"}`);
  lines.push(`- Roles: ${roles.length ? roles.join(", ") : "not chosen yet"}`);
  lines.push(`- Dream companies: ${dreams.length ? dreams.map(d => d.site ? `${d.name} (${d.site})` : d.name).join(", ") : "none yet"}`);
  lines.push(`- Cities: ${anywhere || !state.locs.length ? "anywhere" : state.locs.join(", ")}`);
  lines.push(`- Visa sponsorship needed: ${prof.needs_sponsorship ? "yes" : "no"}`);
  lines.push(`- Alerts: ${chanLabel.length ? chanLabel.join(" and ") : "none yet"}${chans.length ? ", " + when : ""}`);
  lines.push(`- Also watch: ${state.sources.length ? state.sources.map(s => SRC.find(x => x[0] === s)[1]).join(", ") : "nothing else"}`);
  const utc = (+h + 7) % 24;
  const cron = `cron: "0 ${utc} * * ${days === "weekdays" ? "1-5" : "*"}"`;
  return {prof, text: lines.join("\n"), cron, auto: companies.filter(c => c.ats !== "manual").length, hand: companies.filter(c => c.ats === "manual").length};
}
function update() {
  const b = build();
  $("claude-text").textContent = b.text;
  $("file-text").textContent = JSON.stringify(b.prof, null, 1);
  $("cron-note").textContent = `Schedule line for radar.yml: ${b.cron}. GitHub runs on UTC, so in winter it arrives an hour earlier.`;
  $("n-auto").textContent = b.auto; $("n-hand").textContent = b.hand; $("n-roles").textContent = b.prof.roles.length;
  const notes = state.industries.map(k => IND[k].note).filter(Boolean);
  $("ind-note").textContent = notes.join(" ");
  try { localStorage.setItem(KEY, JSON.stringify({...state, name: $("name").value, program: $("program").value, term: $("term").value, dream: $("dream").value, days: $("days").value, time: $("time").value})); } catch (e) {}
}
document.addEventListener("change", e => {
  const t = e.target;
  if (t.id.startsWith("ind-")) {
    if (t.checked && state.industries.length >= 3) { t.checked = false; $("ind-note").textContent = "Three is the limit, so the morning list stays short. Uncheck one to swap."; return; }
    state.industries = checked("industries");
    render(); return;
  }
  if (t.id.startsWith("role-")) {
    const r = t.value, sug = suggested().includes(r);
    state.rolesOn = state.rolesOn.filter(x => x !== r); state.rolesOff = state.rolesOff.filter(x => x !== r);
    if (t.checked && !sug) state.rolesOn.push(r);
    if (!t.checked && sug) state.rolesOff.push(r);
  }
  if (t.id.startsWith("loc-")) {
    if (t.value === "Anywhere" && t.checked) { state.locs = ["Anywhere"]; render(); return; }
    state.locs = checked("locs").filter(l => l !== "Anywhere");
    if (state.locs.length !== checked("locs").length) { render(); return; }
  }
  if (t.id.startsWith("src-")) { state.sources = checked("sources"); update(); return; }
  if (t.id.startsWith("ch-")) {
    if (t.value === "claude" && t.checked) { state.channels = ["claude"]; render(); return; }
    state.channels = checked("channels").filter(c => c !== "claude");
    if (state.channels.length !== checked("channels").length) { render(); return; }
  }
  update();
});
document.addEventListener("input", e => { if (["name", "program", "term", "dream"].includes(e.target.id)) update(); });
$("f").addEventListener("submit", e => e.preventDefault());
for (const [tab, panel] of [["t-claude", "o-claude"], ["t-file", "o-file"]]) {
  $(tab).addEventListener("click", () => {
    for (const [t2, p2] of [["t-claude", "o-claude"], ["t-file", "o-file"]]) { $(t2).setAttribute("aria-selected", String(t2 === tab)); $(p2).hidden = p2 !== panel; }
    $("copied").textContent = "";
  });
}
$("copy").addEventListener("click", async () => {
  const pre = $("o-claude").hidden ? $("file-text") : $("claude-text");
  try { await navigator.clipboard.writeText(pre.textContent); $("copied").textContent = "Copied. Paste it into Claude or GitHub."; }
  catch (e) { const r = document.createRange(); r.selectNodeContents(pre); const s = getSelection(); s.removeAllRanges(); s.addRange(r); $("copied").textContent = "Selected. Press Copy on your keyboard (⌘C or Ctrl+C)."; }
});
(function restore() {
  for (const id of ["name", "program", "term", "dream", "days", "time"]) if (state[id]) $(id).value = state[id];
  render();
})();
