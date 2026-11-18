"""Free precision check via RPC: of the coins a wallet bought, how many did Cupsey (6DQAG) buy within 60 min after it?"""
import json,sys,time
from concurrent.futures import ThreadPoolExecutor
from rpctrades import sigs, rpc
SOL='So11111111111111111111111111111111111111112'
ct=json.load(open('trades_6DQAG.json')); CB={}
for t in ct:
    if t['from']['address']==SOL: m=t['to']['address']; CB[m]=min(CB.get(m,1e20),t['time'])
for e in json.load(open('entries_6DQAG.json')): CB[e['mint']]=min(CB.get(e['mint'],1e20),e['cb'])
T0=min(CB.values()); T1=max(CB.values())
def hist(w,maxs=2000):
    allr=[];b=None
    while len(allr)<maxs:
        r=sigs(w,before=b); allr+=r
        if len(r)<1000: break
        b=r[-1]['signature']
    def one(x):
        if x.get('err'): return []
        t=rpc('getTransaction',[x['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}],history=True)
        if not t: return None
        m=t['meta']; d={}
        for sg,bals in ((1,m.get('postTokenBalances')),(-1,m.get('preTokenBalances'))):
            for bb in bals or []:
                if bb.get('owner')==w and bb['mint']!=SOL: d[bb['mint']]=d.get(bb['mint'],0)+sg*float(bb['uiTokenAmount']['uiAmountString'] or 0)
        return [(x['blockTime']*1000,mt,v>0) for mt,v in d.items() if abs(v)>0]
    with ThreadPoolExecutor(4) as ex: R=list(ex.map(one,allr))
    miss=sum(r is None for r in R)
    return [y for r in R if r for y in r],len(allr),miss
for w in sys.argv[1:]:
    H,n,miss=hist(w); fb={}
    for tm,m,buy in H:
        if buy: fb[m]=min(fb.get(m,1e20),tm)
    inper={m:tm for m,tm in fb.items() if T0-3600_000<=tm<=T1}
    fol=[m for m,tm in inper.items() if m in CB and 0<CB[m]-tm<=3600_000]
    aft=[m for m,tm in inper.items() if m in CB and CB[m]<=tm]
    span=(time.strftime('%m-%d %H:%M',time.gmtime(min(fb.values())/1000)),time.strftime('%m-%d %H:%M',time.gmtime(max(fb.values())/1000))) if fb else None
    print(f'{w[:8]} sigs {n} (missed {miss}) coins bought {len(fb)} span {span} | in Cupsey period {len(inper)} | Cupsey bought AFTER it: {len(fol)} ({len(fol)/max(1,len(inper)):.0%}) | it bought after Cupsey: {len(aft)}',flush=True)
