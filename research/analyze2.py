"""Pre-positioning analysis around Cupsey's BIG entries (6DQAG wallet).
For each token: wallets that bought in the 60 min before his first buy and sold during his hold."""
import json,os,collections,statistics,sys
C={'6DQAGJT7VZPVBsuG4kn3AvpyHCEi7B2RFFvMZdbqQqqP'}
big=json.load(open('big_tokens.json'))
W=collections.defaultdict(lambda:collections.defaultdict(float))
HITS=collections.defaultdict(list)
N=0
for f in os.listdir('tok2'):
    k=f[:-5]; d=json.load(open('tok2/'+f)); e=big[k]
    cb=e['first_buy']; cs=e['last_sell']
    tr=d['pre']+d['hold']
    if not tr: continue
    N+=1
    by=collections.defaultdict(list)
    for t in tr: by[t['wallet']].append(t)
    for w,ts in by.items():
        if w in C: continue
        pb=[t for t in ts if t['type']=='buy' and t['time']<cb-1000]
        if not pb: continue
        st=W[w]; st['pre_tokens']+=1
        amt_in=sum(t['amount'] for t in pb); sol_in=sum(t['volumeSol'] for t in pb)
        sd=[t for t in ts if t['type']=='sell' and cb-1000<=t['time']<=cs]
        amt_out=sum(t['amount'] for t in sd); sol_out=sum(t['volumeSol'] for t in sd)
        lead=(cb-min(t['time'] for t in pb))/1000
        if sol_in>=0.1 and amt_out>=0.5*amt_in:
            first_sell=(min(t['time'] for t in sd)-cb)/1000
            before_exit=(cs-max(t['time'] for t in sd))/1000
            st['hits']+=1; st['sol_in']+=sol_in; st['sol_out']+=sol_out
            HITS[w].append(dict(token=k,lead_s=round(lead),sol_in=round(sol_in,3),sol_out=round(sol_out,3),
                                first_sell_s=round(first_sell),sold_before_cupsey_exit_s=round(before_exit)))
json.dump({'N':N,'W':W,'HITS':HITS},open('features2.json','w'))
print('tokens',N,'wallets that pre-bought',len(W))
rows=sorted(W.items(),key=lambda x:(-x[1]['hits'],-x[1]['sol_out']))
for w,s in rows[:int(sys.argv[1]) if len(sys.argv)>1 else 40]:
    h=HITS[w]
    print(f"{w} hits {int(s['hits']):3d}/{int(s['pre_tokens']):3d} in {s['sol_in']:7.2f} out {s['sol_out']:7.2f} "
          f"lead_med {statistics.median([x['lead_s'] for x in h]) if h else '-'}s first_sell_med {statistics.median([x['first_sell_s'] for x in h]) if h else '-'}s")
