import datetime,collections,sys,json
from rpc import sigs, tx
from concurrent.futures import ThreadPoolExecutor
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
def flows(A,pages=1,max_tx=600):
    allr=[];b=None
    for _ in range(pages):
        r=sigs(A,b); allr+=r
        if len(r)<1000: break
        b=r[-1]['signature']
    ok=[s for s in allr if not s['err']][:max_tx]
    def one(s):
        t=tx(s['signature']); out=[]
        if not t: return out
        m=t['meta']; keys=[k['pubkey'] for k in t['transaction']['message']['accountKeys']]
        swap=len(m.get('postTokenBalances') or [])>2
        if swap: return out
        if A in keys:
            i=keys.index(A); d=(m['postBalances'][i]-m['preBalances'][i])/1e9
            if abs(d)>=0.3:
                for j,k in enumerate(keys):
                    dj=(m['postBalances'][j]-m['preBalances'][j])/1e9
                    if j!=i and dj*d<0 and abs(dj)>=0.5*abs(d): out.append(('SOL','in' if d>0 else 'out',k,abs(d),s['blockTime']))
        pre={b['accountIndex']:b for b in m.get('preTokenBalances') or []}; ud={}
        for bb in m.get('postTokenBalances') or []:
            if bb['mint']!=USDC: continue
            p=pre.get(bb['accountIndex']); ud[bb.get('owner')]=ud.get(bb.get('owner'),0)+float(bb['uiTokenAmount']['uiAmountString'] or 0)-(float(p['uiTokenAmount']['uiAmountString'] or 0) if p else 0)
        if abs(ud.get(A,0))>=50:
            for o,v in ud.items():
                if o!=A and v*ud[A]<0: out.append(('USDC','in' if ud[A]>0 else 'out',o,abs(ud[A]),s['blockTime']))
        return out
    with ThreadPoolExecutor(3) as ex: return allr,[x for l in ex.map(one,ok) for x in l]
