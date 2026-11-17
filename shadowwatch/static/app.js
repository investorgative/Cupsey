const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ago=t=>{const s=Math.max(0,Date.now()/1000-t);return s<60?`${s|0}s`:s<3600?`${s/60|0}m`:s<86400?`${s/3600|0}h`:`${s/86400|0}d`};
const tfmt=t=>new Date(t*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
const mc=v=>!v?'–':v>=1e6?`$${(v/1e6).toFixed(2)}M`:`$${(v/1e3).toFixed(1)}K`;
const scoreColor=s=>s>=70?'#22c55e':s>=45?'#eab308':'#64748b';
let S=null, seen=new Set(), first=true;

document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.id==='tab-'+b.dataset.tab));
  try{localStorage.setItem('tab',b.dataset.tab)}catch(e){}
});
try{const t=localStorage.getItem('tab');if(t)document.querySelector(`nav button[data-tab="${t}"]`)?.click()}catch(e){}

async function api(path,body){
  const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
  if(r.status===401){location.href='/login';throw 0}
  return r.json();
}
function tokenLink(e){return `<a href="https://dexscreener.com/solana/${e.mint}" target="_blank" rel="noopener">${esc(e.symbol)}</a> <a class="muted mono" href="https://axiom.trade/meme/${e.mint}" target="_blank" rel="noopener" title="Open in Axiom">↗</a>`}

