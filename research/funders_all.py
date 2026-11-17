import json,collections
from funder import funder
d=json.load(open('features2.json'));H=d['HITS']
targets=[]
for w,hs in H.items():
    for h in hs:
        if h['sol_out']-h['sol_in']>=0.5: targets.append((w,h['token'])); 
ws=sorted({w for w,_ in targets})
print('wallets to trace',len(ws),flush=True)
for i,w in enumerate(ws):
    funder(w,max_pages=1)
    if i%100==0: print(i,flush=True)
print('done')
