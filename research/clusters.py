"""Coordinated pre-buy groups: >=3 non-Cupsey wallets buying the same coin in the same slot
before Cupsey's first slot. Do they sell into his pump and exit before him?"""
import json,collections,time
from holdout import entries, CUP
E=entries(); out=[]
for e in E:
    tr=e['trades']; cb=e['cb']; fs=e['fs']
    cs=[t['slot'] for t in tr if t['wallet'] in CUP and t['type']=='buy' and t.get('slot')]
    if not cs: continue
    cslot=min(cs); first_slot=min(t['slot'] for t in tr if t.get('slot'))
    S=collections.defaultdict(set)
    for t in tr:
        if t['type']=='buy' and t.get('slot') and t['slot']<cslot and t['wallet'] not in CUP: S[t['slot']].add(t['wallet'])
    for sl,W in S.items():
        if len(W)<3: continue
        b=[t for t in tr if t['wallet'] in W and t['type']=='buy' and t['time']<=cb]
        s=[t for t in tr if t['wallet'] in W and t['type']=='sell' and cb<=t['time']<=fs+5000]
        bs=sum(t['volumeSol'] for t in b); ss=sum(t['volumeSol'] for t in s)
        btok=sum(t['amount'] for t in b); stok=sum(t['amount'] for t in s)
        last=max((t['time'] for t in s),default=None)
        out.append(dict(mint=e['mint'],cb=cb,slot=sl,dslot=cslot-sl,launch=(sl==first_slot and e.get('pre_full',False)),
            n=len(W),wallets=sorted(W),buy=round(bs,2),sold=round(ss,2),soldfrac=round(stok/btok,2) if btok else 0,
            exit_before=bool(last and last<=fs),lead=(cb-min(t['time'] for t in b))/1000 if b else None))
json.dump(out,open('clusters.json','w'))
n=len(E); withc=len({c['mint'] for c in out})
print('entries',n,'with >=3-wallet same-slot pre-buy group:',withc,'groups',len(out))
big=[c for c in out if c['buy']>=5]
print('groups buying >=5 SOL:',len(big),'on',len({c['mint'] for c in big}),'coins')
dump=[c for c in big if c['soldfrac']>=0.5 and c['sold']>c['buy']]
print('...of which sold >=50% into Cupsey at a profit:',len(dump),'on',len({c['mint'] for c in dump}),'coins; exit before his first sell:',sum(c['exit_before'] for c in dump))
# wallet reuse across groups
cnt=collections.Counter(w for c in out for w in c['wallets'])
rep=[w for w,k in cnt.items() if k>=2]
print('wallets in >=2 groups:',len(rep))
for c in sorted(dump,key=lambda c:-(c['sold']-c['buy'])):
    print(f"  {c['mint'][:6]} {time.strftime('%m-%d %H:%M',time.gmtime(c['cb']/1000))} n={c['n']:2d} slots-before={c['dslot']:4d} lead {c['lead']:6.1f}s in {c['buy']:5.1f} out {c['sold']:5.1f} sold {c['soldfrac']:.0%} exit-before={c['exit_before']} reused={sum(cnt[w]>=2 for w in c['wallets'])}")
