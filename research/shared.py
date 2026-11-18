"""Drowning/upstream link search: trace SOL flows of candidate wallets, find counterparties shared by >=2 candidates (hubs/exchanges excluded)."""
import json,os,sys,glob,collections
from concurrent.futures import ThreadPoolExecutor
import flows, activity
MINPNL=float(os.environ.get('MINPNL','10')); MINVAL=float(os.environ.get('MINVAL','0.5'))
def candidates():
  A=json.load(open('activity.json')) if os.path.exists('activity.json') else {}
  out=collections.defaultdict(list)
  for p in glob.glob('tok4x/*.json'):
    c=json.load(open(p))
    if c['pnl']<MINPNL: continue
    for h in c['holders']:
      if h['status']=='exited' and not h.get('launch_block') and not h.get('snipe') and h['w']!=c.get('creator') and (h.get('val') or 0)>=MINVAL:
        out[h['w']].append((c['mint'][:6],round(c['pnl'],1),h.get('val')))
  return out
def run_trace(w):
  f=f'flows/{w}.json'
  if os.path.exists(f): return
  try:
    r=flows.trace(w,newest=150,oldest=60); json.dump(r,open(f,'w'))
  except Exception as e: print('err',w,e)
if __name__=='__main__':
  os.makedirs('flows',exist_ok=True)
  C=candidates(); ws=list(C)
  # bot filter first (cheap)
  todo=[w for w in ws if w not in json.load(open('activity.json'))]
  if todo:
    with ThreadPoolExecutor(4) as ex:
      for w,a in ex.map(activity.one,todo):
        if a: activity.C[w]=a
    json.dump(activity.C,open('activity.json','w'))
  A=activity.C if activity.C else json.load(open('activity.json'))
  ws=[w for w in ws if w in A and not activity.bot(A[w])]
  print('candidates',len(C),'non-bot',len(ws),flush=True)
  if 'trace' in sys.argv:
    with ThreadPoolExecutor(int(os.environ.get("TH","5"))) as ex: list(ex.map(run_trace,ws))
  # shared counterparties
  CP=collections.defaultdict(lambda: collections.defaultdict(list))
  for w in ws:
    f=f'flows/{w}.json'
    if not os.path.exists(f): continue
    for t,d,cp,a in json.load(open(f))['rows']: CP[cp][w].append((d,a,t))
  json.dump({'cands':{w:C[w] for w in ws}},open('shared_cands.json','w'))
  multi=[(cp,ww) for cp,ww in CP.items() if len(ww)>=2 and cp not in ws or (cp in ws and len(ww)>=1)]
  need=[cp for cp,_ in multi if cp not in A]
  if need:
    with ThreadPoolExecutor(4) as ex:
      for w,a in ex.map(activity.one,need):
        if a: A[w]=a
    json.dump(A,open('activity.json','w'))
  def hub(cp): a=A.get(cp); return a is None or (a['bal'] or 0)>300 or activity.bot(a)
  res=[]
  for cp,ww in multi:
    if hub(cp) and cp not in ws: continue
    res.append({'cp':cp,'is_cand':cp in ws,'wallets':{w:ww[w] for w in ww},'act':A.get(cp)})
  res.sort(key=lambda r:-len(r['wallets']))
  json.dump(res,open('shared.json','w'),indent=0)
  for r in res[:40]:
    print(r['cp'][:10],'cand' if r['is_cand'] else '    ',len(r['wallets']),[ (w[:8],[(d,a) for d,a,_ in v][:3]) for w,v in list(r['wallets'].items())[:5]])
