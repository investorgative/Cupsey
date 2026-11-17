import json,datetime,collections
from fanout2 import fanout
from rpc import sigs, rpc
f=lambda t: datetime.datetime.utcfromtimestamp(t).strftime('%m-%d')
def kind(a):
    s=sigs(a); span=(s[0]['blockTime']-s[-1]['blockTime'])/3600 if s else 0
    k='EXCHANGE/service' if len(s)==1000 and span<6 else ('busy' if len(s)==1000 else 'private')
    return k,len(s),round(rpc('getBalance',[a])['value']/1e9,1)
roots={'End wallet 8EKr':'8EKrpV9k5Tmyq2RxpfzPsYN9w9UnKzDBbmif2pTZBjeA','Big wallet 4qBr':'4qBro3VYM7ZcDeLTcGueazKYQYED6ZmM3HEy7NxTuNFU'}
seen=set(); edges=[]; nodes={}
def walk(a,depth,path):
    if a in seen or depth>3: return
    seen.add(a)
    k,n,bal=kind(a); nodes[a]={'kind':k,'sigs':n,'bal':bal}
    print('  '*depth+f'[{depth}] {a} {k} sigs={n} bal={bal}',flush=True)
    if k=='EXCHANGE/service' or depth==3: return
    allr,res=fanout(a,pages=1,max_tx=700)
    agg=collections.defaultdict(lambda:[0,0.0,'',None])
    for ts,kd,d,amt in res:
        g=agg[(d,kd)]; g[0]+=1; g[1]+=amt; g[3]=max(g[3] or 0,ts)
    top=sorted(agg.items(),key=lambda x:-(x[1][1]*(1 if x[0][1]=='USDC' else 150)))[:3]
    for (d,kd),(cnt,amt,_,last) in top:
        edges.append((a,d,kd,round(amt,1),cnt,f(last)))
        print('  '*depth+f'   -> {d[:10]} {cnt}x {round(amt,1)} {kd} last {f(last)}',flush=True)
        walk(d,depth+1,path+[a])
for name,a in roots.items():
    print('ROOT',name,flush=True); walk(a,1,[])
json.dump({'nodes':nodes,'edges':edges},open('downstream.json','w'))
