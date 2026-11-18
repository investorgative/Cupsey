"""Flag hyperactive (bot) wallets: span of their last 1000 signatures. Cache in activity.json."""
import json,os,sys,time,requests
from concurrent.futures import ThreadPoolExecutor
R=['https://api.mainnet-beta.solana.com','https://solana-rpc.publicnode.com']
C=json.load(open('activity.json')) if os.path.exists('activity.json') else {}
def rpc(m,pa):
  for i in range(6):
    try:
      r=requests.post(R[i%2],json={'jsonrpc':'2.0','id':1,'method':m,'params':pa},timeout=30).json()
      if 'result' in r: return r['result']
    except Exception: pass
    time.sleep(1+i*2)
def one(w):
  s=rpc('getSignaturesForAddress',[w,{'limit':1000}])
  if s is None: return w,None
  span=(s[0]['blockTime']-s[-1]['blockTime'])/3600 if len(s)>1 and s[-1].get('blockTime') else None
  b=rpc('getBalance',[w])
  return w,{'n':len(s),'span_h':span,'bal':(b['value']/1e9 if b else None),'first':s[-1].get('blockTime') if s else None,'last':s[0].get('blockTime') if s else None}
def bot(a): return a and a['n']>=1000 and a['span_h'] is not None and a['span_h']<24*7
if __name__=='__main__':
  ws=[w for w in json.load(sys.stdin) if w not in C]
  with ThreadPoolExecutor(4) as ex:
    for w,a in ex.map(one,ws):
      if a: C[w]=a
  json.dump(C,open('activity.json','w'))
  print('cached',len(C))
