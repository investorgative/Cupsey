"""First SOL funder of a wallet (cheap for fresh wallets; gives up on busy ones)."""
import json,os
from rpc import sigs, tx
CACHE='funder_cache.json'
_c=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def funder(w, max_pages=3):
    if w in _c: return _c[w]
    b=None; last=None; n=0
    for _ in range(max_pages):
        r=sigs(w,b)
        if not r: break
        n+=len(r); last=r; b=r[-1]['signature']
        if len(r)<1000: break
    res={'n_sigs':n,'complete':bool(last) and len(last)<1000,'funder':None,'amount':None,'first_ts':None}
    if res['complete']:
        for s in [s for s in reversed(last) if not s['err']][:4]:
            t=tx(s['signature'])
            if not t: continue
            ins=t['transaction']['message']['instructions']+[i for g in (t['meta'].get('innerInstructions') or []) for i in g['instructions']]
            for i in ins:
                p=i.get('parsed') if isinstance(i,dict) else None
                if isinstance(p,dict) and i.get('program')=='system' and p.get('type') in ('transfer','createAccount'):
                    inf=p['info']
                    if (inf.get('destination') or inf.get('newAccount'))==w and inf.get('lamports',0)>=5_000_000:
                        res.update(funder=inf['source'],amount=inf['lamports']/1e9,first_ts=t['blockTime']); break
            if res['funder']: break
    _c[w]=res; json.dump(_c,open(CACHE,'w')); return res
