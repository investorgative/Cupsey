"""Score wallets vs. the market-wide 'heating up' effect, then merge wallets into entities.
Entity links: two wallets bought the same coin within 2 s of each other before Cupsey on >=2 different coins
(or in the same slot when slots are known). Wallets of one operator move together; strangers rarely do twice."""
import json,collections,math,sys,itertools
from insider import load,CUP,WIN
src=sys.argv[1] if len(sys.argv)>1 else 'tok2'
E=load(src)
S=collections.defaultdict(collections.Counter); EV=collections.defaultdict(list)
co=collections.Counter(); coins_of=collections.defaultdict(set)
tot_pre=tot_ctrl=0; used=0
for e in E:
    tr=e['trades']; cb=e['cb']; fs=e['fs']
    if not tr: continue
    cov=cb-min(t['time'] for t in tr)
    WIN=min(120_000,cov//3)
    if WIN<30_000: continue
    used+=1
    by=collections.defaultdict(list)
    for t in tr: by[t['wallet']].append(t)
    cs=[t.get('slot') for t in tr if t['wallet'] in CUP and t['type']=='buy' and t.get('slot')]
    cslot=min(cs) if cs else None
    prebuy={}
    for w,ts in by.items():
        if w in CUP: continue
        buys=[t for t in ts if t['type']=='buy']; sells=[t for t in ts if t['type']=='sell']
        pre=[t for t in buys if cb-WIN<=t['time']<=cb and (t['slot']<cslot if cslot and t.get('slot') else t['time']<cb-500)]
        nc=sum(1 for lo,hi in ((cb-2*WIN,cb-WIN),(cb-3*WIN,cb-2*WIN)) if any(lo<=t['time']<hi for t in buys))
        s=S[w]; s['seen']+=1; s['ctrl']+=nc; tot_ctrl+=nc
        if not pre: continue
        s['pre']+=1; tot_pre+=1
        amt=sum(t['amount'] for t in pre); sd=[t for t in sells if cb<=t['time']<=fs+5000]
        if amt>0 and sum(t['amount'] for t in sd)>=0.5*amt:
            s['sold']+=1; pin=sum(t['volumeSol'] for t in pre); pout=sum(t['volumeSol'] for t in sd)
            s['pmilli']+=int((pout-pin)*1000)
            last=max(t['time'] for t in sd)
            if 0<fs-last<=30000 and fs-cb>60000: s['exit']+=1
            EV[w].append(e['mint'])
            prebuy[w]=min(t for t in pre if True and True)['slot'] if False else (min(t['time'] for t in pre), min((t.get('slot') or 0) for t in pre))
            coins_of[w].add(e['mint'])
    ws=sorted(prebuy.items(),key=lambda x:x[1][0])
    for i in range(len(ws)):
        for j in range(i+1,len(ws)):
            (a,(ta,sa)),(b,(tb,sb))=ws[i],ws[j]
            if tb-ta>2000: break
            if sa and sb and sa!=sb: continue
            co[tuple(sorted((a,b)))]+=1
R=tot_pre/(tot_ctrl/2) if tot_ctrl else 1
print(f'{src}: entries {used}, market-wide pre/control ratio R={R:.2f} (how much more everyone buys right before Cupsey)')
# union-find on repeated co-buys
par={}
def f(x):
    par.setdefault(x,x)
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for (a,b),n in co.items():
    if n>=2: par[f(a)]=f(b)
groups=collections.defaultdict(set)
for w in S:
    if S[w]['sold']>=1: groups[f(w)].add(w)
rows=[]
for g,mem in groups.items():
    coins=set().union(*[coins_of[w] for w in mem])
    pre=sum(S[w]['pre'] for w in mem); ctrl=sum(S[w]['ctrl'] for w in mem)/2
    exp=max(0.5,ctrl*R)
    z=(pre-exp)/math.sqrt(exp)
    rows.append(dict(members=sorted(mem),n=len(mem),coins=len(coins),pre=pre,ctrl=round(ctrl,1),exp=round(exp,1),z=round(z,2),
                     sold=sum(S[w]['sold'] for w in mem),exit=sum(S[w]['exit'] for w in mem),profit=round(sum(S[w]['pmilli'] for w in mem)/1000,1)))
rows.sort(key=lambda r:(-(r['coins']>=3), -r['z']*min(r['coins'],8)))
print('top entities (coins = distinct Cupsey coins where a member pre-bought AND sold into his pump):')
for r in rows[:25]:
    print(f"  coins {r['coins']:2d} | pre {r['pre']} vs expected {r['exp']} (z {r['z']}) | exit-before {r['exit']} | +{r['profit']} SOL | {r['n']} wallet(s): {', '.join(w[:6] for w in r['members'][:6])}")
json.dump({'R':R,'rows':rows,'S':S},open(f'entities_{src}.json','w'))
