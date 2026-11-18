"""Execution fingerprint of pre-buy transactions: router program(s), compute-unit limit/price,
tip destination + amount. Compares profitable early sellers vs control pre-buyers."""
import json,os,collections,random,sys,base58,threading
from concurrent.futures import ThreadPoolExecutor
from holdout import entries, CUP
from rotation2 import hitters
from rpctrades import rpc
STD={'ComputeBudget111111111111111111111111111111','11111111111111111111111111111111','TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
     'TokenzQdBNbLqP5VEhdkAS6EFDnWhNBWQxkNvUbuF5RWr','ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL','MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr',
     'Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo','SysvarRent111111111111111111111111111111111'}
JITO={'96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5','HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe','Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY',
 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49','DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh','ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt',
 'DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL','3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT'}
CACHE='fp_cache.json'; fpc=json.load(open(CACHE)) if os.path.exists(CACHE) else {}; L=threading.Lock()
def fp(sig):
    if sig in fpc: return fpc[sig]
    t=rpc('getTransaction',[sig,{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}])
    if not t: return None
    msg=t['transaction']['message']; keys=[k['pubkey'] for k in msg['accountKeys']]
    signer=keys[0]; nsig=sum(1 for k in msg['accountKeys'] if k.get('signer'))
    progs=[];cul=cup=None;tips=[]
    for ins in msg['instructions']:
        p=ins.get('programId')
        if p=='ComputeBudget111111111111111111111111111111' and ins.get('data'):
            d=base58.b58decode(ins['data'])
            if d[0]==2: cul=int.from_bytes(d[1:5],'little')
            elif d[0]==3: cup=int.from_bytes(d[1:9],'little')
        elif p=='11111111111111111111111111111111' and ins.get('parsed',{}).get('type')=='transfer':
            i=ins['parsed']['info']; 
            if i['source']==signer: tips.append((i['destination'],i['lamports']))
        elif p not in STD: progs.append(p)
    m=t['meta']
    r=dict(progs=progs,cul=cul,cup=cup,tips=tips,nsig=nsig,fee=m.get('fee'),nix=len(msg['instructions']),
           jito=any(d in JITO for d,_ in tips),alt=bool(msg.get('addressTableLookups')),pos=None)
    with L: fpc[sig]=r
    return r
if __name__=='__main__':
    E=entries(); h=len(E)//2; jobs=[]
    for name,part in (('old',E[:h]),('new',E[h:])):
        H,P=hitters(part); hit=[w for w,l in H.items() if sum(x[1] for x in l)>=0.5]
        mint_set={x[0] for w in hit for x in H[w]}
        # control: pre-buyers on same coins who did not sell into him
        rest=sorted(P-set(H)); random.seed(7); ctrl=set(random.sample(rest,len(hit)))
        hit=set(hit)
        for e in part:
            cs=[t.get('slot') for t in e['trades'] if t['wallet'] in CUP and t['type']=='buy' and t.get('slot')]; cslot=min(cs) if cs else None
            seen=set()
            for t in sorted(e['trades'],key=lambda t:t['time']):
                w=t['wallet']
                if t['type']!='buy' or w in seen or not t.get('tx'): continue
                if not (t['slot']<cslot if cslot and t.get('slot') else t['time']<e['cb']-500): continue
                g='HIT' if w in hit else 'CTRL' if w in ctrl else None
                if g: seen.add(w); jobs.append(dict(half=name,grp=g,w=w,mint=e['mint'],tx=t['tx'],lead=e['cb']-t['time']))
    print('jobs',len(jobs),collections.Counter((j['half'],j['grp']) for j in jobs),flush=True)
    with ThreadPoolExecutor(4) as ex:
        for i,(j,r) in enumerate(zip(jobs,ex.map(lambda j:fp(j['tx']),jobs))):
            j['fp']=r
            if i%100==0:
                print(' fp',i,flush=True)
                with L: json.dump(fpc,open(CACHE,'w'))
    json.dump(fpc,open(CACHE,'w')); json.dump(jobs,open('fp_jobs.json','w'))
