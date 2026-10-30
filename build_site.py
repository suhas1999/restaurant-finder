"""Build a phone-friendly static site in docs/ from results/<Town>_*.xlsx (served by GitHub Pages).

Usage: python3 build_site.py   ->  docs/index.html + docs/<town>/index.html for every town in results/
"""
import html
import json
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).parent
RESULTS, DOCS = HERE / "results", HERE / "docs"
WORKER_URL = "https://restaurant-finder.suhas1999.workers.dev"  # Cloudflare Worker in worker/

CSS = """
:root{--bg:#f6f4ef;--card:#fff;--text:#1d1d1f;--muted:#6b6b70;--accent:#c2410c;--star:#f59e0b;--line:#e7e3da}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--card:#1e1e1e;--text:#f2f2f2;--muted:#a0a0a5;--accent:#fb923c;--line:#2c2c2c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:17px/1.4 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif}
header{padding:20px 16px 8px}h1{margin:0;font-size:26px}header p{margin:4px 0 0;color:var(--muted);font-size:15px}
.tabs{position:sticky;top:0;z-index:2;display:flex;gap:8px;padding:10px 16px;background:var(--bg);border-bottom:1px solid var(--line)}
.tabs button{flex:1;padding:12px;border:0;border-radius:12px;font-size:16px;font-weight:600;background:var(--card);color:var(--text);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.tabs button.on{background:var(--accent);color:#fff}
.note{margin:12px 16px 0;color:var(--muted);font-size:14px}
ol{list-style:none;margin:0;padding:12px 16px 40px}
li{background:var(--card);border-radius:14px;padding:14px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);display:flex;gap:12px}
.rank{flex:none;width:34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;display:grid;place-items:center;font-size:15px}
.body{min-width:0;flex:1}.name{font-weight:700;font-size:18px;overflow-wrap:anywhere}
.meta{color:var(--muted);font-size:14px;margin-top:2px}.stars{color:var(--star);font-weight:700}
.addr{color:var(--muted);font-size:14px;margin-top:6px}
.btns{display:flex;gap:8px;margin-top:10px}.btns a{flex:1;text-align:center;padding:10px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px;border:1px solid var(--line);color:var(--text)}
.btns a.none{color:var(--muted);font-weight:400}.btns a{white-space:nowrap}.btns a.map{background:var(--accent);color:#fff;border-color:var(--accent)}
.towns a{display:block;margin:12px 16px;padding:18px;background:var(--card);border-radius:14px;text-decoration:none;color:var(--text);font-size:20px;font-weight:700;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.hidden{display:none}
.add{margin:8px 16px 4px;display:flex;gap:8px}.add input{flex:1;min-width:0;padding:14px;font-size:17px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--text)}
.add button{padding:14px 18px;border:0;border-radius:12px;background:var(--accent);color:#fff;font-size:17px;font-weight:700}.add button:disabled{opacity:.5}
#prog{margin:8px 16px;padding:14px;background:var(--card);border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
#prog .t{font-weight:700}#prog .msg{color:var(--muted);font-size:15px;margin-top:4px}#prog ul{list-style:none;margin:10px 0 0;padding:0}
#prog li{background:none;box-shadow:none;padding:4px 0;margin:0;display:block;font-size:15px}#prog a{color:var(--accent);font-weight:700}
h2{margin:18px 16px 0;font-size:15px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
"""

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}</style></head><body>"""


def read(path):
    rows = list(load_workbook(path).active.iter_rows(values_only=True))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def card(r):
    e = lambda v: html.escape(str(v or ""))
    rating = f'<span class="stars">★ {r["Rating"]}</span> · {int(r["Reviews"] or 0):,} reviews' if r["Rating"] else "No rating"
    km = f' · {r["Km from Centre"]} km' if r.get("Km from Centre") is not None else ""
    phone = str(r["Phone"] or "").strip()
    call = f'<a href="tel:{e(phone.replace(" ", ""))}">📞 {e(phone)}</a>' if phone else '<a class="none">No phone listed</a>'
    return (f'<li><div class="rank">{r["Rank"]}</div><div class="body"><div class="name">{e(r["Restaurant Name"])}</div>'
            f'<div class="meta">{rating}</div><div class="meta">{e(r["Category"])}{km}</div>'
            f'<div class="addr">{e(r["Address"])}</div>'
            f'<div class="btns"><a class="map" href="{e(r["Google Maps Link"])}">📍 Open in Maps</a>{call}</div></div></li>')


def town_page(town, top, pop):
    return (HEAD.format(title=f"{town} Restaurants", css=CSS)
            + f'<header><h1>🍽️ {html.escape(town)}</h1><p>Best restaurants from Google Maps reviews</p></header>'
            + '<div class="tabs"><button class="on" data-t="top">⭐ Top Rated</button><button data-t="pop">🔥 Most Popular</button></div>'
            + '<p class="note" id="n-top">Best ratings, with more weight to places that have many reviews.</p>'
            + '<p class="note hidden" id="n-pop">Most reviewed places rated 4.0 or above.</p>'
            + '<ol id="top">' + "".join(card(r) for r in top) + "</ol>"
            + '<ol id="pop" class="hidden">' + "".join(card(r) for r in pop) + "</ol>"
            + """<script>document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
