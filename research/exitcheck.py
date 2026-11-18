"""Per Cupsey entry: holders at his buy (exact, from tok4) -> which of them fully exited AFTER his buy
and BEFORE his first sell. Uses each holder's token account history (a handful of txs)."""
import json,os,sys,time,glob
from concurrent.futures import ThreadPoolExecutor
from solders.pubkey import Pubkey
from rpctrades import sigs, rpc, decode
from insider import CUP
ATA=Pubkey.from_string('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')
OUT='tok4x'; os.makedirs(OUT,exist_ok=True)
MIN_SOL=0.1          # ignore dust holders (value at Cupsey's entry price)
def ata(owner,mint,prog):
    return str(Pubkey.find_program_address([bytes(Pubkey.from_string(owner)),bytes(Pubkey.from_string(prog)),bytes(Pubkey.from_string(mint))],ATA)[0])
def snapshot(d):
    e=d['entry']; bal={}; first={}; signers=set(); last={}
    for t in d['txs']:
        signers.add(t['signer'])
        for o,b in t['bal'].items(): bal[o]=b; last[o]=t['time']
        for w,side,a,v in t['trades']:
            if side=='buy': first.setdefault(w,(t['slot'],t['time']))
    return bal,first,signers,last
def cupsey_price(mint,e):
    try:
        d=json.load(open(f'tok3/{mint}.json'))
        b=[t for t in d['trades'] if t['wallet'] in CUP and t['type']=='buy' and t['amount']>0]
        if b: return sum(t['volumeSol'] for t in b[:3])/sum(t['amount'] for t in b[:3])
    except Exception: pass
    return None
def check(owner,mint,prog,cb,fs,b0):
    a=ata(owner,mint,prog)
    r=sigs(a)
    win=[s for s in r if s.get('blockTime') and cb/1000<=s['blockTime']<=fs/1000 and not s.get('err')]
    if not win: return dict(status='held' if b0>0 else 'none',ata=a)
    tx=[]
    for s in sorted(win,key=lambda s:s['slot']):
        t=rpc('getTransaction',[s['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':1}],history=True)
        if not t: return dict(status='error',ata=a)
        post=None
        for bb in t['meta'].get('postTokenBalances') or []:
            if bb['mint']==mint and bb.get('owner')==owner: post=float(bb['uiTokenAmount']['uiAmountString'] or 0)
        tr=[x for x in decode(t,mint) if x[0]==owner]
        tx.append(dict(time=s['blockTime']*1000,slot=s['slot'],post=post if post is not None else 0.0,
                       sold=sum(x[2] for x in tr if x[1]=='sell'),bought=sum(x[2] for x in tr if x[1]=='buy'),
                       sol_out=sum(x[3] for x in tr if x[1]=='sell'),sol_in=sum(x[3] for x in tr if x[1]=='buy'),sig=s['signature']))
    endb=tx[-1]['post']; bought=sum(x['bought'] for x in tx)
    exited=endb<=0.05*b0 and bought<=0.2*b0
    return dict(status='exited' if exited else 'traded',ata=a,end=endb,tx=tx,
                first_sell=min((x['time'] for x in tx if x['sold']>0),default=None),
                sol_out=sum(x['sol_out'] for x in tx),sol_in=sum(x['sol_in'] for x in tx))
def run(fn):
    d=json.load(open(fn)); e=d['entry']; mint=e['mint']; out=f'{OUT}/{mint}.json'
    if os.path.exists(out) or not d['full']: return
    cb,fs=e['cb'],e['first_sell']
    info=rpc('getAccountInfo',[mint,{'encoding':'jsonParsed'}]); prog=info['value']['owner']
    px=cupsey_price(mint,e)
    bal,first,signers,last=snapshot(d)
    H=[]
    for o,b in bal.items():
        if b<=0 or o in CUP or o==d['creator'] or o not in signers: continue      # pools/PDAs never sign
        if px and b*px<MIN_SOL: continue
        fb=first.get(o)
        H.append(dict(w=o,bal=b,val=round(b*px,3) if px else None,first_slot=fb[0] if fb else None,first_time=fb[1] if fb else None,
                      launch_block=bool(fb and fb[0]==d['launch_slot']),snipe=bool(fb and fb[0]-d['launch_slot']<=3)))
    def job(h):
        try: h.update(check(h['w'],mint,prog,cb,fs,h['bal']))
        except Exception as ex: h.update(status='error',err=str(ex))
        return h
    with ThreadPoolExecutor(6) as ex: H=list(ex.map(job,H))
    json.dump(dict(mint=mint,cb=cb,fs=fs,pnl=e['pnl'],entry=e['entry'],px=px,creator=d['creator'],launch_time=d['launch_time'],
                   holders=H),open(out,'w'))
    c={};[c.__setitem__(h['status'],c.get(h['status'],0)+1) for h in H]
    print(mint[:6],'pnl',round(e['pnl'],1),'holders',len(H),c,flush=True)
if __name__=='__main__':
    while True:
        todo=[f for f in sorted(glob.glob('tok4/*.json'),key=os.path.getmtime) if not os.path.exists(f"{OUT}/{os.path.basename(f)}")]
        todo=[f for f in todo if json.load(open(f)).get('full')]
        for f in todo:
            try: run(f)
            except Exception as ex: print('ERR',f,ex,flush=True)
        if len(sys.argv)>1 and sys.argv[1]=='once': break
        if not any(os.path.exists(x) for x in glob.glob('tok4/*.lock')) and not todo: break
        time.sleep(60)
