import sys,json,datetime,collections,statistics
sys.path.insert(0,'../shadowwatch')
from solana import parse_swap
from rpc import sigs, tx
from fanout2 import fanout
from concurrent.futures import ThreadPoolExecutor
f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
G='GDQnERSchwsFseR2Gj723HThQFtyZZLX8LZ43Ugvbg1b'; Y='6yYzwmfQS9rTi74cwfzazjDoMDHx3YcLizxCFWsqcWfM'; BIG='4qBro3VYM7ZcDeLTcGueazKYQYED6ZmM3HEy7NxTuNFU'
def swaps(w,n=600):
    s=[x for x in sigs(w) if not x['err']][:n]
    def one(x):
        t=tx(x['signature']); sw=parse_swap(t,w) if t else None
        return (x['blockTime'],sw) if sw else None
    with ThreadPoolExecutor(3) as ex: r=[v for v in ex.map(one,s) if v]
    return s,r
for name,w in [('GDQn',G),('6yYz',Y)]:
    s,sw=swaps(w)
    toks=collections.Counter(x[1]['mint'] for x in sw)
    buys=[x for x in sw if x[1]['side']=='BUY']
    print(f'== {name}: {len(s)} recent ok tx, {len(sw)} swaps ({len(buys)} buys), {len(toks)} coins, span {f(s[-1]["blockTime"])} -> {f(s[0]["blockTime"])}')
    if buys: print('   buy size median',round(statistics.median(x[1]['sol'] for x in buys),3),'SOL; top coins',[(m[:6],c) for m,c in toks.most_common(5)])
    json.dump([[t,x] for t,x in sw],open(f'loop_{name}.json','w'))
allr,res=fanout(Y,pages=2,max_tx=1500)
tg=sorted(ts for ts,k,d,a in res if d==G)
amts=[a for ts,k,d,a in res if d==G]
print('6yYz -> GDQn transfers found',len(tg), 'amount median',round(statistics.median(amts),3) if amts else '-', 'first',f(tg[0]) if tg else '-','last',f(tg[-1]) if tg else '-')
gs=json.load(open('loop_GDQn.json'))
gb=sorted(t for t,x in gs if x['side']=='BUY')
if tg and gb:
    lag=[]
    for t in tg:
        nxt=[b for b in gb if b>=t]
        if nxt: lag.append(nxt[0]-t)
    print('time from a 6yYz top-up to GDQn next buy (s): median',statistics.median(lag) if lag else '-','| within 2 min:',sum(l<=120 for l in lag),'of',len(lag))
y=json.load(open('loop_6yYz.json'))
common=set(x['mint'] for _,x in gs)&set(x['mint'] for _,x in y)
print('coins traded by BOTH wallets:',len(common))
seed=json.load(open('../shadowwatch/data/tracker_seed.json'))
hits=collections.Counter(o['wallet'] for o in seed['obs'] if o['hit']); pre=collections.Counter(o['wallet'] for o in seed['obs'])
print('Cupsey early-buy record: GDQn',hits[G],'/',pre[G],'| 6yYz',hits[Y],'/',pre[Y])
