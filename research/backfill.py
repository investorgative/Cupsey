import json,os,collections,time,sys
from rpctrades import window, fetch_trades
SOL='So11111111111111111111111111111111111111112'
tr=json.load(open('trades_6DQAG.json'))
P=collections.defaultdict(list)
for t in tr:
    buy=t['from']['address']==SOL; m=(t['to'] if buy else t['from'])['address']
    P[m].append((t['time'],'B' if buy else 'S',t['volume']['sol'],t['tx']))
entries=[]
for m,v in P.items():
    v.sort(); b=[x for x in v if x[1]=='B']; s=[x for x in v if x[1]=='S']
    if not b or not s: continue
    t0=b[0][0]; entry=sum(x[2] for x in b if x[0]-t0<=10000)
    if entry<5: continue
    fs=[x for x in s if x[0]>=t0]
    if not fs: continue
    entries.append(dict(mint=m,cb=t0,buy_tx=b[0][3],first_sell=fs[0][0],first_sell_tx=fs[0][3],last_sell=fs[-1][0],last_sell_tx=fs[-1][3],entry=entry,
                        buys=[(x[0],x[2]) for x in b],sells=[(x[0],x[2]) for x in s]))
entries.sort(key=lambda e:-e['cb'])
json.dump(entries,open('entries_6DQAG.json','w'))
os.makedirs('tok3',exist_ok=True)
print('entries',len(entries),flush=True)
order=list(enumerate(entries))
if len(sys.argv)>1 and sys.argv[1]=='rev': order=order[::-1]
for i,e in order:
    fn=f"tok3/{e['mint']}.json"
    if os.path.exists(fn) or os.path.exists(fn+'.lock'): continue
    open(fn+'.lock','w').close()
    t=time.time()
    try:
        pre=window(e['mint'],before_sig=e['buy_tx'],max_sigs=600)
        hold=window(e['mint'],before_sig=e['first_sell_tx'],until_sig=e['buy_tx'],max_sigs=1500)
        exitw=[]
        if e['last_sell_tx']!=e['first_sell_tx']:
            exitw=window(e['mint'],before_sig=e['last_sell_tx'],until_sig=e['first_sell_tx'],max_sigs=300)
        after=window(e['mint'],until_sig=e['last_sell_tx'],max_sigs=0)  # placeholder
        sigs_all={s['signature']:s for s in pre+hold+exitw}
        trades=fetch_trades(e['mint'],list(sigs_all.values()))
        json.dump(dict(entry=e,trades=trades,n_pre=len(pre),n_hold=len(hold),n_exit=len(exitw),
                       pre_full=len(pre)<600,hold_full=len(hold)<1500),open(fn,'w'))
        os.remove(fn+'.lock')
        print(i,e['mint'][:6],'pre',len(pre),'hold',len(hold),'exit',len(exitw),'trades',len(trades),f'{time.time()-t:.0f}s',flush=True)
    except Exception as ex:
        print('ERR',e['mint'],ex,flush=True)
print('DONE',flush=True)
