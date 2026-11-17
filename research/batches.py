import json,datetime,collections,sys
from fanout2 import fanout
f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
pay=json.load(open('fanout_EzcD6K.json'))
rec=collections.defaultdict(list)
for ts,k,d,a in pay: rec[d].append((ts,k,a))
# one-off/large non-payroll recipients since Aug
skip={'6HA88ZFF','Fe11Bnc3','7DN5VKvr','AXMPqV8s','7NVu2wtt','HMaR7kMw','3szYsTw7'}
cands=[d for d,v in rec.items() if not any(d.startswith(s) for s in skip) and max(t for t,_,_ in v)>1787000000 and sum(a if k=='USDC' else a*150 for _,k,a in v)>=3000]
cands=sorted(cands,key=lambda d:-sum(a if k=='USDC' else a*150 for _,k,a in rec[d]))[:15]
print('candidates',len(cands),flush=True)
out={}
for d in cands:
    try: allr,res=fanout(d,pages=1,max_tx=400)
    except Exception as e: print(d,'err',e); continue
    ev=sorted(res); batches=[]; i=0
    while i<len(ev):
        j=i
        while j+1<len(ev) and ev[j+1][0]-ev[i][0]<=1800: j+=1
        grp=ev[i:j+1]; dests={g[2] for g in grp}
        if len(dests)>=4: batches.append((f(grp[0][0]),len(dests),[(g[2][:6],g[1],round(g[3],1)) for g in grp][:16]))
        i=j+1
    got=[(f(t),k,round(a,1)) for t,k,a in rec[d]]
    out[d]={'sigs':len(allr),'got':got,'transfers':len(res),'batches':batches}
    print('==',d,'sigs',len(allr),'got from treasury',got[:4],'| plain transfers',len(res),'| batches',len(batches),flush=True)
    for b in batches[:5]: print('    BATCH',b,flush=True)
json.dump(out,open('batches.json','w'))
