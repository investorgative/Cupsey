"""Scan an address's recent transactions for any contact with a set of known network addresses."""
import json,sys,collections,time
from concurrent.futures import ThreadPoolExecutor
from rpctrades import sigs, rpc
a=sys.argv[1]; N=int(sys.argv[2]) if len(sys.argv)>2 else 1500
s=json.load(open('../shadowwatch/data/tracker_seed.json')); txt=json.dumps(s)
import re
known=set(re.findall(r'[1-9A-HJ-NP-Za-km-z]{43,44}',txt))
known|={'EzcD6Kc7GYBqBdRo6Lnv3YiwpAUtxYtb5xKWw8r7Q7H8','3szYsTw792LHoUygwKRXEvjASZL7APGeYb87etKBAdcS','4sAUSQFdvWRBxR8UoLBYbw8CcXuwXWxnN8pXa4mtm5nU',
 'ETqRpFdAiA1wMPQ2XxnafCdGh1qTqL8iyecbnNxXtrYh','3tsMk1wL3vNeVxxKbccM9wH1CgpwtTgb8Pbn6myuDbKP','EGKn9PmWh4G7ywcjMFtuxd6upM8tma4wgVNn4zmRQuNn'}
known.discard(a)
allr=[];b=None
while len(allr)<N:
    r=sigs(a,before=b); allr+=r
    if len(r)<1000: break
    b=r[-1]['signature']
ok=[x for x in allr if not x.get('err')][:N]
print(a[:8],'sigs',len(allr),time.strftime('%m-%d %H:%M',time.gmtime(allr[-1]['blockTime'])),'->',time.strftime('%m-%d %H:%M',time.gmtime(allr[0]['blockTime'])),flush=True)
def one(x):
    t=rpc('getTransaction',[x['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}])
    if not t: return None
    keys=[k['pubkey'] for k in t['transaction']['message']['accountKeys']]
    m=t['meta']; i=keys.index(a) if a in keys else None
    d=(m['postBalances'][i]-m['preBalances'][i])/1e9 if i is not None else 0
    hit=[k for k in keys if k in known]
    return (x['blockTime'],keys[0],hit,round(d,3),len(m.get('postTokenBalances') or []))
with ThreadPoolExecutor(6) as ex: R=[r for r in ex.map(one,ok) if r]
hits=[r for r in R if r[2]]
print('fetched',len(R),'contacts with known network:',len(hits))
for r in hits[:30]: print('  ',time.strftime('%m-%d %H:%M',time.gmtime(r[0])),'signer',r[1][:8],'known',[k[:8] for k in r[2]],'dSOL',r[3])
# also: plain SOL in/out counterparties
cp=collections.Counter()
for r in R:
    if r[4]==0 and abs(r[3])>=0.05: cp[(r[1][:8], 'in' if r[3]>0 else 'out')]+=1
print('plain-transfer counterparties (signer, dir):',cp.most_common(12))
