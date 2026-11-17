import json,collections,datetime
from fanout2 import fanout
from rpc import rpc, sigs
f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
r=json.load(open('fanout_EzcD6K.json'))
pay=collections.defaultdict(list)
for ts,k,d,a in r: pay[d].append((ts,k,a))
targets=[d for d in pay if any(d.startswith(p) for p in ['6HA88ZFF','Fe11Bnc3','7DN5VKvr','AXMPqV8s','7NVu2wtt','HMaR7kMw'])]
out={}
dest_count=collections.defaultdict(set)
for w in targets:
    allr,res=fanout(w,pages=2,max_tx=1200)
    got=sum(a for _,k,a in pay[w] if k=='SOL'); gotu=sum(a for _,k,a in pay[w] if k=='USDC')
    agg=collections.defaultdict(lambda:[0,0.0,''])
    for ts,k,d,a in res: g=agg[d]; g[0]+=1; g[1]+=a; g[2]=k; dest_count[d].add(w)
    out[w]={'sigs':len(allr),'span':(f(allr[-1]['blockTime']),f(allr[0]['blockTime'])) if allr else None,'bal':rpc('getBalance',[w])['value']/1e9,
            'received_sol':round(got,1),'received_usdc':round(gotu,1),'plain_transfers':len(res),'top':sorted([(d,n,round(a,1),k) for d,(n,a,k) in agg.items()],key=lambda x:-x[2])[:8]}
    print('==',w,json.dumps({k:v for k,v in out[w].items() if k!='top'}),flush=True)
    for t in out[w]['top']: print('   ->',t,flush=True)
shared={d:sorted(ws) for d,ws in dest_count.items() if len(ws)>=2}
print('destinations shared by 2+ payroll wallets:',{d[:10]:[w[:6] for w in ws] for d,ws in shared.items()})
json.dump({'out':out,'shared':shared},open('payroll.json','w'))
