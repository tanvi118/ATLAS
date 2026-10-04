import { useEffect, useRef, useState } from "react";
const API = "http://localhost:8787";
const PAL = {
  dark: { bg: "#0d0b17", bg2: "#1b1530", tx: "#ece7ff", pn: "rgba(34,26,58,.6)", ln: "rgba(205,180,255,.3)", g: "#b8f2e6", a: "#ffc8dd", m: "#cdb4ff", c: "#a2d2ff", p: "#ffb5a7", on: "#1b1530",
    s: ["#b8f2e6", "#ffc8dd", "#cdb4ff", "#a2d2ff", "#ffb5a7", "#caffbf", "#bdb2ff", "#ffc6ff", "#9bf6ff", "#fdc5f5", "#b9fbc0", "#a0c4ff"] },
  light: { bg: "#f6f1fd", bg2: "#ffffff", tx: "#3a3452", pn: "rgba(255,255,255,.75)", ln: "rgba(140,110,200,.35)", g: "#5fbfa9", a: "#ee93b8", m: "#9b7fd6", c: "#6fadea", p: "#ef9a8a", on: "#ffffff",
    s: ["#7fd6c2", "#f59ac0", "#a98ddf", "#7fb8f0", "#f4a698", "#9bd98a", "#8f8cf0", "#e79be8", "#6fd0e0", "#f1a0d8", "#8ad8a0", "#82a8f0"] },
};
const AGS = [["calendar", "CALENDAR", "Events", "a"], ["gmail", "GMAIL", "Email", "m"], ["reminders", "REMINDERS", "Tasks", "g"], ["alarm", "ALARM", "Alarms", "c"], ["chrome", "CHROME", "Search", "p"]];
const DN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (n) => String(n).padStart(2, "0");
const SR = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

// ---- sweet female voice ----
let VOICE = null;
const pick = () => { const v = speechSynthesis.getVoices(); VOICE = ["Samantha", "Ava", "Allison", "Susan", "Tessa", "Moira", "Karen", "Google UK English Female", "Zira"].map((n) => v.find((x) => x.name.includes(n))).find(Boolean) || v.find((x) => /female/i.test(x.name)) || v.find((x) => x.lang.startsWith("en")) || null; };
if (typeof speechSynthesis !== "undefined") { speechSynthesis.onvoiceschanged = pick; pick(); }
const speak = (t) => { try { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(t); if (VOICE) u.voice = VOICE; u.pitch = 1.3; u.rate = 1.02; speechSynthesis.speak(u); } catch {} };

// ---- alarm audio (one persistent context, unlocked by first click) ----
let ctx;
const unlock = () => { try { if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); ctx.resume(); } catch {} };
const tone = (f, t0, d, type) => { if (!ctx) return; const o = ctx.createOscillator(), g = ctx.createGain(), n = ctx.currentTime + t0; o.type = type; o.frequency.value = f;
  g.gain.setValueAtTime(.0001, n); g.gain.exponentialRampToValueAtTime(.4, n + .02); g.gain.exponentialRampToValueAtTime(.0001, n + d); o.connect(g).connect(ctx.destination); o.start(n); o.stop(n + d + .05); };
const SND = { bell: () => { tone(880, 0, .5, "sine"); tone(1320, .15, .5, "sine"); }, digital: () => [0, .25, .5].forEach((t) => tone(1000, t, .15, "square")), chime: () => [523, 659, 784].forEach((f, i) => tone(f, i * .2, .5, "triangle")) };

const useLS = (k, i) => { const [v, s] = useState(() => { try { return JSON.parse(localStorage.getItem(k)) ?? i; } catch { return i; } }); useEffect(() => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }, [k, v]); return [v, s]; };
const nextRing = (a, now) => { if (a.ts) return a.ts; const [h, m] = a.time.split(":").map(Number); for (let d = 0; d < 8; d++) { const c = new Date(now); c.setDate(c.getDate() + d); c.setHours(h, m, 0, 0); if (c > now && (!a.days.length || a.days.includes(c.getDay()))) return +c; } return 0; };
const eta = (ms) => { const m = Math.max(0, Math.round(ms / 6e4)); return (m >= 60 ? Math.floor(m / 60) + "h " : "") + (m % 60) + "m"; };
const fmt12 = (t) => { const [h, m] = t.split(":").map(Number); return ((h % 12) || 12) + ":" + pad(m) + (h < 12 ? " AM" : " PM"); };