['top','pop'].forEach(t=>{document.getElementById(t).classList.toggle('hidden',t!==b.dataset.t);
document.getElementById('n-'+t).classList.toggle('hidden',t!==b.dataset.t)});scrollTo(0,0)})</script></body></html>""")


def main():
    towns = sorted(p.name[:-len("_top_rated.xlsx")] for p in RESULTS.glob("*_top_rated.xlsx") if not p.name.startswith("~$"))
    for t in towns:
        top, pop = read(RESULTS / f"{t}_top_rated.xlsx"), read(RESULTS / f"{t}_most_popular.xlsx")
        out = DOCS / t.lower()
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(town_page(t.replace("_", " "), top, pop))
        print(f"docs/{t.lower()}/index.html: {len(top)} top rated, {len(pop)} most popular")
    (DOCS / "towns.json").write_text(json.dumps([{"name": t.replace("_", " "), "slug": t.lower()} for t in towns]))
    links = "".join(f'<a href="{t.lower()}/">{html.escape(t.replace("_", " "))} →</a>' for t in towns)
    (DOCS / "index.html").write_text(
        HEAD.format(title="Restaurant Finder", css=CSS)
        + '<header><h1>🍽️ Restaurant Finder</h1><p>Find the best restaurants in any town</p></header>'
        + '<form class="add" id="f"><input id="q" placeholder="Type a town, e.g. Tanuku" autocomplete="off" required>'
        + '<button id="go">Find</button></form>'
        + '<form class="add hidden" id="pwf"><input id="pw" type="password" placeholder="Password to add new towns" autocomplete="current-password"></form><div id="prog" class="hidden"></div>'
        + f'<h2>Towns</h2><div class="towns">{links}</div>'
        + ADD_SCRIPT.replace("WORKER_URL", WORKER_URL) + "</body></html>")


# Home page search box: open the town if we already have it, else ask the Worker to start a GitHub Actions run
# and show its steps until the new page is live.
ADD_SCRIPT = """<script>
const W='WORKER_URL', P=document.getElementById('prog'), B=document.getElementById('go');
const LABEL={'Get code':'Starting','Set up Python':'Starting','Install packages':'Starting','Check town name':'Checking town name',
 'Search Google Maps':'Searching Google Maps (2-4 min)','Build website':'Building the page','Publish':'Saving'};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const show=(t,msg,steps)=>{P.classList.remove('hidden');P.innerHTML='<div class="t">'+t+'</div>'+(msg?'<div class="msg">'+msg+'</div>':'')+(steps||'')};
const slugOf=t=>t.trim().split(/\\s+/).join('_').toLowerCase();
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const PW=document.getElementById('pw'), PWF=document.getElementById('pwf');
const savedPw=()=>{try{return localStorage.getItem('rf_pw')||''}catch(e){return ''}};
const savePw=v=>{try{v?localStorage.setItem('rf_pw',v):localStorage.removeItem('rf_pw')}catch(e){}};
document.getElementById('f').onsubmit=async e=>{
 e.preventDefault(); const town=document.getElementById('q').value.trim(); if(!town)return;
 const have=await fetch('towns.json?'+Date.now()).then(r=>r.json()).catch(()=>[]);
 const hit=have.find(t=>t.slug===slugOf(town)); if(hit){location.href=hit.slug+'/';return}
 const password=PW.value||savedPw();
 if(!password){PWF.classList.remove('hidden');PW.focus();show(esc(town)+' is new','Enter the password to add it.');return}
 B.disabled=true; show('Starting search for '+esc(town)+'…');
 try{
  const r=await fetch(W+'/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({town,password})}).then(r=>r.json());
  if(r.badPassword){savePw('');PW.value='';PWF.classList.remove('hidden');PW.focus();show('Wrong password','Please check it and try again.');B.disabled=false;return}
  savePw(password);PWF.classList.add('hidden');
  if(r.error){show('Could not search',esc(r.error));B.disabled=false;return}
  if(r.exists){location.href=r.slug+'/';return}
  const t0=Date.now();
  while(true){
   await wait(5000);
   const s=await fetch(W+'/status?town='+encodeURIComponent(r.town)).then(r=>r.json()).catch(()=>({steps:[]}));
   const seen=new Set(), rows=(s.steps||[]).filter(x=>LABEL[x.name]&&!seen.has(LABEL[x.name])&&seen.add(LABEL[x.name]))
    .map(x=>'<li>'+(x.conclusion==='success'?'✅':x.conclusion==='failure'?'❌':x.status==='in_progress'?'⏳':'⬜')+' '+LABEL[x.name]+'</li>');
   const mins=Math.floor((Date.now()-t0)/60000), secs=Math.floor((Date.now()-t0)/1000)%60;
   if(s.status==='completed'){
    if(s.conclusion!=='success'){show('Could not add '+esc(r.town),'The search failed. Check the town name and try again.','<ul>'+rows.join('')+'</ul>');B.disabled=false;return}
    break}
   show('Adding '+esc(r.town)+'…','Time so far: '+mins+'m '+secs+'s. You can keep this page open.','<ul>'+rows.join('')+'</ul>');
  }
  for(let i=0;i<60;i++){
   show('Almost done…','Publishing the '+esc(r.town)+' page (about 1 min)');
   if((await fetch(r.slug+'/?'+Date.now(),{method:'HEAD'})).ok)break; await wait(5000)}
  show('✅ '+esc(r.town)+' is ready','<a href="'+r.slug+'/">Open '+esc(r.town)+' →</a>');
  setTimeout(()=>location.href=r.slug+'/',1500);
 }catch(err){show('Could not search','Please check your internet and try again.');B.disabled=false}
};
</script>"""

if __name__ == "__main__":
    main()
