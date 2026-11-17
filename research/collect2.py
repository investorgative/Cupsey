import json,os
from st import get,NCALLS
big=json.load(open('big_tokens.json'))
keys=sorted(big,key=lambda k:-big[k]['first_buy'])[:110]
os.makedirs('tok2',exist_ok=True)
def fetch_back(m,end,start,cap):
    out=[];cur=int(end)
    for _ in range(cap):
        j=get(f'/trades/{m}',{'sortDirection':'DESC','cursor':cur})
        tr=[t for t in j['trades'] if t['time']>=start]; out+=tr
        if len(tr)<len(j['trades']) or not j.get('hasNextPage') or not j['trades']: return out[::-1],True
        cur=j['nextCursor']
    return out[::-1],False
def fetch(m,start,end,cap):
    out=[];cur=int(start)
    for _ in range(cap):
        j=get(f'/trades/{m}',{'sortDirection':'ASC','cursor':cur})
        tr=[t for t in j['trades'] if t['time']<=end]; out+=tr
        if len(tr)<len(j['trades']) or not j.get('hasNextPage') or not j['trades']: return out,True
        cur=j['nextCursor']
    return out,False
for i,k in enumerate(keys):
    fn=f'tok2/{k}.json'
    if os.path.exists(fn): continue
    e=big[k]; cb=e['first_buy']; cs=min(e['last_sell'],cb+45*60000)+30000
    try:
        pre,okp=fetch_back(k,cb,cb-60*60000,4)
        hold,okh=fetch(k,cb,cs,5)
    except Exception as ex:
        print('err',k,ex,flush=True); continue
    json.dump({'pre':pre,'hold':hold,'pre_complete':okp,'hold_complete':okh},open(fn,'w'))
    if i%10==0: print(i,len(pre),len(hold),okp,okh,'calls',NCALLS[0],flush=True)
print('done calls',NCALLS[0])
