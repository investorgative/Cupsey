"""Rotation test on ALL entries (no control-window requirement):
profitable early sellers (bought before Cupsey's slot, sold >=50% into his hold, +>=0.5 SOL)
vs a random control of pre-buyers who did not sell into him. Are there private funders that
supply profitable early sellers in BOTH halves, more than they supply the control group?"""
import json,collections,random,sys
from holdout import entries, CUP
from rotation import funder, is_hub, save, fc, hubc
def hitters(part):
    H=collections.defaultdict(list); P=set()
    for e in part:
        tr=e['trades']; cb=e['cb']; fs=e['fs']
        cs=[t.get('slot') for t in tr if t['wallet'] in CUP and t['type']=='buy' and t.get('slot')]; cslot=min(cs) if cs else None
        by=collections.defaultdict(list)
        for t in tr: by[t['wallet']].append(t)
        for w,ts in by.items():
            if w in CUP: continue
            pre=[t for t in ts if t['type']=='buy' and (t['slot']<cslot if cslot and t.get('slot') else t['time']<cb-500)]
            if not pre: continue
            P.add(w)
            sd=[t for t in ts if t['type']=='sell' and cb<=t['time']<=fs+5000]
            amt=sum(t['amount'] for t in pre)
            if amt>0 and sum(t['amount'] for t in sd)>=0.5*amt:
                H[w].append((e['mint'],sum(t['volumeSol'] for t in sd)-sum(t['volumeSol'] for t in pre),cb-min(t['time'] for t in pre)))
    return H,P
if __name__=='__main__':
    E=entries(); h=len(E)//2; G={}
    for name,part in (('old',E[:h]),('new',E[h:])):
        H,P=hitters(part)
        hit=[w for w,l in H.items() if sum(p for _,p,_ in l)>=0.5]
        rest=sorted(P-set(H)); random.seed(7); ctrl=random.sample(rest,len(hit))
        G[name]=(hit,ctrl,H)
    todo=sorted({w for n in G for w in G[n][0]+G[n][1] if w not in fc})
    print('to trace',len(todo),'cached',len(fc),flush=True)
    for i,w in enumerate(todo):
        try: funder(w)
        except Exception as ex: fc[w]={'n':None,'funder':None,'err':str(ex)}
        if i%25==0: save(); print(' traced',i,flush=True)
    save()
    def fmap(ws):
        M=collections.defaultdict(set)
        for w in ws:
            f=(fc.get(w) or {}).get('funder')
            if f: M[f].add(w)
        return M
    out={}
    for label,idx in (('HIT',0),('CTRL',1)):
        Mo,Mn=fmap(G['old'][idx]),fmap(G['new'][idx])
        fresh=sum(1 for n in G for w in G[n][idx] if (fc.get(w) or {}).get('n') and fc[w]['n']<2000)
        traced=sum(1 for n in G for w in G[n][idx] if (fc.get(w) or {}).get('funder'))
        multi=[f for f in set(Mo)|set(Mn) if len(Mo[f])+len(Mn[f])>=2]
        both=[f for f in set(Mo)&set(Mn)]
        privb=[f for f in both if not is_hub(f)]; privm=[f for f in multi if not is_hub(f)]
        print(f'{label}: n={len(G["old"][idx])}+{len(G["new"][idx])} fresh(<2000 sigs)={fresh} traced={traced} | funders w/ 2+ wallets={len(multi)} private={len(privm)} | in BOTH halves={len(both)} private={len(privb)}')
        for f in sorted(privm,key=lambda f:-(len(Mo[f])+len(Mn[f])))[:15]:
            print(f'    {f}  old {len(Mo[f])} new {len(Mn[f])}  {[w[:6] for w in Mo[f]]} / {[w[:6] for w in Mn[f]]}')
        out[label]={f:[sorted(Mo[f]),sorted(Mn[f])] for f in privm}
    json.dump(dict(groups={n:dict(hit=G[n][0],ctrl=G[n][1],hits={w:G[n][2][w] for w in G[n][0]}) for n in G},funders=out,hubs=hubc),open('rotation2.json','w'))
