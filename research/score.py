"""Stage 2: rank candidate shadow wallets.
Inputs: tok/*.json (all trades in a window around each sampled Cupsey entry), cupsey trades, features.json
Signals:
  co-occurrence   - share of Cupsey's sampled tokens the wallet traded in the window
  timing          - entered in the same second as / before Cupsey
  slot test       - landed in the SAME or an EARLIER slot than Cupsey's buy (copy-traders can't)
  precision       - share of the wallet's OWN recent tokens that Cupsey also traded (filters snipers that buy everything)
  exit-liquidity  - bought before Cupsey and sold while he was still holding
"""
import json,os,collections,statistics,sys,time
from st import get, NCALLS
from rpc import tx
from concurrent.futures import ThreadPoolExecutor
CUPSEY=['2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK']
SOL='So11111111111111111111111111111111111111112'
toks=json.load(open('cupsey_tokens.json'))
fe=json.load(open('features.json')); F=fe['F']; N=fe['ntok']; EX=fe['EX']
ctr=json.load(open('trades_2fg5QD.json'))+json.load(open('trades_suqh5s.json'))
C_TOK=set(t['to']['address'] if t['from']['address']==SOL else t['from']['address'] for t in ctr)
C_MIN=min(t['time'] for t in ctr); C_MAX=max(t['time'] for t in ctr)

def prelim(c):
    t=c.get('tokens',0)
    return t/N*40 + (c.get('same_sec',0)+c.get('pre_buy',0))/max(t,1)*30 + c.get('exitliq',0)/max(1,t)*30
cands=[(w,c) for w,c in F.items() if c.get('tokens',0)>=max(6,0.05*N) and c.get('same_sec',0)+c.get('pre_buy',0)>=4]
cands.sort(key=lambda x:-prelim(x[1]))
print('candidates',len(cands))
TOP=cands[:70]

# ---- slot test ----
cache=json.load(open('slotcache.json')) if os.path.exists('slotcache.json') else {}
def slot(sig):
    if sig in cache and cache[sig]: return cache[sig]
    t=tx(sig); v=[t['slot'],t['transaction']['message']['accountKeys'][0]['pubkey']] if t else None
    cache[sig]=v; return v
tokdata={f[:-5]:json.load(open('tok/'+f)) for f in os.listdir('tok')}
pairs=collections.defaultdict(list)
for k,tr in tokdata.items():
    cb=[t for t in tr if t['wallet'] in CUPSEY and t['type']=='buy']
    if not cb: continue
    c0=min(cb,key=lambda t:t['time'])
    first={}
    for t in tr:
        if t['type']=='buy' and t['wallet'] not in first: first[t['wallet']]=t
    for w,_ in TOP:
        b=first.get(w)
        if b and -60000<=b['time']-c0['time']<=5000: pairs[w].append((c0['tx'],b['tx']))
need=set()
for w,_ in TOP:
    for a,b in pairs[w][:8]: need|={a,b}
with ThreadPoolExecutor(3) as ex: list(ex.map(slot,need))
json.dump(cache,open('slotcache.json','w'))
SLOT={}
for w,_ in TOP:
    d=[cache[b][0]-cache[a][0] for a,b in pairs[w][:8] if cache.get(a) and cache.get(b)]
    SLOT[w]=d

# ---- precision via wallet history (SolanaTracker, 1 credit/page) ----
pc=json.load(open('preccache.json')) if os.path.exists('preccache.json') else {}
def precision(w):
    if w in pc: return pc[w]
    try: j=get(f'/wallet/{w}/trades')
    except Exception as e: return None
    tr=[t for t in j['trades'] if C_MIN<=t['time']<=C_MAX]
    tk=set(t['to']['address'] if t['from']['address']==SOL else t['from']['address'] for t in tr)
    tk.discard(SOL)
    allt=set(t['to']['address'] if t['from']['address']==SOL else t['from']['address'] for t in j['trades'])
    span=(j['trades'][0]['time']-j['trades'][-1]['time'])/3.6e6 if j['trades'] else 0
    r={'n':len(tk),'hit':len(tk&C_TOK),'trades':len(j['trades']),'span_h':round(span,1),'tokens_total':len(allt)}
    pc[w]=r; json.dump(pc,open('preccache.json','w')); return r

def score(w,c):
    t=c.get('tokens',0); sd=SLOT.get(w,[])
    cooc=min(1,t/N/0.5)
    early=(c.get('same_sec',0)+c.get('pre_buy',0))/max(t,1)
    slot_ok=(sum(x<=0 for x in sd)/len(sd)) if len(sd)>=3 else None
    p=PREC.get(w); prec=(p['hit']/p['n']) if p and p['n']>=5 else None
    exl=c.get('exitliq',0)/max(1,c.get('pre_buy',0)+c.get('same_sec',0))
    s=30*cooc+10*early+10*min(1,exl*2)
    s+=25*(slot_ok if slot_ok is not None else 0.3)
    s+=25*(prec if prec is not None else 0.3)
    return round(min(100,s),1),dict(cooc=cooc,early=early,slot_ok=slot_ok,prec=prec,exl=exl)

PREC={}
pre=sorted(TOP,key=lambda x:-score(x[0],x[1])[0])
for w,c in pre[:45]:
    PREC[w]=precision(w)
res=[]
for w,c in TOP:
    s,parts=score(w,c); res.append((s,w,c,parts))
res.sort(reverse=True)
json.dump({'N':N,'res':res,'SLOT':SLOT,'PREC':PREC},open('scored.json','w'))
for s,w,c,p in res[:40]:
    print(f"{s:5.1f} {w[:10]} tok {c.get('tokens',0):3d} ss {c.get('same_sec',0):3d} pre {c.get('pre_buy',0):3d} exl {c.get('exitliq',0):3d} slot {SLOT.get(w)} prec {PREC.get(w)}")
print('st calls',NCALLS)
