"""Builds shadowwatch/data/wallets.json (conviction scores + evidence + method report) from the research outputs."""
import json,time,html
sc=json.load(open('scored.json')); B=json.load(open('bundle.json')); N=sc['N']
F=json.load(open('features.json'))['F']
CUPSEY=[{"address":"2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f","label":"Cupsey (kolscan)","tier":"official",
         "evidence":["Wallet listed as Cupsey on kolscan.io (linked to x.com/Cupseyy)"]},
        {"address":"suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK","label":"Cupsey #2 (older public)","tier":"official",
         "evidence":["Older publicly attributed Cupsey wallet","Buys the same token within 2 s of the kolscan wallet in 97% of cases (1118 / 1156 shared tokens)"]}]
rows=[]
for s,w,c,p in sc['res']:
    b=B.get(w,{}); t=c.get('tokens',0); sd=sc['SLOT'].get(w,[]); pr=sc['PREC'].get(w)
    adj=(b['adjacent']/b['n']) if b.get('n',0)>=3 else None
    same=(b['same_slot']/b['n']) if b.get('n',0)>=3 else None
    prec=(pr['hit']/pr['n']) if pr and pr['n']>=5 else None
    if prec is None and pr and pr['span_h']>0:   # no time overlap with our Cupsey data: rate-based upper bound
        prec_ub=min(1,(1300/720)/(pr['tokens_total']/pr['span_h']))
    else: prec_ub=None
    cooc=t/N
    # conviction
    score=0
    score+=35*(adj if adj is not None else 0)                 # same Jito bundle / consecutive tx = same operator
    score+=25*(prec if prec is not None else (prec_ub or 0.2)) # trades (almost) only Cupsey tokens
    score+=20*min(1,cooc/0.6)                                  # shows up on most of his tokens
    score+=10*(same if same is not None else 0)
    score+=10*min(1,(c.get('same_sec',0))/max(1,t))
    score=round(min(99,score))
    ev=[]
    ev.append(f"Traded {t} of {N} sampled Cupsey tokens ({cooc:.0%}) in the window around his entry")
    if c.get('same_sec'): ev.append(f"Bought within ±1 s of Cupsey on {c['same_sec']} tokens; bought 1–180 s before him on {c.get('pre_buy',0)}")
    if b.get('n'): ev.append(f"Slot test ({b['n']} samples): same slot as Cupsey {b['same_slot']}×, consecutive tx in the same bundle {b['adjacent']}×")
    if prec is not None: ev.append(f"Of its own recent tokens, {pr['hit']}/{pr['n']} ({prec:.0%}) were also traded by Cupsey")
    elif prec_ub is not None: ev.append(f"Trades ~{pr['tokens_total']/max(pr['span_h'],0.1):.0f} tokens/hour vs Cupsey's ~2/hour → at most ~{prec_ub:.0%} overlap (generic sniper)")
    if c.get('exitliq'): ev.append(f"Bought before Cupsey and sold while he was holding on {c['exitliq']} tokens")
    if adj and adj>=0.5: kind="Bundled shadow wallet"
    elif same and same>=0.8: kind="Same-slot follower (fast copy-bot?)"
    elif c.get('pre_buy',0)>c.get('same_sec',0): kind="Early sniper (not Cupsey-specific)"
    else: kind="Co-trader"
    tier="high" if score>=70 else "medium" if score>=45 else "low"
    rows.append(dict(address=w,label=f"{kind.split(' (')[0]} {w[:4]}",score=score,tier=tier,kind=kind,evidence=ev,
                     stats={"type":kind,"tokens":f"{t}/{N}","same-sec":c.get('same_sec',0),"pre-buys":c.get('pre_buy',0),
                            "precision":f"{prec:.0%}" if prec is not None else "–"}))
rows.sort(key=lambda r:-r['score'])
rows=rows[:30]
for r in rows:
    if r['address'].startswith('FxN3'): r['label']="Shadow A (FxN3)"
    if r['address'].startswith('7NAd'): r['label']="Shadow B (7NAd)"
summary=("2 high-conviction shadow wallets found (FxN3…, 7NAd…). They are bundled with Cupsey's public wallets in the same "
         "block, match his size 1:1 and exit in the same second. No wallet was found that systematically buys before him.")
method=open('report.html').read()
json.dump({"generated":time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime()),"summary":summary,"method":method,
           "cupsey":CUPSEY,"shadows":rows},open('../shadowwatch/data/wallets.json','w'),indent=1)
for r in rows[:12]: print(r['score'],r['tier'],r['label'],r['kind'])
