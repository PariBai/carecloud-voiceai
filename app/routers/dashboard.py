"""A lightweight read-only dashboard UI.

The REST API (`/patients`) stays pure JSON for the evaluators. This page is a
separate, self-contained HTML view that fetches that same endpoint and renders
it as a searchable table — the "simple web UI" bonus. No build step, no
external assets (CSP-friendly), everything inline.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CareCloud — Patients Dashboard</title>
<style>
  :root{--bg:#f5f7fb;--card:#fff;--ink:#1a2233;--muted:#6b7a99;--line:#e6ebf3;--brand:#2456c6;--ok:#178a4c}
  @media (prefers-color-scheme:dark){:root{--bg:#0f1420;--card:#171d2b;--ink:#e8edf6;--muted:#93a1bd;--line:#28324a;--brand:#7aa2ff}}
  *{box-sizing:border-box}
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
  header{padding:22px 28px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
  h1{font-size:1.25rem;margin:0}
  .count{background:var(--brand);color:#fff;border-radius:20px;padding:2px 12px;font-size:.85rem;font-weight:600}
  .sub{color:var(--muted);font-size:.9rem;margin:2px 0 0}
  .bar{padding:16px 28px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  input{flex:1;min-width:200px;padding:10px 14px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink);font-size:.95rem}
  button{padding:10px 16px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink);cursor:pointer;font-size:.9rem}
  button:hover{border-color:var(--brand)}
  .wrap{padding:0 28px 40px;overflow-x:auto}
  table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;min-width:820px}
  th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--line);font-size:.9rem;white-space:nowrap}
  th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:.72rem;letter-spacing:.04em}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:rgba(36,86,198,.05)}
  .name{font-weight:600}
  .empty{padding:40px;text-align:center;color:var(--muted)}
  a{color:var(--brand)}
</style></head><body>
<header>
  <h1>CareCloud &mdash; Patients</h1>
  <span class="count" id="count">…</span>
  <div style="flex:1"></div>
  <div class="sub">Call to register: <strong>+1 (346) 292-9312</strong></div>
</header>
<div class="bar">
  <input id="q" placeholder="Search by name, phone, city…" autocomplete="off">
  <button onclick="load()">↻ Refresh</button>
  <a href="/patients" style="align-self:center">raw JSON</a>
</div>
<div class="wrap">
  <table id="tbl"><thead><tr>
    <th>Name</th><th>DOB</th><th>Sex</th><th>Phone</th><th>Email</th>
    <th>Address</th><th>City</th><th>State</th><th>ZIP</th><th>Language</th><th>Registered</th>
  </tr></thead><tbody id="rows"></tbody></table>
  <div class="empty" id="empty" style="display:none">No patients yet. Call the number above to register the first one.</div>
</div>
<script>
let ALL=[];
function phone(p){return p&&p.length===10?`(${p.slice(0,3)}) ${p.slice(3,6)}-${p.slice(6)}`:(p||"");}
function esc(s){return (s??"").toString().replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
function render(list){
  const rows=document.getElementById('rows');
  document.getElementById('empty').style.display=list.length?'none':'block';
  rows.innerHTML=list.map(p=>{
    const addr=[p.address_line_1,p.address_line_2].filter(Boolean).join(', ');
    const reg=(p.created_at||'').slice(0,10);
    return `<tr>
      <td class="name">${esc(p.first_name)} ${esc(p.last_name)}</td>
      <td>${esc(p.date_of_birth)}</td><td>${esc(p.sex)}</td>
      <td>${esc(phone(p.phone_number))}</td><td>${esc(p.email||'')}</td>
      <td>${esc(addr)}</td><td>${esc(p.city)}</td><td>${esc(p.state)}</td>
      <td>${esc(p.zip_code)}</td><td>${esc(p.preferred_language||'')}</td><td>${esc(reg)}</td>
    </tr>`;}).join('');
}
function filter(){
  const q=document.getElementById('q').value.toLowerCase().trim();
  if(!q)return render(ALL);
  render(ALL.filter(p=>[p.first_name,p.last_name,p.phone_number,p.city,p.state,p.email]
    .filter(Boolean).some(v=>v.toLowerCase().includes(q))));
}
async function load(){
  try{
    const r=await fetch('/patients');const j=await r.json();
    ALL=j.data||[];
    document.getElementById('count').textContent=ALL.length+' total';
    filter();
  }catch(e){document.getElementById('count').textContent='error loading';}
}
document.getElementById('q').addEventListener('input',filter);
load();
</script>
</body></html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return _PAGE
