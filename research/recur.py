"""For hub wallets of candidate clusters: all counterparties, matched against holders/exiters of every analysed Cupsey coin."""
import sys,json,glob,collections,os
import flows
from concurrent.futures import ThreadPoolExecutor
H=collections.defaultdict(list)
for p in glob.glob('tok4x/*.json'):
  c=json.load(open(p))
  for h in c['holders']: H[h['w']].append((c['mint'][:6],round(c['pnl'],1),h['status']))
def cps(w,cap=1500):
  f=f'flows/hub_{w}.json'
  if os.path.exists(f): return json.load(open(f))
  s=[x for x in flows.sigs(w,cap) if not x.get('err')][:cap]
  with ThreadPoolExecutor(6) as ex: txs=dict(ex.map(flows.tx,[x['signature'] for x in s]))
  out=collections.defaultdict(float)
  for x in s:
    for d,cp,a in flows.transfers(w,txs.get(x['signature'])): out[d+':'+cp]+=a
  r={'n':len(s),'cps':out}; json.dump(r,open(f,'w')); return r
for w in sys.argv[1:]:
  r=cps(w); hit=collections.defaultdict(list)
  for k,a in r['cps'].items():
    d,cp=k.split(':')
    if cp in H: hit[cp]=(d,round(a,2),H[cp])
  coins={m for v in hit.values() for m,_,_ in v[2]}
  print('\n',w,'txs',r['n'],'counterparties',len(r['cps']),'that hold Cupsey coins',len(hit),'distinct coins',len(coins))
  for cp,v in sorted(hit.items(),key=lambda x:-len(x[1][2]))[:12]: print('  ',cp[:10],v[0],v[1],v[2][:6])
