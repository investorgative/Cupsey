"""For each candidate: of all tokens it bought (in the period we have Cupsey data for),
how often did Cupsey's main wallet buy the same token within 60 min AFTER the candidate?"""
import json,os,sys
from st import get,NCALLS
SOL='So11111111111111111111111111111111111111112'
ct=json.load(open('trades_6DQAG.json'))
T0=min(t['time'] for t in ct); T1=max(t['time'] for t in ct)
CB={}
for t in ct:
    if t['from']['address']==SOL:
        m=t['to']['address']; CB[m]=min(CB.get(m,1e20),t['time'])
big=json.load(open('big_tokens.json'))
CACHE='prec2_cache.json'
pc=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def history(w,max_pages=2):
    if w in pc: return pc[w]
    out=[];cur=None
    for _ in range(max_pages):
        j=get(f'/wallet/{w}/trades',{'cursor':cur} if cur else None)
        out+=[[t['time'],t['from']['address']==SOL,(t['to'] if t['from']['address']==SOL else t['from'])['address'],t['volume']['sol']] for t in j['trades']]
        if not j.get('hasNextPage') or not j['trades'] or j['trades'][-1]['time']<T0: break
        cur=j['nextCursor']
    pc[w]=out; json.dump(pc,open(CACHE,'w')); return out
def precision(w):
    h=history(w)
    fb={}
    for tm,isbuy,m,sol in h:
        if isbuy and T0<=tm<=T1-3600_000: fb[m]=min(fb.get(m,1e20),tm)
    n=len(fb)
    fol=[m for m,tm in fb.items() if m in CB and 0<CB[m]-tm<=3600_000]
    bigf=[m for m in fol if m in big]
    span=(max(x[0] for x in h)-min(x[0] for x in h))/3.6e6 if h else 0
    return {'tokens':n,'followed':len(fol),'followed_big':len(bigf),'prec':round(len(fol)/n,3) if n else None,
            'covers_from':min((x[0] for x in h),default=0),'span_h':round(span,1),'trades':len(h)}
if __name__=='__main__':
    for w in sys.argv[1].split(','):
        print(w[:10],precision(w),flush=True)
    print('calls',NCALLS)
