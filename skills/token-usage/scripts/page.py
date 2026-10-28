"""page.py: DaisyDisk-style sunburst page for token_usage.py (self-contained HTML, no external resources)."""
import json

L10N = {
 "en": {"title": "Claude Code token usage", "reset": "resets", "used": "used, left", "in": "in", "all": "All",
        "window": "Window", "project": "Project", "conversation": "Conversation", "action": "Request",
        "of_window": "of window", "weight": "weight (est.)", "tokens": "tokens read", "ctx": "new context", "out": "written", "req": "requests",
        "units": "units", "back": "click: back", "left": "left",
        "footer": "Measured: the app's percentages and the tokens of local transcripts (once per request, subagents included). Estimated: the weight (cache read 0.1, new context 1.25, written 5) and the budget derived from the percentage. Sessions run on other machines are not in the rings. A request is one call to the model; session startups carry the initial context, not a command."},
 "fr": {"title": "Consommation de tokens Claude Code", "reset": "remise à zéro", "used": "utilisé, reste", "in": "dans", "all": "Tout",
        "window": "Fenêtre", "project": "Projet", "conversation": "Conversation", "action": "Requête",
        "of_window": "de la fenêtre", "weight": "poids (estimé)", "tokens": "tokens lus", "ctx": "contexte neuf", "out": "écrit", "req": "requêtes",
        "units": "unités", "back": "clic : retour", "left": "reste",
        "footer": "Mesuré : les pourcentages de l'app et les tokens des transcriptions locales (une fois par requête, sous-agents compris). Estimé : le poids (contexte relu 0,1, contexte neuf 1,25, texte écrit 5) et le budget déduit du pourcentage. Les sessions d'autres machines ne sont pas dans les anneaux. Une requête est un appel au modèle ; les démarrages de session portent le contexte initial, pas une commande."},
}

