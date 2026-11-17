"""List wallets a source sent SOL or USDC to (excluding pools/exchanges noise via min amounts)."""
import json,sys,datetime
from rpc import sigs, tx, rpc
from concurrent.futures import ThreadPoolExecutor
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
def fanout(src,pages=3,max_tx=1500):
    b=None;allr=[]
    for _ in range(pages):
        r=sigs(src,b); allr+=r
        if len(r)<1000: break
        b=r[-1]['signature']
    ok=[s for s in allr if not s['err']][:max_tx]
    def one(s):
        t=tx(s['signature']); out=[]
        if not t: return out
        m=t['meta']; keys=[k['pubkey'] for k in t['transaction']['message']['accountKeys']]
        if keys[0]!=src: return out   # only txs the source itself signed
        pre={b['accountIndex']:b for b in m.get('preTokenBalances') or []}
        for bb in m.get('postTokenBalances') or []:
            if bb['mint']!=USDC: continue
            p=pre.get(bb['accountIndex']); d=float(bb['uiTokenAmount']['uiAmountString'] or 0)-(float(p['uiTokenAmount']['uiAmountString'] or 0) if p else 0)
            if d>=50 and bb.get('owner')!=src: out.append((t['blockTime'],'USDC',bb['owner'],round(d,1)))
        for i,k in enumerate(keys):
            d=(m['postBalances'][i]-m['preBalances'][i])/1e9
            if k!=src and d>=0.02 and not (m.get('postTokenBalances') and len(m['postTokenBalances'])>2): out.append((t['blockTime'],'SOL',k,round(d,3)))
        return out
    with ThreadPoolExecutor(3) as ex: res=[x for l in ex.map(one,ok) for x in l]
    return allr,res
if __name__=='__main__':
    src=sys.argv[1]
    allr,res=fanout(src)
    print(src,'sigs',len(allr),'span',f(allr[-1]['blockTime']),'->',f(allr[0]['blockTime']),'bal',rpc('getBalance',[src])['value']/1e9)
    json.dump(res,open(f'fanout_{src[:6]}.json','w'))
    for r in sorted(res): print(' ',f(r[0]),r[1],r[2],r[3])
