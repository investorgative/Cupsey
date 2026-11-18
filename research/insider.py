"""Insider tests over Cupsey entries.
Per wallet W and entry e (coin), with cb = Cupsey first buy, fs = Cupsey first sell:
  PRE   = W bought in [cb-W, cb)            (the window just before Cupsey)
  CTRL  = W bought in [cb-2W, cb-W) and [cb-3W, cb-2W)  (same-size control windows on the same coin, earlier)
  SOLD  = W sold >=50% of what it pre-bought between cb and fs+5s (sold into Cupsey's pump)
  EXIT  = W's last sell lies in [fs-30s, fs)  (out right before Cupsey starts selling)
An insider shows PRE >> CTRL across many coins; bots/snipers show PRE ~ CTRL.
Run on: tok2 (SolanaTracker windows) and/or tok3 (free RPC windows)."""
import json,os,collections,math,sys
CUP={'6DQAGJT7VZPVBsuG4kn3AvpyHCEi7B2RFFvMZdbqQqqP','2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK',
     'FxN3VZ4BosL5urG2yoeQ156JSdmavm9K5fdLxjkPmaMR','7NAd2EpYGGeFofpyvgehSXhH5vg6Ry6VRMW2Y6jiqCu1','DJ18fwvsL1XxYFRvrVCM861sxyAZCMucvECsEDGFCoiV'}
WIN=120_000
def load(src):
    out=[]
    if src=='tok2':
        big=json.load(open('big_tokens.json'))
        ent={e['mint']:e for e in json.load(open('entries_6DQAG.json'))} if os.path.exists('entries_6DQAG.json') else {}
        for fn in os.listdir('tok2'):
            k=fn[:-5]; d=json.load(open('tok2/'+fn)); b=big[k]; e=ent.get(k)
            fs=e['first_sell'] if e else b['last_sell']
            out.append(dict(mint=k,cb=b['first_buy'],fs=fs,trades=d['pre']+d['hold'],src='tok2'))
    else:
        for fn in os.listdir('tok3'):
            d=json.load(open('tok3/'+fn)); e=d['entry']
            out.append(dict(mint=e['mint'],cb=e['cb'],fs=e['first_sell'],trades=d['trades'],src='tok3'))
    return out
def analyse(entries):
    S=collections.defaultdict(lambda:collections.Counter()); EV=collections.defaultdict(list)
    used=0
    for e in entries:
        tr=e['trades']; cb=e['cb']; fs=e['fs']
        if not tr: continue
        t_first=min(t['time'] for t in tr)
        if cb-t_first<3*WIN: continue          # need room for the control windows
        used+=1
        by=collections.defaultdict(list)
        for t in tr: by[t['wallet']].append(t)
        for w,ts in by.items():
            if w in CUP: continue
            buys=[t for t in ts if t['type']=='buy']; sells=[t for t in ts if t['type']=='sell']
            pre=[t for t in buys if cb-WIN<=t['time']<cb-500]
            c1=[t for t in buys if cb-2*WIN<=t['time']<cb-WIN]; c2=[t for t in buys if cb-3*WIN<=t['time']<cb-2*WIN]
            s=S[w]
            if pre: s['pre']+=1
            if c1: s['ctrl']+=1
            if c2: s['ctrl']+=1
            if pre:
                amt=sum(t['amount'] for t in pre)
                sd=[t for t in sells if cb<=t['time']<=fs+5000]
                if amt>0 and sum(t['amount'] for t in sd)>=0.5*amt:
                    s['sold']+=1
                    pin=sum(t['volumeSol'] for t in pre); pout=sum(t['volumeSol'] for t in sd)
                    s['profit_milli']+=int((pout-pin)*1000)
                    last=max(t['time'] for t in sd)
                    if 0<fs-last<=30000 and fs-cb>60000: s['exit']+=1
                    EV[w].append(dict(mint=e['mint'],lead=round((cb-min(t['time'] for t in pre))/1000),pin=round(pin,3),pout=round(pout,3),exit_before=round((fs-last)/1000)))
    return used,S,EV
if __name__=='__main__':
    src=sys.argv[1] if len(sys.argv)>1 else 'tok2'
    used,S,EV=analyse(load(src))
    print('entries usable',used,'wallets',len(S))
    # score: pre vs ctrl (expected ctrl rate = 2 windows per entry), Poisson-ish z
    rows=[]
    for w,s in S.items():
        if s['sold']<2: continue
        pre=s['pre']; ctrl=s.get('ctrl',0)/2
        z=(pre-ctrl)/math.sqrt(ctrl+1)
        rows.append((s['sold'],z,w,dict(s)))
    rows.sort(key=lambda r:(-r[0]*min(r[1],5),))
    for sold,z,w,s in rows[:30]:
        print(f"{w} sold-into {sold} | pre {s['pre']} vs ctrl/2 {s.get('ctrl',0)/2:.1f} (z {z:.1f}) | exit-before {s.get('exit',0)} | profit {s.get('profit_milli',0)/1000:.1f} SOL")
    json.dump({'S':S,'EV':EV},open(f'insider_{src}.json','w'))
