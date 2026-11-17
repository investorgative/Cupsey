import json,os,sys
from rpc import rpc
CUP={'2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK'}
sc=json.load(open('scored.json'))
cands=[r[1] for r in sc['res'][:24]]
out=json.load(open('bundle.json')) if os.path.exists('bundle.json') else {}
sigcache={}
files=sorted(os.listdir('tok'))
for w in cands:
    if w in out: continue
    adj=same=n=0
    for f in files:
        if n>=6: break
        tr=json.load(open('tok/'+f)); mint=f[:-5]
        cb=[t for t in tr if t['wallet'] in CUP and t['type']=='buy']
        if not cb: continue
        t0=min(t['time'] for t in cb)
        wb=[t for t in tr if t['wallet']==w and t['type']=='buy' and abs(t['time']-t0)<=3000]
        if not wb: continue
        later=[t for t in tr if t['time']>t0+20000]
        if not later: continue
        if mint not in sigcache: sigcache[mint]=rpc('getSignaturesForAddress',[mint,{'before':later[0]['tx'],'limit':1000}]) or []
        idx={s['signature']:(s['slot'],s.get('transactionIndex') or 0) for s in sigcache[mint]}
        cp=[idx[t['tx']] for t in cb if t['tx'] in idx]; wp=[idx[t['tx']] for t in wb if t['tx'] in idx]
        if not cp or not wp: continue
        n+=1
        if any(a[0]==b[0] for a in wp for b in cp): same+=1
        if any(a[0]==b[0] and abs(a[1]-b[1])<=4 for a in wp for b in cp): adj+=1
    out[w]={'n':n,'same_slot':same,'adjacent':adj}
    print(w[:10],out[w],flush=True)
    json.dump(out,open('bundle.json','w'))
