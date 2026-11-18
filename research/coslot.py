"""Operator graph: wallets that pre-buy (before Cupsey's slot) in the SAME SLOT on >=2 different
Cupsey coins are linked. Components = operators (throwaways included). Each operator is then scored
on both halves: coins pre-bought, coins sold into his pump, profit, exit before him."""
import json,collections,itertools,time
from holdout import entries, CUP
E=entries(); h=len(E)//2; half={e['mint']:('old' if i<h else 'new') for i,e in enumerate(E)}
pair=collections.defaultdict(set); act=collections.defaultdict(dict)
for e in E:
    tr=e['trades']; cb=e['cb']; fs=e['fs']
    cs=[t['slot'] for t in tr if t['wallet'] in CUP and t['type']=='buy' and t.get('slot')]
    if not cs: continue
    cslot=min(cs); S=collections.defaultdict(set); by=collections.defaultdict(list)
    for t in tr: by[t['wallet']].append(t)
    for w,ts in by.items():
        if w in CUP: continue
        pre=[t for t in ts if t['type']=='buy' and t.get('slot') and t['slot']<cslot]
        if not pre: continue
        for t in pre: S[t['slot']].add(w)
        sd=[t for t in ts if t['type']=='sell' and cb<=t['time']<=fs+5000]
        a=sum(t['amount'] for t in pre); sa=sum(t['amount'] for t in sd)
        act[w][e['mint']]=dict(buy=sum(t['volumeSol'] for t in pre),sold=sum(t['volumeSol'] for t in sd),
            into=a>0 and sa>=0.5*a,exitb=bool(sd) and max(t['time'] for t in sd)<=fs,lead=(cb-min(t['time'] for t in pre))/1000)
    for sl,W in S.items():
        if len(W)>40: continue      # launch-block mobs
        for a,b in itertools.combinations(sorted(W),2): pair[(a,b)].add(e['mint'])
par={}
def f(x):
    par.setdefault(x,x)
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
links=[(p,m) for p,m in pair.items() if len(m)>=2]
for (a,b),m in links: par[f(a)]=f(b)
C=collections.defaultdict(set)
for (a,b),m in links: C[f(a)].update((a,b))
print('wallets with pre-buys',len(act),'| linked pairs (same slot on >=2 coins)',len(links),'| operators',len(C))
rows=[]
for r,W in C.items():
    st={'old':collections.Counter(),'new':collections.Counter()}; coins={'old':set(),'new':set()}; into={'old':set(),'new':set()}
    for w in W:
        for m,a in act[w].items():
            hf=half[m]; coins[hf].add(m); st[hf]['buy']+=a['buy']; st[hf]['sold']+=a['sold']
            if a['into']: into[hf].add(m)
    rows.append(dict(n=len(W),wallets=sorted(W),
        old=dict(coins=len(coins['old']),into=len(into['old']),pnl=round(st['old']['sold']-st['old']['buy'],1)),
        new=dict(coins=len(coins['new']),into=len(into['new']),pnl=round(st['new']['sold']-st['new']['buy'],1))))
rows.sort(key=lambda r:-(r['old']['into']+r['new']['into']))
json.dump(rows,open('operators.json','w'))
both=[r for r in rows if r['old']['into']>=2 and r['new']['into']>=2]
print('operators selling into Cupsey on >=2 coins in BOTH halves:',len(both))
for r in rows[:30]:
    print(f"  {r['n']:3d}w | old: {r['old']['coins']:3d} coins, into {r['old']['into']:3d}, pnl {r['old']['pnl']:7.1f} | new: {r['new']['coins']:3d} coins, into {r['new']['into']:3d}, pnl {r['new']['pnl']:7.1f} | {','.join(w[:6] for w in r['wallets'][:5])}")
