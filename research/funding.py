"""Who funded each wallet? Walk back to the wallet's oldest txs and record SOL senders.
Also scan the most recent 1000 sigs for direct SOL transfers with other wallets in the set."""
import json,sys,os
from rpc import sigs, tx
ws=sys.argv[1].split(',')
out=json.load(open('funding.json')) if os.path.exists('funding.json') else {}
def transfers(t, me):
    res=[]
    if not t: return res
    ins=t['transaction']['message']['instructions']+[i for g in (t['meta'].get('innerInstructions') or []) for i in g['instructions']]
    for i in ins:
        p=i.get('parsed') if isinstance(i,dict) else None
        if isinstance(p,dict) and p.get('type') in ('transfer','transferWithSeed','createAccount') and i.get('program')=='system':
            inf=p['info']; src=inf.get('source'); dst=inf.get('destination') or inf.get('newAccount'); lam=inf.get('lamports',0)
            if me in (src,dst) and lam>=10_000_000: res.append((src,dst,lam/1e9,t['blockTime']))
    return res
for w in ws:
    if w in out: continue
    b=None; pages=0; last=[]
    while pages<25:
        r=sigs(w,b); pages+=1
        if not r: break
        last=r; b=r[-1]['signature']
        if len(r)<1000: break
    oldest=[s for s in reversed(last) if not s['err']][:6]
    fund=[]
    for s in oldest: fund+=transfers(tx(s['signature']),w)
    out[w]={'reached_start':len(last)<1000 and pages<25,'pages':pages,'first_transfers':fund,
            'first_seen':oldest[0]['blockTime'] if oldest else None}
    print(w[:8],out[w],flush=True)
    json.dump(out,open('funding.json','w'))