TEMPLATE = r"""<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><title>__TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#2C3035;--panel:#23272b;--text:#e8eaed;--muted:#9aa3ad;--accent:#38bdf8;--green:#22c55e;--line:#3a3f46}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,-apple-system,"Helvetica Neue",Arial,sans-serif}
header{padding:18px 28px 10px;display:flex;gap:28px;align-items:flex-start;flex-wrap:wrap;border-bottom:1px solid var(--line)}
header h1{font-size:17px;font-weight:600;margin:0 0 6px}header .sub{color:var(--muted);font-size:12.5px}
.quotas{display:flex;gap:22px;flex-wrap:wrap}.q{min-width:220px}.q .lab{font-size:12px;color:var(--muted);display:flex;justify-content:space-between;gap:14px}
.q .bar{height:8px;background:#1b1e22;border-radius:4px;margin:5px 0 3px;overflow:hidden}.q .bar i{display:block;height:100%;border-radius:4px}
.q .pct{font-size:13px}.q .pct b{font-size:16px}
main{display:grid;grid-template-columns:minmax(420px,560px) 1fr;min-height:calc(100vh - 110px)}
#sun{padding:16px 10px 10px 20px}#sun svg{width:100%;height:auto;display:block}
path.seg{cursor:pointer;stroke:var(--bg);stroke-width:1.2px;transition:opacity .12s}path.seg.dim{opacity:.28}
#centre{cursor:pointer}
aside{padding:18px 24px 24px 10px;border-left:1px solid var(--line);overflow:auto}
.crumb{color:var(--muted);font-size:12.5px;margin-bottom:8px;height:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.crumb span{cursor:pointer}.crumb span:hover{color:var(--accent)}
.hover{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:14px;height:124px;overflow:hidden}
.hover h2{margin:0 0 4px;font-size:15px;font-weight:600;height:21px;line-height:21px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hover .meta{color:var(--muted);font-size:12.5px;height:18px;line-height:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hover .nums{display:flex;gap:18px;margin-top:8px;flex-wrap:nowrap;height:40px;overflow:hidden}.hover .nums div{font-size:12px;color:var(--muted);white-space:nowrap}.hover .nums b{display:block;font-size:15px;color:var(--text)}
table{width:100%;border-collapse:collapse;font-size:13px}td{padding:0 6px;height:30px;border-bottom:1px solid var(--line);vertical-align:middle;white-space:nowrap}
td.nom{white-space:nowrap;max-width:380px;overflow:hidden;text-overflow:ellipsis}tr{cursor:pointer}tr:hover td{background:#2f343a}
td .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:8px;vertical-align:-1px}
td .b{display:inline-block;height:7px;background:#1b1e22;border-radius:3px;width:90px;vertical-align:middle}td .b i{display:block;height:100%;border-radius:3px}
td.r{text-align:right;color:var(--muted)}td.r b{color:var(--text);font-weight:500}
footer{padding:10px 28px 18px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
@media(max-width:900px){main{grid-template-columns:1fr}aside{border-left:0;border-top:1px solid var(--line)}}
</style></head><body>
<header>
 <div><h1>__TITLE__</h1><div class="sub" id="sub"></div></div>
 <div class="quotas" id="quotas"></div>
</header>
<main>
 <div id="sun"></div>
 <aside>
  <div class="crumb" id="crumb"></div>
  <div class="hover" id="hover"></div>
  <table><tbody id="liste"></tbody></table>
 </aside>
</main>
<footer>__FOOTER__</footer>
<script>
const D = __DATA__; const S = D.strings; const FR = D.lang === 'fr';
const fmt = n => { const s = x => FR ? x.replace('.', ',') : x; return n>=1e9?s((n/1e9).toFixed(2))+' G':n>=1e6?s((n/1e6).toFixed(2))+' M':n>=1e3?Math.round(n/1e3)+' k':Math.round(n)+''; };
const pct = (a,b) => b?Math.round(a/b*100):0;
document.getElementById('sub').textContent = D.subtitle;
const Q = document.getElementById('quotas');
for (const w of D.quotas) {
  const col = w.pct>=85?'#ef4444':w.pct>=65?'#f59e0b':'var(--green)';
  Q.insertAdjacentHTML('beforeend', `<div class="q"><div class="lab"><span>${esc(w.label)}</span><span>${S.reset} ${esc(w.reset)}</span></div><div class="bar"><i style="width:${w.pct}%;background:${col}"></i></div><div class="pct"><b>${w.pct} %</b> ${S.used} ${100-w.pct} % (${S.in} ${esc(w.in)})</div></div>`);
}
let id=0; function prep(n,parent,depth){n.id=id++;n.parent=parent;n.depth=depth;if(n.children){n.children.sort((a,b)=>b.v-a.v);n.children.forEach(c=>prep(c,n,depth+1));}} prep(D.tree,null,0);
const HUES=[200,30,140,80,280,350,50,170,320,110,240,15];
function hue(n){while(n.depth>1)n=n.parent;return n.depth===1?HUES[n.parent.children.indexOf(n)%HUES.length]:210;}
function color(n){const h=hue(n);const l=n.others?30:n.depth===1?52:n.depth===2?44:38;const s=n.others?22:70;return `hsl(${h} ${s}% ${l}%)`;}
const R0=78,W=60,RINGS=3,SIZE=2*(R0+W*RINGS)+8,C=SIZE/2;
const NS='http://www.w3.org/2000/svg';
const svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox',`0 0 ${SIZE} ${SIZE}`);document.getElementById('sun').appendChild(svg);
function arc(a0,a1,r0,r1){const g=a=>[C+r1*Math.cos(a),C+r1*Math.sin(a)];const h=a=>[C+r0*Math.cos(a),C+r0*Math.sin(a)];if(a1-a0>=2*Math.PI-1e-6)a1=a0+2*Math.PI-1e-4;const big=a1-a0>Math.PI?1:0;const [x0,y0]=g(a0),[x1,y1]=g(a1),[x2,y2]=h(a1),[x3,y3]=h(a0);return `M${x0},${y0}A${r1},${r1},0,${big},1,${x1},${y1}L${x2},${y2}A${r0},${r0},0,${big},0,${x3},${y3}Z`;}
let root=D.tree;
function draw(){
  svg.innerHTML='';
  const rec=(n,a0,a1,depth)=>{if(depth>RINGS||!n.children)return;let a=a0;const span=a1-a0;for(const c of n.children){const da=n.v?span*c.v/n.v:0;if(da>0.0025){const p=document.createElementNS(NS,'path');p.setAttribute('d',arc(a,a+da,R0+W*(depth-1)+2,R0+W*depth-1));p.setAttribute('class','seg');p.setAttribute('fill',color(c));p.dataset.id=c.id;p.addEventListener('mouseenter',()=>hover(c));p.addEventListener('mouseleave',()=>hover(null));p.addEventListener('click',()=>zoom(c));svg.appendChild(p);rec(c,a,a+da,depth+1);}a+=da;}};
  rec(root,-Math.PI/2,3*Math.PI/2,1);
  const circle=document.createElementNS(NS,'circle');circle.setAttribute('cx',C);circle.setAttribute('cy',C);circle.setAttribute('r',R0-4);circle.setAttribute('fill','#1b1e22');circle.setAttribute('id','centre');circle.addEventListener('click',()=>{if(root.parent)zoom(root.parent);});svg.appendChild(circle);
  const t=(y,txt,size,col)=>{const e=document.createElementNS(NS,'text');e.setAttribute('x',C);e.setAttribute('y',y);e.setAttribute('text-anchor','middle');e.setAttribute('font-size',size);e.setAttribute('fill',col);e.setAttribute('style','pointer-events:none');e.textContent=txt;svg.appendChild(e);};
  if(root.parent){t(C-10,root.name.length>18?root.name.slice(0,17)+'…':root.name,12,'#e8eaed');t(C+8,fmt(root.v)+' '+S.units,11,'#9aa3ad');t(C+24,S.back,10,'#38bdf8');}
  else if(D.main_quota){const q=D.main_quota;t(C-14,q.label,10,'#9aa3ad');t(C+8,q.pct+' %',24,q.pct>=85?'#ef4444':q.pct>=65?'#f59e0b':'#22c55e');t(C+26,S.left+' '+(100-q.pct)+' %',11,'#9aa3ad');}
  else{t(C-4,fmt(root.v),20,'#e8eaed');t(C+16,S.units,11,'#9aa3ad');}
  list();hover(null);
}
function path(n){const l=[];for(let x=n;x;x=x.parent)l.unshift(x);return l;}
function zoom(n){if(!n.children)n=n.parent;root=n;draw();}
function isDesc(id,n){const rec=(m)=>String(m.id)===id||(m.children||[]).some(rec);return rec(n);}
function hover(n){
  document.querySelectorAll('path.seg').forEach(p=>p.classList.toggle('dim',!!n&&!path(n).some(x=>String(x.id)===p.dataset.id)&&!isDesc(p.dataset.id,n)));
  const H=document.getElementById('hover');const x=n||root;const total=D.tree.v;
  const typ=x.depth===0?S.window:x.depth===1?S.project:x.depth===2?S.conversation:S.action;
  H.innerHTML=`<h2>${typ} : ${esc(x.name)}</h2><div class="meta">${esc(x.meta||'')}</div><div class="nums"><div><b>${pct(x.v,total)} %</b>${S.of_window}</div><div><b>${fmt(x.v)}</b>${S.weight}</div><div><b>${fmt(x.tokens||0)}</b>${S.tokens}</div><div><b>${fmt(x.ctx||0)}</b>${S.ctx}</div><div><b>${fmt(x.out||0)}</b>${S.out}</div><div><b>${x.n||1}</b>${S.req}</div></div>`;
}
function list(){
  const L=document.getElementById('liste');L.innerHTML='';
  document.getElementById('crumb').innerHTML=path(root).map(x=>`<span data-id="${x.id}">${esc(x.depth?x.name.slice(0,30):S.all)}</span>`).join(' › ');
  document.querySelectorAll('.crumb span').forEach(s=>s.addEventListener('click',()=>{zoom(find(D.tree,s.dataset.id));}));
  for(const c of root.children||[]){
    const tr=document.createElement('tr');const part=pct(c.v,root.v);
    tr.innerHTML=`<td><span class="sw" style="background:${color(c)}"></span><span class="b"><i style="width:${part}%;background:${color(c)}"></i></span></td><td class="r"><b>${part} %</b></td><td class="nom">${esc(c.name)}${c.meta?` <span style="color:var(--muted)">· ${esc(c.meta)}</span>`:''}</td><td class="r"><b>${fmt(c.v)}</b></td><td class="r">${c.n?c.n+' '+S.req.slice(0,3)+'.':''}</td>`;
    tr.addEventListener('mouseenter',()=>hover(c));tr.addEventListener('mouseleave',()=>hover(null));tr.addEventListener('click',()=>zoom(c));L.appendChild(tr);
  }
}
function find(n,id){if(String(n.id)===String(id))return n;for(const c of n.children||[]){const r=find(c,id);if(r)return r;}return null;}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
draw();
</script></body></html>
"""


def write_html(path, tree, quotas, main_quota, subtitle, lang="en"):
    s = L10N.get(lang, L10N["en"])
    data = {"tree": tree, "quotas": quotas, "main_quota": main_quota, "subtitle": subtitle, "lang": lang, "strings": s}
    page = (TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__TITLE__", s["title"]).replace("__FOOTER__", s["footer"]).replace("__LANG__", lang))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
