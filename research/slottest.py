import json,os,collections,sys
from rpc import tx
from concurrent.futures import ThreadPoolExecutor
CUPSEY={'2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK'}
cands=sys.argv[1].split(',')
toks=json.load(open('cupsey_tokens.json'))
cache=json.load(open('slotcache.json')) if os.path.exists('slotcache.json') else {}
def slot(sig):
    if sig in cache: return cache[sig]
    t=tx(sig); v=(t['slot'], t['transaction']['message']['accountKeys'][0]['pubkey']) if t else None
    cache[sig]=v; return v
jobs=collections.defaultdict(list)
for f in os.listdir('tok'):
    tr=json.load(open('tok/'+f));
    cb=[t for t in tr if t['wallet'] in CUPSEY and t['type']=='buy']
    if not cb: continue
    c0=min(cb,key=lambda t:t['time'])
    for w in cands:
        wb=[t for t in tr if t['wallet']==w and t['type']=='buy' and abs(t['time']-c0['time'])<=5000]
        if wb: jobs[w].append((f[:6],c0['tx'],min(wb,key=lambda t:t['time'])['tx']))
pairs=[(w,j) for w in cands for j in jobs[w][:6]]
sigs={s for _,j in pairs for s in j[1:]}
with ThreadPoolExecutor(3) as ex: list(ex.map(slot,sigs))
json.dump(cache,open('slotcache.json','w'))
for w in cands:
    out=[]
    for tok,cs,ws in jobs[w][:6]:
        a=cache.get(cs); b=cache.get(ws)
        if a and b: out.append(b[0]-a[0])
    print(w[:8],'n',len(jobs[w]),'slot diff (W - Cupsey):',out, 'signer', cache.get(jobs[w][0][2]) if jobs[w] else None)
