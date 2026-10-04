// ATLAS RAG backend: upload -> chunk -> BM25 retrieval -> grounded answer (Claude if key set, else extractive)
const express = require("express"), cors = require("cors"), multer = require("multer"), fs = require("fs");
const pdf = require("pdf-parse/lib/pdf-parse.js"), mammoth = require("mammoth");
const app = express(), up = multer({ storage: multer.memoryStorage() });
app.use(cors(), express.json({ limit: "1mb" }));
const DB = "atlas_docs.json"; let docs = fs.existsSync(DB) ? JSON.parse(fs.readFileSync(DB)) : [];
const save = () => fs.writeFileSync(DB, JSON.stringify(docs));
const STOP = new Set("the is a an of to and in on for with what how why who when are was be this that it as at by from".split(" "));
const tok = (s) => s.toLowerCase().match(/[a-z0-9]{2,}/g) || [];
const chunk = (t) => { t = t.replace(/\s+/g, " "); const o = []; for (let i = 0; i < t.length; i += 700) o.push(t.slice(i, i + 900)); return o; };
function search(q, k = 4) {
  const qt = tok(q).filter((w) => !STOP.has(w)), all = [];
  docs.forEach((d) => d.chunks.forEach((c) => all.push({ doc: d.name, c, t: tok(c) })));
  const N = all.length || 1, avg = all.reduce((s, x) => s + x.t.length, 0) / N || 1, df = {};
  qt.forEach((w) => (df[w] = all.filter((x) => x.t.includes(w)).length));
  return all.map((x) => { const tf = {}; x.t.forEach((w) => (tf[w] = (tf[w] || 0) + 1)); let s = 0;
    qt.forEach((w) => { const f = tf[w] || 0; if (!f) return; s += Math.log(1 + (N - df[w] + .5) / (df[w] + .5)) * f * 2.2 / (f + 1.2 * (.25 + .75 * x.t.length / avg)); });
    return { ...x, s }; }).filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, k);
}
app.post("/upload", up.array("files"), async (req, res) => {
  try { const added = [];
    for (const f of req.files) { const n = f.originalname.toLowerCase(); let text;
      if (n.endsWith(".pdf")) text = (await pdf(f.buffer)).text;
      else if (n.endsWith(".docx")) text = (await mammoth.extractRawText({ buffer: f.buffer })).value;
      else text = f.buffer.toString("utf8");
      docs.push({ id: Date.now() + Math.random().toString(36).slice(2, 6), name: f.originalname, chunks: chunk(text) }); added.push(f.originalname); }
    save(); res.json({ added });
  } catch (e) { res.status(500).json({ error: e.message }); }
});
app.get("/docs", (_, r) => r.json(docs.map((d) => ({ id: d.id, name: d.name, chunks: d.chunks.length }))));
app.delete("/docs/:id", (q, r) => { docs = docs.filter((d) => d.id !== q.params.id); save(); r.json({ ok: 1 }); });
app.post("/ask", async (req, res) => {
  const { question, memory = [] } = req.body, hits = search(question);
  if (!hits.length) return res.json({ answer: "I couldn't find that in your uploaded documents.", sources: [] });
  const sources = [...new Set(hits.map((h) => h.doc))];
  if (process.env.ANTHROPIC_API_KEY) {
    try { const r = await fetch("https://api.anthropic.com/v1/messages", { method: "POST",
        headers: { "content-type": "application/json", "x-api-key": process.env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({ model: "claude-sonnet-5-5", max_tokens: 600,
          system: "You are ATLAS, a friendly student assistant. Answer ONLY from the context. If it is not there, say so. Be concise. About the student: " + memory.join("; "),
          messages: [{ role: "user", content: "Context:\n" + hits.map((h, i) => `[${i + 1}] ${h.c}`).join("\n\n") + "\n\nQuestion: " + question }] }) });
      const j = await r.json(); if (j.content) return res.json({ answer: j.content.map((b) => b.text || "").join(""), sources, mode: "claude" });
    } catch {}
  }
  res.json({ answer: hits.slice(0, 2).map((h) => h.c.slice(0, 350)).join(" ... "), sources, mode: "extractive" });
});
app.listen(8787, () => console.log("ATLAS backend on http://localhost:8787"));
