"""List ALL signatures between Cupsey's buy and his first sell for every entry (cheap: 1000 per call)."""
import json,os,sys
from rpctrades import sigs
E=json.load(open('entries_6DQAG.json'))
OUT='holdsigs'; os.makedirs(OUT,exist_ok=True)
for i,e in enumerate(E):
    fn=f"{OUT}/{e['mint']}.json"
    if os.path.exists(fn) or not e.get('first_sell_tx'): continue
    got=[];b=e['first_sell_tx']
    while True:
        r=sigs(e['mint'],before=b,until=e['buy_tx'])
        got+=[[s['signature'],s['slot'],s.get('blockTime'),bool(s.get('err'))] for s in r]
        if len(r)<1000: break
        b=r[-1]['signature']
        if len(got)>60000: break
    json.dump(got,open(fn,'w')); print(i,e['mint'][:6],len(got),flush=True)
