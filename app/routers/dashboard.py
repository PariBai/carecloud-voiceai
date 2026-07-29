"""A lightweight read-only dashboard UI.

The REST API (`/patients`) stays pure JSON for the evaluators. This page is a
separate, self-contained HTML view that fetches that same endpoint and renders
it as searchable cards — the "simple web UI" bonus. A card layout shows every
field at a glance without the horizontal scrolling a wide table forces on
narrow screens. No build step, no external assets, everything inline.
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
  header{padding:22px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
  h1{font-size:1.25rem;margin:0}
  .count{background:var(--brand);color:#fff;border-radius:20px;padding:2px 12px;font-size:.85rem;font-weight:600}
  .sub{color:var(--muted);font-size:.9rem}
  .bar{padding:16px 24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  input{flex:1;min-width:200px;padding:10px 14px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink);font-size:.95rem}
  button{padding:10px 16px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink);cursor:pointer;font-size:.9rem}
  button:hover{border-color:var(--brand)}
  a{color:var(--brand)}
  .grid{padding:4px 24px 44px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
  .patient{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .phead{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:12px}
  .pname{font-size:1.1rem;font-weight:700}
  .pdate{color:var(--muted);font-size:.78rem;white-space:nowrap}
  .row{display:flex;gap:10px;padding:5px 0;border-top:1px solid var(--line);font-size:.9rem}
  .row:first-of-type{border-top:none}
  .k{color:var(--muted);min-width:96px;flex-shrink:0}
  .v{font-weight:500;word-break:break-word}
  .empty{padding:50px 24px;text-align:center;color:var(--muted)}
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
<div class="grid" id="grid"></div>
<div class="empty" id="empty" style="display:none">No patients yet. Call the number above to register the first one.</div>
<script>
let ALL=[];
function phone(p){return p&&p.length===10?`(${p.slice(0,3)}) ${p.slice(3,6)}-${p.slice(6)}`:(p||"—");}
function esc(s){return (s??"").toString().replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
function row(k,v){return v?`<div class="row"><span class="k">${k}</span><span class="v">${esc(v)}</span></div>`:"";}
function card(p){
  const addr=[p.address_line_1,p.address_line_2].filter(Boolean).join(', ');
  const cityline=[p.city,p.state].filter(Boolean).join(', ')+(p.zip_code?' '+p.zip_code:'');
  const emerg=p.emergency_contact_name?`${p.emergency_contact_name} (${phone(p.emergency_contact_phone)})`:'';
  const ins=[p.insurance_provider,p.insurance_member_id].filter(Boolean).join(' · ');
  return `<div class="patient">
    <div class="phead"><span class="pname">${esc(p.first_name)} ${esc(p.last_name)}</span>
      <span class="pdate">${esc((p.created_at||'').slice(0,10))}</span></div>
    ${row('Date of birth',p.date_of_birth)}
    ${row('Sex',p.sex)}
    ${row('Phone',phone(p.phone_number))}
    ${row('Email',p.email)}
    ${row('Address',addr)}
    ${row('City / State',cityline)}
    ${row('Language',p.preferred_language)}
    ${row('Insurance',ins)}
    ${row('Emergency',emerg)}
  </div>`;
}
function render(list){
  document.getElementById('empty').style.display=list.length?'none':'block';
  document.getElementById('grid').innerHTML=list.map(card).join('');
}
function filter(){
  const q=document.getElementById('q').value.toLowerCase().trim();
  render(!q?ALL:ALL.filter(p=>[p.first_name,p.last_name,p.phone_number,p.city,p.state,p.email]
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