function renderStatus(){
  const w=S.watcher, lag=w.last_cycle?Date.now()/1000-w.last_cycle:999;
  const a=S.alerts, ch=['discord','ntfy','telegram'].filter(k=>a[k]);
  $('#status').innerHTML=
    `<span class="pill ${lag<30?'ok':'bad'}">● watcher ${lag<30?'live':'stalled'} · ${w.wallets} wallets · ${w.cycle_ms??'–'}ms</span>`+
    `<span class="pill ${ch.length?'ok':'bad'}">alerts: ${ch.join(', ')||'none configured'}</span>`+
    (S.tunnel_url?`<span class="pill ok" title="public link">🌐 ${esc(S.tunnel_url.replace('https://',''))}</span>`:'')+
    `<a class="pill" href="/logout">log out</a>`;
}
function renderSetups(){
  const el=$('#setups');
  if(!S.setups.length){el.innerHTML='<div class="empty">No shadow-wallet activity in the last 24h yet. Alerts fire as soon as it happens.</div>';return}
  el.innerHTML=S.setups.map(s=>{
    const cls=s.state.startsWith('LIVE')?'s-live':s.state.startsWith('EXIT')?'s-exit':s.state==='closed'?'s-closed':'s-wait';
    return `<div class="card"><div class="t"><span class="sym">${tokenLink(s)}</span><span class="state ${cls}">${esc(s.state)}</span></div>
      <div class="kv"><span>shadows <b>${s.shadows.length}</b></span><span>lead <b>${s.lead_s!=null?Math.round(s.lead_s)+'s':'–'}</b></span><span>mcap <b>${mc(s.mcap)}</b></span><span>${ago(s.last)} ago</span></div>
      <div class="muted small" style="margin-top:6px">${s.shadows.map(esc).join(', ')}</div></div>`}).join('');
}
function renderFeed(){
  const fs=$('#f-shadow').checked, fc=$('#f-cupsey').checked;
  const rows=S.events.filter(e=>(e.role==='shadow'&&fs)||(e.role==='cupsey'&&fc)).slice(0,200);
  $('#feed tbody').innerHTML=rows.length?rows.map(e=>`<tr class="${!first&&!seen.has(e.sig)?'flash':''}">
    <td class="mono">${tfmt(e.ts)}</td><td><span class="role ${e.role}">${e.role}</span> <a href="https://solscan.io/account/${e.wallet}" target="_blank" rel="noopener">${esc(e.label)}</a></td>
    <td class="${e.side}">${e.side}</td><td>${tokenLink(e)}</td><td class="mono">${(+e.sol).toFixed(3)}</td><td>${mc(e.mcap)}</td>
    <td><a class="muted" href="https://solscan.io/tx/${e.sig}" target="_blank" rel="noopener">tx</a></td></tr>`).join('')
    :'<tr><td colspan="7" class="muted" style="text-align:center;padding:18px">Waiting for trades…</td></tr>';
}
function walletCard(w){
  const s=w.score??null, live=w.live;
  return `<div class="w"><div class="top">
    <div><div><b>${esc(w.label)}</b> <span class="tier ${esc(w.tier||'low')}">${esc(w.tier||'')}</span></div>
      <div class="addr"><a href="https://solscan.io/account/${w.address}" target="_blank" rel="noopener">${w.address}</a></div></div>
    ${s!=null?`<div class="score" title="conviction score"><div class="bar"><i style="width:${s}%;background:${scoreColor(s)}"></i></div><b>${Math.round(s)}</b></div>`:''}
    <div class="toggle"><span class="muted small">watch</span><div class="switch ${w.enabled?'on':''}" data-a="${w.address}" data-on="${w.enabled?1:0}"></div>
      ${w.manual?`<button class="ghost small" data-del="${w.address}">remove</button>`:''}</div></div>
    ${w.stats?`<div class="kv">${Object.entries(w.stats).map(([k,v])=>`<span>${esc(k)} <b>${esc(v)}</b></span>`).join('')}</div>`:''}
    ${w.evidence?.length?`<ul>${w.evidence.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}
    ${live?`<div class="kv"><span>since install: <b>${live.buys}</b> buys / <b>${live.sells}</b> sells</span><span>last seen <b>${ago(live.last)} ago</b></span></div>`:''}
  </div>`;
}
function renderWallets(){
  const sh=S.wallets.filter(w=>w.role==='shadow').sort((a,b)=>(b.score??101)-(a.score??101));
  $('#gen').textContent=S.generated?`Discovery run: ${S.generated}. ${S.summary||''}`:'';
  $('#wallets').innerHTML=sh.map(walletCard).join('')||'<div class="empty">No shadow wallets yet.</div>';
  $('#cwallets').innerHTML=S.wallets.filter(w=>w.role==='cupsey').map(walletCard).join('');
  document.querySelectorAll('.switch').forEach(sw=>sw.onclick=async()=>{await api('/api/wallet',{address:sw.dataset.a,enabled:sw.dataset.on!=='1'});load()});
  document.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{if(confirm('Remove this wallet?')){await api('/api/wallet',{address:b.dataset.del,delete:true});load()}});
}
function renderCupsey(){
  const ev=S.events.filter(e=>e.role==='cupsey').slice(0,100);
  const sb=S.events.filter(e=>e.role==='shadow'&&e.side==='BUY');
  $('#cfeed tbody').innerHTML=ev.length?ev.map(e=>{
    const pre=e.side==='BUY'?sb.filter(x=>x.mint===e.mint&&x.ts<=e.ts&&e.ts-x.ts<600):[];
    return `<tr><td class="mono">${tfmt(e.ts)}</td><td>${esc(e.label)}</td><td class="${e.side}">${e.side}</td><td>${tokenLink(e)}</td><td class="mono">${(+e.sol).toFixed(3)}</td><td>${mc(e.mcap)}</td>
    <td>${pre.length?`<b style="color:var(--green)">yes · ${new Set(pre.map(x=>x.label)).size} shadow(s), ${Math.round(e.ts-Math.min(...pre.map(x=>x.ts)))}s earlier</b>`:'<span class="muted">–</span>'}</td></tr>`}).join('')
    :'<tr><td colspan="7" class="muted" style="text-align:center;padding:18px">No Cupsey trades seen yet.</td></tr>';
}
function renderMethod(){ $('#method').innerHTML=S.method||'<p class="muted">No discovery report.</p>' }
function notify(){
  if(first) return;
  for(const e of S.events){ if(seen.has(e.sig)) continue;
    if(['setup','shadow_sell'].includes(e.alert)&&window.Notification&&Notification.permission==='granted'){
      new Notification(e.alert==='setup'?`SETUP: ${e.symbol}`:`EXIT: shadow selling ${e.symbol}`,{body:`${e.label} ${e.side} ${(+e.sol).toFixed(2)} SOL`});
    }}
}
async function load(){
  try{S=await api('/api/state')}catch(e){return}
  notify(); renderStatus(); renderSetups(); renderFeed(); renderWallets(); renderCupsey(); renderMethod();
  S.events.forEach(e=>seen.add(e.sig)); first=false;
}
$('#f-shadow').onchange=$('#f-cupsey').onchange=renderFeed;
$('#notif').onclick=()=>window.Notification&&Notification.requestPermission();
$('#test').onclick=async()=>{await api('/api/test-alert',{});$('#test').textContent='Sent ✓'};
$('#addw').onsubmit=async e=>{e.preventDefault();await api('/api/wallet',{address:$('#addr').value.trim(),label:$('#lbl').value.trim()||null,role:$('#role').value,add:true,enabled:true});e.target.reset();load()};
load(); setInterval(load,3000);
