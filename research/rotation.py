"""Rotation test: do the SAME private funders keep supplying wallets that front-run Cupsey,
in both the older and the newer half of his entries, more than they supply ordinary pre-buyers?"""
import json,os,collections,random,sys,math
from holdout import entries, stats, CUP
from rpctrades import sigs, rpc
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
CACHE='funder2_cache.json'
fc=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def save(): json.dump(fc,open(CACHE,'w'))
def funder(w):
    """First external SOL/USDC source (or first foreign signer) of a fresh-ish wallet; None if too old/busy."""
    if w in fc: return fc[w]
    allr=[];b=None
    for _ in range(2):
        r=sigs(w,before=b)
        allr+=r
        if len(r)<1000: break
        b=r[-1]['signature']
    res={'n':len(allr),'funder':None,'kind':None,'amt':None,'ts':None}
    if allr and len(allr)<2000:
        for s in [s for s in reversed(allr) if not s.get('err')][:5]:
            t=rpc('getTransaction',[s['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}],history=True)
            if not t: continue
            m=t['meta']; keys=[k['pubkey'] for k in t['transaction']['message']['accountKeys']]
            if w in keys:
                i=keys.index(w); d=(m['postBalances'][i]-m['preBalances'][i])/1e9
                if d>=0.01:
                    src=[keys[j] for j in range(len(keys)) if j!=i and (m['postBalances'][j]-m['preBalances'][j])/1e9<=-0.9*d]
                    if src: res.update(funder=src[0],kind='sol',amt=d,ts=s.get('blockTime')); break
            pre={x['accountIndex']:x for x in m.get('preTokenBalances') or []}; ud={}
            for x in m.get('postTokenBalances') or []:
                if x['mint']!=USDC: continue
                p=pre.get(x['accountIndex']); ud[x.get('owner')]=ud.get(x.get('owner'),0)+float(x['uiTokenAmount']['uiAmountString'] or 0)-(float(p['uiTokenAmount']['uiAmountString'] or 0) if p else 0)
            if ud.get(w,0)>=20:
                src=[o for o,v in ud.items() if o!=w and v<0]
                if src: res.update(funder=src[0],kind='usdc',amt=ud[w],ts=s.get('blockTime')); break
            if keys[0]!=w and not res['funder'] and len(m.get('postTokenBalances') or [])<=2:
                res.update(funder=keys[0],kind='signer',ts=s.get('blockTime')); break
    fc[w]=res; return res
hubc={}
def is_hub(a):
    if a in hubc: return hubc[a]
    s=sigs(a); h=len(s)==1000 and (s[0]['blockTime']-s[-1]['blockTime'])<6*3600
    hubc[a]=h; return h
if __name__=='__main__':
    E=entries(); h=len(E)//2
    halves={'old':E[:h],'new':E[h:]}
    groups={}
    for name,part in halves.items():
        used,S,co,R=stats(part)
        hit=[w for w,s in S.items() if s['sold']>=1]
        pre_only=[w for w,s in S.items() if s['pre']>=1 and s['sold']==0]
        random.seed(1); ctrl=random.sample(pre_only,min(len(pre_only),len(hit)))
        groups[name]=(hit,ctrl)
        print(name,'usable',used,'hitters',len(hit),'control pre-buyers',len(ctrl),flush=True)
    todo=sorted({w for hit,ctrl in groups.values() for w in hit+ctrl if w not in fc})
    print('wallets to trace',len(todo),flush=True)
    for i,w in enumerate(todo):
        try: funder(w)
        except Exception as ex: fc[w]={'n':None,'funder':None,'err':str(ex)}
        if i%50==0: save(); print(' traced',i,flush=True)
    save()
    def fund_map(ws):
        M=collections.defaultdict(set)
        for w in ws:
            r=fc.get(w) or {}
            if r.get('funder'): M[r['funder']].add(w)
        return M
    for label,idx in (('HITTERS (sold into Cupsey)',0),('CONTROL (pre-bought, did not sell into him)',1)):
        Mo=fund_map(groups['old'][idx]); Mn=fund_map(groups['new'][idx])
        both=[f for f in set(Mo)&set(Mn)]
        priv=[f for f in both if not is_hub(f)]
        traced=sum(1 for w in groups['old'][idx]+groups['new'][idx] if (fc.get(w) or {}).get('funder'))
        print(f'{label}: traced funders for {traced} wallets | funders active in BOTH halves: {len(both)} | private (non-exchange): {len(priv)}')
        for f in sorted(priv,key=lambda f:-(len(Mo[f])+len(Mn[f])))[:12]:
            print(f'    {f} funds {len(Mo[f])} old + {len(Mn[f])} new wallets: {[w[:6] for w in list(Mo[f])[:3]]} / {[w[:6] for w in list(Mn[f])[:3]]}')
    json.dump({'hub':hubc},open('rotation_hubs.json','w'))
