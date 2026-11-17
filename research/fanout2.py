"""Strict fan-out: only explicit system transfers (SOL) and SPL USDC transfers signed by `src`."""
import json,sys,datetime
from rpc import sigs, tx, rpc
from concurrent.futures import ThreadPoolExecutor
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
def fanout(src,pages=3,max_tx=3000):
    allr=[];b=None
    for _ in range(pages):
        r=sigs(src,b); allr+=r
        if len(r)<1000: break
        b=r[-1]['signature']
    ok=[s for s in allr if not s['err']][:max_tx]
    def one(s):
        t=tx(s['signature']); out=[]
        if not t: return out
        keys=[k['pubkey'] for k in t['transaction']['message']['accountKeys']]
        if keys[0]!=src: return out
        ins=t['transaction']['message']['instructions']
        if any(i.get('programId') not in ('11111111111111111111111111111111','TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','ComputeBudget111111111111111111111111111111','ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTKsLJA8knL','MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr','TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb') for i in ins):
            return out  # contains a DEX/program call -> not a plain transfer
        pre={b['accountIndex']:b for b in t['meta'].get('preTokenBalances') or []}
        for i in ins:
            p=i.get('parsed') if isinstance(i,dict) else None
            if not isinstance(p,dict): continue
            inf=p.get('info',{})
            if i.get('program')=='system' and p.get('type')=='transfer' and inf.get('source')==src and inf.get('lamports',0)>=10_000_000:
                out.append((s['blockTime'],'SOL',inf['destination'],inf['lamports']/1e9))
        for bb in t['meta'].get('postTokenBalances') or []:
            if bb['mint']!=USDC or bb.get('owner')==src: continue
            p=pre.get(bb['accountIndex']); d=float(bb['uiTokenAmount']['uiAmountString'] or 0)-(float(p['uiTokenAmount']['uiAmountString'] or 0) if p else 0)
            if d>=20: out.append((s['blockTime'],'USDC',bb.get('owner'),d))
        return out
    with ThreadPoolExecutor(3) as ex: res=[x for l in ex.map(one,ok) for x in l]
    return allr,res
if __name__=='__main__':
    src=sys.argv[1]; allr,res=fanout(src)
    json.dump(res,open(f'fan2_{src[:6]}.json','w'))
    f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
    print(src,'sigs',len(allr),f(allr[-1]['blockTime']),'->',f(allr[0]['blockTime']),'bal',rpc('getBalance',[src])['value']/1e9,'plain transfers',len(res))
