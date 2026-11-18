"""Discovery/validation split. Entities are found on the OLDER half of Cupsey entries only,
then checked on the NEWER half they were not selected on."""
import json,collections,math,sys,os,itertools
from insider import CUP
def entries():
    E={}
    big=json.load(open('big_tokens.json'))
    for fn in os.listdir('tok2'):
        k=fn[:-5]; d=json.load(open('tok2/'+fn)); b=big[k]
        E[k]=dict(mint=k,cb=b['first_buy'],fs=b['last_sell'],trades=d['pre']+d['hold'])
    ent={e['mint']:e for e in json.load(open('entries_6DQAG.json'))}
    for fn in os.listdir('tok3'):
        if not fn.endswith('.json'): continue
        d=json.load(open('tok3/'+fn)); e=d['entry']
        E[e['mint']]=dict(mint=e['mint'],cb=e['cb'],fs=e['first_sell'],trades=d['trades'])   # tok3 preferred (slots, first sell)
    for k,e in E.items():
        if k in ent: e['fs']=ent[k]['first_sell']
    return sorted(E.values(),key=lambda e:e['cb'])
def stats(E):
    S=collections.defaultdict(collections.Counter); co=collections.Counter(); tot_pre=tot_ctrl=0; used=0
    for e in E:
        tr=e['trades']; cb=e['cb']; fs=e['fs']
        if not tr: continue
        cov=cb-min(t['time'] for t in tr); W=min(120_000,cov//3)
        if W<30_000: continue
        used+=1
        cs=[t.get('slot') for t in tr if t['wallet'] in CUP and t['type']=='buy' and t.get('slot')]; cslot=min(cs) if cs else None
        by=collections.defaultdict(list)
        for t in tr: by[t['wallet']].append(t)
        pb={}
        for w,ts in by.items():
            if w in CUP: continue
            buys=[t for t in ts if t['type']=='buy']; sells=[t for t in ts if t['type']=='sell']
            pre=[t for t in buys if cb-W<=t['time']<=cb and (t['slot']<cslot if cslot and t.get('slot') else t['time']<cb-500)]
            nc=sum(1 for lo,hi in ((cb-2*W,cb-W),(cb-3*W,cb-2*W)) if any(lo<=t['time']<hi for t in buys))
            s=S[w]; s['ctrl']+=nc; tot_ctrl+=nc
            if not pre: continue
            s['pre']+=1; tot_pre+=1
            amt=sum(t['amount'] for t in pre); sd=[t for t in sells if cb<=t['time']<=fs+5000]
            if amt>0 and sum(t['amount'] for t in sd)>=0.5*amt:
                s['sold']+=1; s['pmilli']+=int((sum(t['volumeSol'] for t in sd)-sum(t['volumeSol'] for t in pre))*1000)
                last=max(t['time'] for t in sd)
                if 0<fs-last<=30000 and fs-cb>60000: s['exit']+=1
                pb[w]=(min(t['time'] for t in pre),min((t.get('slot') or 0) for t in pre))
                s.setdefault('coins',0); s['coins']+=1
        ws=sorted(pb.items(),key=lambda x:x[1][0])
        for i in range(len(ws)):
            for j in range(i+1,len(ws)):
                (a,(ta,sa)),(b,(tb,sb))=ws[i],ws[j]
                if tb-ta>2000: break
                if sa and sb and sa!=sb: continue
                co[tuple(sorted((a,b)))]+=1
    R=tot_pre/(tot_ctrl/2) if tot_ctrl else 1
    return used,S,co,R
def groups(S,co):
    par={}
    def f(x):
        par.setdefault(x,x)
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    for (a,b),n in co.items():
        if n>=2: par[f(a)]=f(b)
    G=collections.defaultdict(set)
    for w,s in S.items():
        if s['sold']>=1: G[f(w)].add(w)
    return list(G.values())
def score(mem,S,R):
    pre=sum(S[w]['pre'] for w in mem); ctrl=sum(S[w]['ctrl'] for w in mem)/2; exp=max(0.5,ctrl*R)
    return dict(pre=pre,exp=round(exp,1),z=round((pre-exp)/math.sqrt(exp),2),sold=sum(S[w]['sold'] for w in mem),
                exit=sum(S[w]['exit'] for w in mem),profit=round(sum(S[w]['pmilli'] for w in mem)/1000,1))
if __name__=='__main__':
    E=entries(); h=len(E)//2
    A,B=E[:h],E[h:]
    ua,SA,coA,RA=stats(A); ub,SB,coB,RB=stats(B)
    print(f'entries total {len(E)} | discovery (older) usable {ua}, R={RA:.2f} | validation (newer) usable {ub}, R={RB:.2f}')
    cands=[]
    for mem in groups(SA,coA):
        sc=score(mem,SA,RA)
        if sc['sold']>=3 and sc['z']>=2.5: cands.append((sc['z'],mem,sc))
    cands.sort(key=lambda x:-x[0])
    print(f'{len(cands)} candidate entities from discovery half (sold-into>=3, z>=2.5)')
    rep=0
    out=[]
    for z,mem,sc in cands:
        vb=score(mem,SB,RB); active=sum(SB[w]['pre'] for w in mem)>0
        ok=vb['sold']>=1 and vb['z']>=1.5
        rep+=ok
        out.append(dict(members=sorted(mem),disc=sc,val=vb,replicated=ok))
        print(f"  {'REPLICATES' if ok else '          '} disc: sold {sc['sold']} pre {sc['pre']}/exp {sc['exp']} z {sc['z']} | val: sold {vb['sold']} pre {vb['pre']}/exp {vb['exp']} z {vb['z']} exit {vb['exit']} +{vb['profit']} SOL | {len(mem)}w: {', '.join(w[:6] for w in sorted(mem)[:5])}")
    print(f'replicated: {rep} of {len(cands)}')
    # null check: same procedure with discovery z threshold on random wallets -> expected replication rate
    json.dump(out,open('holdout.json','w'))
