"""Stage 1: per-token behavioural features of every wallet that traded around Cupsey's entries."""
import json,os,collections,math
CUPSEY={'2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK'}
toks=json.load(open('cupsey_tokens.json'))
F=collections.defaultdict(lambda:collections.Counter())
EX=collections.defaultdict(list)
ntok=0
for f in os.listdir('tok'):
    k=f[:-5]; tr=json.load(open('tok/'+f)); e=toks[k]
    if not tr: continue
    ntok+=1
    cb=e['first_buy']; cs=e['last_sell'] or cb+60_000
    covered_to=tr[-1]['time']
    byw=collections.defaultdict(list)
    for t in tr: byw[t['wallet']].append(t)
    for w,ts in byw.items():
        if w in CUPSEY: continue
        buys=[t for t in ts if t['type']=='buy']; sells=[t for t in ts if t['type']=='sell']
        fb=min((t['time'] for t in buys),default=None)
        c=F[w]; c['tokens']+=1
        if fb is not None:
            d=(fb-cb)/1000
            if -180<=d<0: c['pre_buy']+=1; c['lead_sum']+=-d
            if abs(d)<=1: c['same_sec']+=1
            if 0<d<=30: c['follow_buy']+=1
            c['buy_sol']+=sum(t['volumeSol'] for t in buys)
        si=[t for t in sells if cb<=t['time']<=cs+5000]
        if si: c['sell_into']+=1
        if fb is not None and -180<=(fb-cb)/1000<0 and si: c['exitliq']+=1; EX[w].append(k)
        if fb is not None and abs((fb-cb)/1000)<=1: EX[w+'#ss'].append(k)
print('tokens analysed',ntok,'wallets',len(F))
json.dump({'ntok':ntok,'F':F,'EX':EX},open('features.json','w'))
rank=sorted(F.items(),key=lambda x:-(x[1]['exitliq']*3+x[1]['same_sec']*3+x[1]['pre_buy']))
for w,c in rank[:40]: print(w, dict(c))
