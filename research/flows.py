"""SOL/token transfer counterparties of a wallet (system + spl transfers), newest and oldest txs."""
import json,sys,time,requests,os
from concurrent.futures import ThreadPoolExecutor
R=['https://api.mainnet-beta.solana.com','https://solana-rpc.publicnode.com']
def rpc(m,pa):
  for i in range(8):
    try:
      r=requests.post(R[i%2],json={'jsonrpc':'2.0','id':1,'method':m,'params':pa},timeout=40).json()
      if 'result' in r: return r['result']
    except Exception: pass
    time.sleep(1+i*2)
def sigs(w,maxn=5000):
  out=[];b=None
  while len(out)<maxn:
    p={'limit':1000}; 
    if b: p['before']=b
    s=rpc('getSignaturesForAddress',[w,p]) or []
    out+=s
    if len(s)<1000: break
    b=s[-1]['signature']
  return out
def tx(sig): return sig,rpc('getTransaction',[sig,{'encoding':'jsonParsed','maxSupportedTransactionVersion':0}])
def transfers(w,t):
  res=[]
  if not t: return res
  ins=list(t['transaction']['message']['instructions'])
  for ii in (t['meta'].get('innerInstructions') or []): ins+=ii['instructions']
  for i in ins:
    p=i.get('parsed')
    if not isinstance(p,dict): continue
    info=p.get('info',{}); ty=p.get('type')
    if i.get('program')=='system' and ty in('transfer','transferWithSeed'):
      a=info.get('lamports',0)/1e9
      if info.get('source')==w: res.append(('out',info.get('destination'),a))
      elif info.get('destination')==w: res.append(('in',info.get('source'),a))
  return res
def trace(w,newest=300,oldest=100,minsol=0.05):
  s=sigs(w,20000); ok=[x for x in s if not x.get('err')]
  pick=ok[:newest]+ok[-oldest:]
  with ThreadPoolExecutor(4) as ex: txs=dict(ex.map(tx,[x['signature'] for x in pick]))
  rows=[]
  for x in pick:
    for d,cp,a in transfers(w,txs.get(x['signature'])):
      if a>=minsol: rows.append((x['blockTime'],d,cp,round(a,3)))
  return {'n_sigs':len(s),'first':s[-1]['blockTime'] if s else None,'last':s[0]['blockTime'] if s else None,'rows':sorted(set(rows))}
if __name__=='__main__':
  w=sys.argv[1]; r=trace(w)
  os.makedirs('flows',exist_ok=True); json.dump(r,open(f'flows/{w}.json','w'))
  import datetime as D
  f=lambda t:D.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
  print(w,'sigs',r['n_sigs'],'first',f(r['first']),'last',f(r['last']))
  for t,d,cp,a in r['rows']: print(f(t),d,cp,a)
