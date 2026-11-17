import json,random,os,time
from st import *
from pos import *
A=positions(json.load(open('trades_2fg5QD.json'))); Bp=positions(json.load(open('trades_suqh5s.json')))
toks={}
for P in (A,Bp):
    for k,v in P.items():
        if not v['buys']: continue
        e=toks.setdefault(k,{'first_buy':1e18,'last_sell':0,'size':0})
        e['first_buy']=min(e['first_buy'],min(b[0] for b in v['buys']))
        e['last_sell']=max([e['last_sell']]+[s[0] for s in v['sells']])
        e['size']+=sum(b[1] for b in v['buys'])
keys=sorted(toks,key=lambda k:-toks[k]['size'])
random.seed(1)
sample=keys[:170]+random.sample(keys[170:],110)
os.makedirs('tok',exist_ok=True)
json.dump(toks,open('cupsey_tokens.json','w'))
for i,k in enumerate(sample):
    fn=f'tok/{k}.json'
    if os.path.exists(fn): continue
    e=toks[k]; end=min(max(e['last_sell'],e['first_buy']),e['first_buy']+600_000)+60_000
    out=[];cur=int(e['first_buy']-180_000)
    for p in range(4):
        prm={'sortDirection':'ASC'}
        if cur: prm['cursor']=cur
        try: j=get(f'/trades/{k}',prm)
        except Exception as ex: print('err',k,ex); break
        out+=j['trades']
        if not j.get('hasNextPage') or not j['trades'] or j['trades'][-1]['time']>end: break
        cur=j['nextCursor']
    json.dump(out,open(fn,'w'))
    if i%20==0: print(i,len(out),'calls',NCALLS[0],flush=True)
print('done calls',NCALLS[0])