function Core({ P, mode, active }) {
  const ref = useRef(), M = useRef(), A = useRef(), PR = useRef(); M.current = mode; A.current = active; PR.current = P;
  useEffect(() => {
    const cv = ref.current, x = cv.getContext("2d"), D = devicePixelRatio || 1; let W, H, t = 0, raf;
    const pts = Array.from({ length: 1100 }, (_, i) => { const y = 1 - 2 * (i + .5) / 1100, r = Math.sqrt(1 - y * y), a = i * 2.39996; return { x: Math.cos(a) * r, y, z: Math.sin(a) * r, cl: i % 12, j: .85 + Math.random() * .3 }; });
    const rs = () => { W = cv.width = cv.clientWidth * D; H = cv.height = cv.clientHeight * D; }; rs(); addEventListener("resize", rs);
    const draw = () => {
      const p = PR.current, boost = M.current === "idle" ? 0 : M.current === "listening" ? .08 : .15; t += .004 + boost * .03; x.clearRect(0, 0, W, H);
      const cx = W / 2, cy = H / 2 - 20 * D, R = Math.min(W, H) * .28 * (1 + boost * Math.sin(t * 40) * .3), cs = Math.cos(t), sn = Math.sin(t);
      pts.forEach((q) => { const X = q.x * cs - q.z * sn, Z = q.x * sn + q.z * cs, k = (Z + 2) / 3, s = R * q.j; x.globalAlpha = .3 + k * .65; x.fillStyle = p.s[q.cl]; x.fillRect(cx + X * s, cy + q.y * s, (1 + k * 1.8) * D, (1 + k * 1.8) * D); });
      x.globalAlpha = 1; const g = x.createRadialGradient(cx, cy, 0, cx, cy, R * .5); g.addColorStop(0, p.a + "99"); g.addColorStop(1, p.a + "00"); x.fillStyle = g; x.fillRect(0, 0, W, H);
      x.save(); x.translate(cx, cy); x.strokeStyle = p.g; x.lineWidth = D;
      for (let i = 0; i < 120; i++) { const a = i / 120 * 6.283 - t * 1.5, l = i % 5 ? 5 : 11; x.beginPath(); x.moveTo(Math.cos(a) * R * 1.25, Math.sin(a) * R * 1.25); x.lineTo(Math.cos(a) * (R * 1.25 + l * D), Math.sin(a) * (R * 1.25 + l * D)); x.stroke(); }
      x.lineWidth = 3 * D; x.beginPath(); x.arc(0, 0, R * 1.18, t * 2, t * 2 + 2.2); x.stroke(); x.strokeStyle = p.c; x.beginPath(); x.arc(0, 0, R * 1.12, -t * 3, -t * 3 + 1.2); x.stroke();
      AGS.forEach((a, i) => { const ang = i / 5 * 6.283 + t * .8, px = Math.cos(ang) * R * 1.65, py = Math.sin(ang) * R * 1.65 * .55, on = A.current === a[0], col = p[a[3]];
        x.strokeStyle = x.fillStyle = col; x.lineWidth = D; x.beginPath(); x.arc(px, py, (on ? 11 : 7) * D, 0, 7); on ? x.fill() : x.stroke(); x.font = `${11 * D}px 'Share Tech Mono'`; x.fillText(a[1], px + 14 * D, py + 4 * D); });
      x.restore(); raf = requestAnimationFrame(draw);
    };
    draw(); return () => { cancelAnimationFrame(raf); removeEventListener("resize", rs); };
  }, []);
  return <canvas ref={ref} />;
}

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600&family=Share+Tech+Mono&display=swap');
*{box-sizing:border-box}.app{height:100vh;min-height:640px;display:grid;grid-template-columns:240px 1fr 380px;gap:12px;padding:14px;color:var(--tx);font:15px 'Chakra Petch',sans-serif;background:radial-gradient(circle at 50% 45%,var(--bg2),var(--bg) 70%)}
.col{display:flex;flex-direction:column;gap:12px;min-height:0}.box{border:1px solid var(--ln);padding:10px 12px;background:var(--pn);border-radius:10px}.box h4{margin:0 0 8px;font:400 12px 'Share Tech Mono';color:var(--g);letter-spacing:.12em}
.ttl{font:600 22px 'Chakra Petch';letter-spacing:.3em;color:var(--m)}.mono{font:12px 'Share Tech Mono'}
button,select,input{font:inherit;color:var(--tx)}button{cursor:pointer;background:transparent;border:1px solid var(--ln);border-radius:8px;padding:6px 10px}button:hover,button:focus-visible{background:var(--ln);outline:none}
.ag{display:flex;align-items:center;gap:8px;width:100%;border:0;border-bottom:1px solid var(--ln);border-radius:0;text-align:left}.ag small{margin-left:auto;font:11px 'Share Tech Mono';opacity:.7}.dot{width:9px;height:9px;border-radius:50%}
.stage{position:relative;min-height:0}canvas{position:absolute;inset:0;width:100%;height:100%}.hud{position:absolute;left:0;right:0;bottom:6px;text-align:center}.say{font-size:19px;min-height:52px;padding:0 20px}.st{font:13px 'Share Tech Mono';letter-spacing:.3em;color:var(--a)}
.mic{width:100%;padding:10px;color:var(--g);border-color:var(--g);letter-spacing:.1em;font-weight:600}.mic.on{background:var(--g);color:var(--on)}
.tabs{display:flex;gap:4px;margin-bottom:8px}.tabs button{flex:1;padding:5px 0;font:12px 'Share Tech Mono'}.tabs .on{background:var(--m);color:var(--on);border-color:var(--m)}
.pane{flex:1;overflow:auto;min-height:0}input[type=text],input[type=time],select,input:not([type]){background:var(--pn);border:1px solid var(--ln);border-radius:8px;padding:7px;width:100%}
.row{display:flex;gap:6px;margin:6px 0}.al{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ln)}.big{font:600 24px 'Chakra Petch'}
.d{padding:4px 7px;font:11px 'Share Tech Mono'}.d.on{background:var(--a);color:var(--on);border-color:var(--a)}.ans{border-left:3px solid var(--a);padding-left:10px;margin:8px 0}.ev div{padding:3px 0;border-bottom:1px dashed var(--ln)}
.ring{position:fixed;inset:0;display:grid;place-items:center;background:rgba(20,10,40,.6);z-index:9;backdrop-filter:blur(6px)}.ring>div{background:var(--bg2);border:2px solid var(--a);border-radius:20px;padding:32px 48px;text-align:center;animation:pl 1s infinite alternate}
@keyframes pl{to{box-shadow:0 0 50px var(--a)}}@media(max-width:1000px){.app{grid-template-columns:1fr;height:auto}.stage{height:70vh}}@media(prefers-reduced-motion:reduce){*{animation:none!important}}`;

export default function App() {
  const [theme, setTheme] = useLS("atlas_theme", "dark"), P = PAL[theme];
  const [mode, setMode] = useState("idle"), [mic, setMic] = useState(false), [active, setActive] = useState(null), [tab, setTab] = useState("ask");
  const [said, setSaid] = useState("Say \"ATLAS\" to wake me."), [log, setLog] = useState([]), [typed, setTyped] = useState(""), [q, setQ] = useState("");
  const [tasks, setTasks] = useLS("atlas_tasks", [{ n: "AI exam preparation", d: "Friday" }, { n: "Project synopsis", d: "Monday" }]);
  const [alarms, setAlarms] = useLS("atlas_alarms", []), [mem, setMem] = useLS("atlas_mem", { facts: [], history: [] }), [mf, setMf] = useState("");
  const [docs, setDocs] = useState([]), [ans, setAns] = useState(null), [busy, setBusy] = useState(false), [ringing, setRinging] = useState(null), [now, setNow] = useState(Date.now());
  const [af, setAf] = useState({ time: "07:00", label: "", days: [], sound: "bell", snooze: 9 });
  const awake = useRef(0), rec = useRef(), on = useRef(false), runRef = useRef(), alRef = useRef(), ringRef = useRef(), rt = useRef(), memRef = useRef(), srRef = useRef();
  alRef.current = alarms; memRef.current = mem;
  const ev = (s) => setLog((l) => [[new Date().toLocaleTimeString([], { hour12: false }), s], ...l].slice(0, 40));
  const say = (s) => { setSaid(s); speak(s); ev("ATLAS: " + s); };
  const flash = (k) => { setActive(k); setTimeout(() => setActive(null), 2500); };
  const open = (u) => window.open(u, "_blank");
  const name = (mem.facts.find((f) => f.startsWith("Name: ")) || "").slice(6);

  // ---- alarms ----
  const addAlarm = (a) => { setAlarms((l) => [...l, { id: Date.now() + Math.random(), on: true, days: [], sound: "bell", snooze: 9, label: "Alarm", ...a }]); try { Notification.requestPermission(); } catch {} };
  const stopRing = () => { clearInterval(rt.current); ringRef.current = null; setRinging(null); };
  const startRing = (a) => { unlock(); setRinging(a); ringRef.current = a; const go = () => { try { SND[a.sound || "bell"](); } catch {} }; go(); clearInterval(rt.current); rt.current = setInterval(go, 1500);
    speak("Time to wake up. " + (a.label || "Your alarm") + " is ringing."); try { new Notification("ATLAS alarm", { body: a.label || "Alarm" }); } catch {} ev("Alarm ringing: " + (a.label || "")); };
  srRef.current = startRing;
  const snooze = () => { const a = ringRef.current; if (!a) return; stopRing(); addAlarm({ ts: Date.now() + (a.snooze || 9) * 6e4, label: (a.label || "Alarm").replace(" (snoozed)", "") + " (snoozed)", sound: a.sound, snooze: a.snooze }); say("Snoozed for " + (a.snooze || 9) + " minutes."); };
  useEffect(() => { const i = setInterval(() => {
    const n = new Date(), key = n.toDateString() + n.getHours() + ":" + n.getMinutes(), hm = pad(n.getHours()) + ":" + pad(n.getMinutes()); setNow(Date.now());
    const hit = alRef.current.find((a) => a.on && (a.ts ? Date.now() >= a.ts : a.time === hm && (!a.days.length || a.days.includes(n.getDay())) && a.last !== key));
    if (hit && !ringRef.current) { srRef.current(hit); setAlarms((l) => l.flatMap((a) => a.id !== hit.id ? [a] : hit.ts ? [] : [{ ...a, last: key, on: hit.days.length ? true : false }])); } }, 1000);
    const u = () => unlock(); addEventListener("pointerdown", u); addEventListener("keydown", u); return () => { clearInterval(i); removeEventListener("pointerdown", u); removeEventListener("keydown", u); }; }, []);
  useEffect(() => { document.body.style.margin = 0; document.body.style.background = P.bg; }, [P]);

  // ---- RAG ----
  const loadDocs = () => fetch(API + "/docs").then((r) => r.json()).then(setDocs).catch(() => setDocs(null));
  useEffect(() => { loadDocs(); }, []);
  const upload = async (files) => { const fd = new FormData(); [...files].forEach((f) => fd.append("files", f));
    try { const r = await fetch(API + "/upload", { method: "POST", body: fd }), j = await r.json(); if (j.error) throw 0; say("Indexed " + j.added.length + " document" + (j.added.length > 1 ? "s" : "") + "."); loadDocs(); } catch { say("Upload failed. Is the backend running?"); } };
  const ask = async (question) => { setBusy(true); setTab("ask"); setMode("working");
    try { const r = await fetch(API + "/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, memory: memRef.current.facts }) }), j = await r.json(); setAns({ q: question, ...j }); say(j.answer.slice(0, 300)); }
    catch { say("My document backend is offline."); setAns({ q: question, answer: "Backend not reachable at " + API + ". Run: node server.cjs", sources: [] }); }
    setBusy(false); setMode("idle"); };

  // ---- command router ----
  const run = (raw) => {
    const c = raw.toLowerCase().trim(); if (!c) return; ev("You: " + raw); setMem((m) => ({ ...m, history: [raw, ...m.history].slice(0, 15) })); setMode("working"); setTimeout(() => setMode("idle"), 1500);
    let m;
    if (/snooze/.test(c)) return snooze();
    if (/(stop|dismiss|turn off|cancel) (the |my )?alarm/.test(c)) { stopRing(); return say("Alarm dismissed."); }
    if ((m = c.match(/(light|dark) (mode|theme)/))) { setTheme(m[1]); return say(m[1] + " mode on."); }
    if ((m = c.match(/my name is (\w+)/))) { const n = m[1][0].toUpperCase() + m[1].slice(1); setMem((x) => ({ ...x, facts: [...x.facts.filter((f) => !f.startsWith("Name: ")), "Name: " + n] })); return say("Nice to meet you, " + n + ". I'll remember that."); }
    if ((m = c.match(/remember (?:that )?(.+)/))) { setMem((x) => ({ ...x, facts: [...x.facts, m[1]] })); setTab("memory"); return say("Got it. I'll remember that " + m[1] + "."); }
    if (/what do you (remember|know)/.test(c)) return say(mem.facts.length ? "I remember: " + mem.facts.join(". ") : "I don't have any memories yet.");
    if (/forget (everything|all)/.test(c)) { setMem({ facts: [], history: [] }); return say("Memory cleared."); }
    if (/alarm|wake me|timer/.test(c)) {
      const t = c.match(/(\d+)\s*(second|minute|hour)/); if (t) { const ms = +t[1] * { second: 1e3, minute: 6e4, hour: 36e5 }[t[2]]; addAlarm({ ts: Date.now() + ms, label: "Timer" }); flash("alarm"); setTab("alarms"); return say("Alarm set for " + t[1] + " " + t[2] + "s from now."); }
      const a = c.match(/at (\d{1,2})(?:[:\s](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?/); if (a) { let h = +a[1]; if (/^p/.test(a[3] || "") && h < 12) h += 12; if (/^a/.test(a[3] || "") && h === 12) h = 0; const tm = pad(h) + ":" + pad(+(a[2] || 0)); addAlarm({ time: tm, label: "Voice alarm" }); flash("alarm"); setTab("alarms"); return say("Alarm set for " + fmt12(tm) + "."); }
      setTab("alarms"); return say("Tell me when, like alarm at 7 30 am, or alarm in 10 minutes.");
    }
    if (/remind/.test(c)) { const t = c.replace(/.*remind me( to)?/, "").trim() || "Reminder"; setTasks((l) => [{ n: t, d: "Today" }, ...l]); open("x-apple-reminderkit://"); flash("reminders"); return say("Reminder saved: " + t + "."); }
    if (/calendar|meeting|schedule|event/.test(c)) { const t = c.replace(/.*(calendar|meeting|schedule|event)( for| about| called)?/, "").trim() || "New event"; open("https://calendar.google.com/calendar/r/eventedit?text=" + encodeURIComponent(t)); flash("calendar"); return say("Opening calendar."); }
    if (/gmail|email|mail/.test(c)) { open("https://mail.google.com/mail/?view=cm&fs=1&su=" + encodeURIComponent(c.replace(/.*(gmail|email|mail)( to| about)?/, "").trim())); flash("gmail"); return say("Opening Gmail."); }
    if (/^(search|google|open chrome|look up)/.test(c)) { const t = c.replace(/^(search for|search|google|look up|open chrome)/, "").trim(); open(t ? "https://www.google.com/search?q=" + encodeURIComponent(t) : "https://www.google.com"); flash("chrome"); return say(t ? "Searching for " + t + "." : "Opening Chrome."); }
    if (/^(stop|sleep)/.test(c)) { awake.current = 0; return say("Standing by."); }
    ask(raw);
  };
  runRef.current = run;

  const start = () => {
    unlock(); if (!SR) return setSaid("Voice needs Chrome. Use the text box.");
    const r = new SR(); r.continuous = true; r.interimResults = true; r.lang = "en-US";
    r.onresult = (e) => { if (speechSynthesis.speaking) return; const res = e.results[e.results.length - 1], t = res[0].transcript.toLowerCase(), w = /\b(atlas|at las|atlass)\b/;
      if (w.test(t) && awake.current <= Date.now()) { awake.current = Date.now() + 12000; setMode("listening"); speak(name ? "Yes, " + name + "?" : "Yes?"); setSaid("Listening..."); ev("Wake word detected"); }
      if (res.isFinal && awake.current > Date.now()) { const cmd = t.replace(/.*\b(atlas|at las|atlass)\b[,.]?/, "").trim(); if (cmd) { awake.current = 0; runRef.current(cmd); } } };
    r.onend = () => on.current && r.start(); r.onerror = (e) => e.error === "not-allowed" && setSaid("Allow microphone access in Chrome.");
    r.start(); rec.current = r; on.current = true; setMic(true); setSaid("Standing by. Say \"ATLAS\"."); };
  const stop = () => { on.current = false; rec.current?.stop(); setMic(false); setMode("idle"); setSaid("Voice off."); };

  const vars = { "--bg": P.bg, "--bg2": P.bg2, "--tx": P.tx, "--pn": P.pn, "--ln": P.ln, "--g": P.g, "--a": P.a, "--m": P.m, "--c": P.c, "--p": P.p, "--on": P.on };
  const dayTxt = (d) => !d.length ? "Once" : d.length === 7 ? "Every day" : d.map((x) => DN[x]).join(" ");
  return (<><style>{CSS}</style><div className="app" style={vars}>
    <div className="col">
      <div className="box"><div className="ttl">ATLAS</div><div className="mono" style={{ color: "var(--a)" }}>{mic ? (mode === "listening" ? "LISTENING" : "ONLINE") : "VOICE OFF"} · {new Date(now).toLocaleTimeString([], { hour12: false })}</div>
        <button style={{ marginTop: 8, width: "100%" }} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "☀ Light mode" : "☾ Dark mode"}</button></div>
      <div className="box"><h4>CONNECTED APPS</h4>{AGS.map((a) => <button key={a[0]} className="ag" onClick={() => run(a[0] === "alarm" ? "alarm" : a[0] === "reminders" ? "remind me to check tasks" : a[0] === "chrome" ? "open chrome" : a[0])}><span className="dot" style={{ background: P[a[3]], boxShadow: active === a[0] ? `0 0 10px ${P[a[3]]}` : "none" }} />{a[1]}<small>{a[2]}</small></button>)}</div>
      <div className="box pane"><h4>TASKS</h4><div className="mono">{tasks.map((t, i) => <div key={i} className="al" style={{ padding: "4px 0" }}><span>{t.n} <span style={{ color: "var(--a)" }}>{t.d}</span></span><button className="d" onClick={() => setTasks((l) => l.filter((_, j) => j !== i))}>✕</button></div>)}</div></div>
    </div>
    <div className="stage"><Core P={P} mode={mode} active={active} /><div className="hud"><div className="st">{mode.toUpperCase()}</div><div className="say">{said}</div></div></div>
    <div className="col">
      <div className="box"><button className={"mic" + (mic ? " on" : "")} onClick={mic ? stop : start}>{mic ? "VOICE ON · SAY ATLAS" : "ENABLE VOICE ACTIVATION"}</button></div>
      <div className="box col" style={{ flex: 1 }}>
        <div className="tabs">{[["ask", "ASK"], ["alarms", "ALARMS"], ["memory", "MEMORY"], ["log", "LOG"]].map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
        <div className="pane">
          {tab === "ask" && <>
            <h4>DOCUMENTS {docs === null && <span style={{ color: "var(--p)" }}>· backend offline</span>}</h4>
            <input type="file" multiple accept=".pdf,.txt,.md,.docx" onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
            {(docs || []).map((d) => <div key={d.id} className="al mono" style={{ padding: "4px 0" }}><span>{d.name} · {d.chunks} chunks</span><button className="d" onClick={() => fetch(API + "/docs/" + d.id, { method: "DELETE" }).then(loadDocs)}>✕</button></div>)}
            <h4 style={{ marginTop: 12 }}>ASK YOUR DOCUMENTS</h4>
            <form className="row" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { ask(q); setQ(""); } }}><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. What is RAG?" /><button>{busy ? "…" : "Ask"}</button></form>
            {ans && <div className="ans"><div className="mono" style={{ opacity: .7 }}>Q: {ans.q}</div><p>{ans.answer}</p>{ans.sources?.length > 0 && <div className="mono" style={{ color: "var(--g)" }}>Sources: {ans.sources.join(", ")} {ans.mode === "extractive" && "· extractive (add ANTHROPIC_API_KEY for full answers)"}</div>}</div>}
          </>}
          {tab === "alarms" && <>
            <div className="row"><input type="time" value={af.time} onChange={(e) => setAf({ ...af, time: e.target.value })} /><input placeholder="Label" value={af.label} onChange={(e) => setAf({ ...af, label: e.target.value })} /></div>
            <div className="row">{DN.map((d, i) => <button key={d} className={"d" + (af.days.includes(i) ? " on" : "")} onClick={() => setAf({ ...af, days: af.days.includes(i) ? af.days.filter((x) => x !== i) : [...af.days, i] })}>{d[0]}</button>)}</div>
            <div className="row"><select value={af.sound} onChange={(e) => setAf({ ...af, sound: e.target.value })}><option value="bell">Bell</option><option value="digital">Digital</option><option value="chime">Chime</option></select>
              <select value={af.snooze} onChange={(e) => setAf({ ...af, snooze: +e.target.value })}>{[5, 9, 10, 15].map((n) => <option key={n} value={n}>Snooze {n}m</option>)}</select></div>
            <div className="row"><button style={{ flex: 1 }} onClick={() => { addAlarm({ ...af, label: af.label || "Alarm" }); setAf({ ...af, label: "" }); }}>+ Add alarm</button><button onClick={() => { unlock(); SND[af.sound](); }}>▶ Test sound</button></div>
            {alarms.length === 0 && <div className="mono">No alarms. Try "ATLAS, alarm at 7 30 am".</div>}
            {alarms.map((a) => { const nx = nextRing(a, now); return <div key={a.id} className="al"><div><div className="big">{a.ts ? new Date(a.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : fmt12(a.time)}</div><div className="mono">{a.label} · {a.ts ? "Once" : dayTxt(a.days)} · {a.sound}</div>{a.on && nx > 0 && <div className="mono" style={{ color: "var(--g)" }}>rings in {eta(nx - now)}</div>}</div>
              <div className="row"><input type="checkbox" checked={a.on} onChange={() => setAlarms((l) => l.map((x) => x.id === a.id ? { ...x, on: !x.on } : x))} /><button className="d" onClick={() => { if (a.time) setAf({ time: a.time, label: a.label, days: a.days, sound: a.sound, snooze: a.snooze }); setAlarms((l) => l.filter((x) => x.id !== a.id)); }}>✎</button><button className="d" onClick={() => setAlarms((l) => l.filter((x) => x.id !== a.id))}>✕</button></div></div>; })}
          </>}
          {tab === "memory" && <>
            <h4>LONG-TERM MEMORY</h4><div className="mono">Say "remember that I prefer morning study" or "my name is Tanvi".</div>
            <form className="row" onSubmit={(e) => { e.preventDefault(); if (mf.trim()) { setMem({ ...mem, facts: [...mem.facts, mf.trim()] }); setMf(""); } }}><input value={mf} onChange={(e) => setMf(e.target.value)} placeholder="Add a memory" /><button>Add</button></form>
            {mem.facts.map((f, i) => <div key={i} className="al mono" style={{ padding: "4px 0" }}><span>{f}</span><button className="d" onClick={() => setMem({ ...mem, facts: mem.facts.filter((_, j) => j !== i) })}>✕</button></div>)}
            <h4 style={{ marginTop: 12 }}>RECENT INTERACTIONS</h4><div className="mono">{mem.history.map((h, i) => <div key={i}>· {h}</div>)}</div>
            <button style={{ marginTop: 10 }} onClick={() => setMem({ facts: [], history: [] })}>Clear memory</button>
          </>}
          {tab === "log" && <div className="ev mono">{log.map((l, i) => <div key={i}><span style={{ opacity: .6 }}>{l[0]}</span> {l[1]}</div>)}</div>}
        </div>
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); run(typed); setTyped(""); }}><input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Type a command" /><button>Send</button></form>
    </div>
    {ringing && <div className="ring"><div><div className="mono" style={{ color: "var(--a)" }}>ALARM</div><div className="big" style={{ fontSize: 56 }}>{new Date(now).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div><p>{ringing.label}</p><div className="row" style={{ justifyContent: "center" }}><button onClick={snooze}>Snooze {ringing.snooze || 9}m</button><button className="mic on" style={{ width: "auto" }} onClick={stopRing}>Dismiss</button></div></div></div>}
  </div></>);
}