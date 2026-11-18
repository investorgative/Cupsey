"""Complete pre-buy history for a Cupsey entry: every successful tx of the mint from launch to his buy.
Stores, per tx, every owner's post-balance of the mint (exact holder snapshot at his buy) and signer trades."""
import json,os,sys,time
from concurrent.futures import ThreadPoolExecutor
from rpctrades import sigs, rpc, decode
OUT='tok4'; os.makedirs(OUT,exist_ok=True)
CAP=20000
def order():
    E=json.load(open('entries_6DQAG.json'))
    for e in E: e['pnl']=sum(s for _,s in e['sells'])-sum(b for _,b in e['buys'])
    W=sorted([e for e in E if e['pnl']>0],key=lambda e:-e['pnl']); L=sorted([e for e in E if e['pnl']<=0],key=lambda e:e['pnl'])
    out=[]
    for i in range(max(len(W),len(L))):
        if i<len(W): out.append(W[i])
        if i<len(L): out.append(L[i])
    return out
def one(s,mint):
    t=rpc('getTransaction',[s['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}],history=True)
    if not t: return None
    m=t['meta']; keys=[k['pubkey'] for k in t['transaction']['message']['accountKeys']]
    bal={}
    for b in m.get('postTokenBalances') or []:
        if b['mint']==mint: bal[b.get('owner')]=float(b['uiTokenAmount']['uiAmountString'] or 0)
    for b in m.get('preTokenBalances') or []:
        if b['mint']==mint and b.get('owner') not in bal: bal[b.get('owner')]=0.0   # account closed in this tx
    return dict(sig=s['signature'],slot=s['slot'],time=(s.get('blockTime') or 0)*1000,signer=keys[0],bal=bal,
                trades=[(w,side,a,v) for w,side,a,v in decode(t,mint)])
def run(e):
    fn=f"{OUT}/{e['mint']}.json"; lock=fn+'.lock'
    if os.path.exists(fn) or os.path.exists(lock): return
    open(lock,'w').close(); t0=time.time()
    try:
        allr=[];b=e['buy_tx'];full=False
        while len(allr)<CAP:
            r=sigs(e['mint'],before=b); allr+=r
            if len(r)<1000: full=True; break
            b=r[-1]['signature']
        ok=[s for s in allr if not s.get('err')]
        with ThreadPoolExecutor(8) as ex: R=list(ex.map(lambda s:one(s,e['mint']),ok))
        for rnd in range(4):   # retry what the rate limiter dropped, slower each round
            todo=[i for i,r in enumerate(R) if r is None]
            if not todo: break
            time.sleep(5*(rnd+1))
            with ThreadPoolExecutor(max(1,4-rnd)) as ex: rr=list(ex.map(lambda i:one(ok[i],e['mint']),todo))
            for i,r in zip(todo,rr): R[i]=r
        miss=sum(r is None for r in R); R=[r for r in R if r]
        R.sort(key=lambda r:(r['slot'],r['time']))
        launch=R[0] if (full and R) else None
        json.dump(dict(entry=e,full=full,n_sigs=len(allr),n_ok=len(ok),missed=miss,
                       creator=launch['signer'] if launch else None,launch_slot=launch['slot'] if launch else None,
                       launch_time=launch['time'] if launch else None,txs=R),open(fn,'w'))
        print(e['mint'][:6],'pnl',round(e['pnl'],1),'sigs',len(allr),'ok',len(ok),'missed',miss,'full',full,f'{time.time()-t0:.0f}s',flush=True)
    finally:
        os.remove(lock)
if __name__=='__main__':
    L=order()
    if len(sys.argv)>1 and sys.argv[1]=='rev': L=L[::-1]
    for e in L:
        try: run(e)
        except Exception as ex: print('ERR',e['mint'][:6],ex,flush=True)
