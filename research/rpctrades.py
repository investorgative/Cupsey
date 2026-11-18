"""Free trade reconstruction from public RPC (no API credits).
For a mint and anchor signatures, fetch nearby transactions and decode every signer's buy/sell of that mint."""
import requests, time, itertools, threading, json, os
from concurrent.futures import ThreadPoolExecutor
WSOL='So11111111111111111111111111111111111111112'
URLS=['https://api.mainnet-beta.solana.com','https://solana-rpc.publicnode.com']
_S=requests.Session(); _rr=itertools.cycle(range(len(URLS))); _l=threading.Lock()
def rpc(method,params,tries=7,history=False):
    for t in range(tries):
        with _l: i=next(_rr)
        url=URLS[1] if (history and t%2==0) else URLS[i]
        try:
            r=_S.post(url,json={"jsonrpc":"2.0","id":1,"method":method,"params":params},timeout=25)
            if r.status_code==429: time.sleep(0.5+0.5*t); continue
            j=r.json()
            if j.get('result') is not None: return j['result']
            if 'result' in j and method!='getTransaction': return j['result']
            if 'error' in j and ('429' in str(j['error']) or 'rate' in str(j['error']).lower()): time.sleep(0.5+0.5*t); continue
            if j.get('result') is None and method=='getTransaction': continue   # node without history: try other
            return j.get('result')
        except Exception: time.sleep(0.5+t)
    return None
def sigs(addr,before=None,until=None,limit=1000):
    p={'limit':limit}
    if before: p['before']=before
    if until: p['until']=until
    for attempt in range(6):
        r=rpc('getSignaturesForAddress',[addr,p])
        if r is not None: return r
        time.sleep(2+3*attempt)
    raise RuntimeError('getSignaturesForAddress kept failing')
def decode(tx,mint):
    """-> list of (wallet, side, tokens, sol) for signers whose balance of `mint` changed."""
    if not tx or not tx.get('meta') or tx['meta'].get('err'): return []
    m=tx['meta']; ak=tx['transaction']['message']['accountKeys']
    keys=[k['pubkey'] if isinstance(k,dict) else k for k in ak]
    signers={k['pubkey'] for k in ak if isinstance(k,dict) and k.get('signer')} or {keys[0]}
    tok={}; wsol={}
    for sign,bals in ((1,m.get('postTokenBalances')),(-1,m.get('preTokenBalances'))):
        for b in bals or []:
            o=b.get('owner')
            if o not in signers: continue
            a=float(b['uiTokenAmount'].get('uiAmountString') or 0)*sign
            if b['mint']==mint: tok[o]=tok.get(o,0)+a
            elif b['mint']==WSOL: wsol[o]=wsol.get(o,0)+a
    out=[]
    for o,d in tok.items():
        if abs(d)<=0: continue
        sol=wsol.get(o,0)
        if o in keys:
            i=keys.index(o); sol+=(m['postBalances'][i]-m['preBalances'][i])/1e9
            if i==0: sol+=m.get('fee',0)/1e9
        side='buy' if d>0 else 'sell'
        out.append((o,side,abs(d),abs(sol)))
    return out
def window(mint,before_sig=None,until_sig=None,max_sigs=400):
    """Signatures of `mint` strictly between until_sig (older) and before_sig (newer), newest first, up to max_sigs."""
    got=[];b=before_sig
    while len(got)<max_sigs:
        r=sigs(mint,before=b,until=until_sig,limit=min(1000,max_sigs-len(got)))
        if not r: break
        got+=r; b=r[-1]['signature']
        if len(r)<min(1000,max_sigs-len(got)+len(r)): break
    return got
def fetch_trades(mint,siglist,threads=6):
    ok=[s for s in siglist if not s.get('err')]
    def one(s):
        t=rpc('getTransaction',[s['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}],history=True)
        return [dict(wallet=w,type=side,amount=a,volumeSol=v,time=(s.get('blockTime') or 0)*1000,slot=s['slot'],tx=s['signature']) for w,side,a,v in decode(t,mint)]
    with ThreadPoolExecutor(threads) as ex:
        res=[x for l in ex.map(one,ok) for x in l]
    return sorted(res,key=lambda t:(t['slot'],t['time']))
