"""Score wallets by WHERE Cupsey's profit comes from, not by hit rate.
Candidate role on a coin = held before his buy (not dev, not launch-block) and fully exited after his buy, before his first sell."""
import json,glob,collections,random,math,sys
random.seed(3)
C=[json.load(open(f)) for f in glob.glob('tok4x/*.json')]
P={c['mint']:c['pnl'] for c in C}; coins=list(P); n=len(coins)
totp=sum(max(0,p) for p in P.values())
cost={}
for c in C:
    try: d=json.load(open(f"tok4/{c['mint']}.json"))
    except Exception: continue
    for t in d['txs']:
        for w,side,a,v in t['trades']:
            k=(w,c['mint']); x=cost.setdefault(k,[0,0]); x[0 if side=='buy' else 1]+=v
R=collections.defaultdict(list); H=collections.defaultdict(set)
for c in C:
    for h in c['holders']:
        if h.get('launch_block'): continue
        H[h['w']].add(c['mint'])
        if h['status']=='exited':
            ci,co=cost.get((h['w'],c['mint']),[0,0])
            R[h['w']].append(dict(mint=c['mint'],cpnl=c['pnl'],val=h['val'] or 0,out=h['sol_out'],profit=h['sol_out']+co-ci,
                                  lead=(c['cb']-h['first_time'])/1000 if h.get('first_time') else None,snipe=h.get('snipe'),
                                  sell_after=(h['first_sell']-c['cb'])/1000 if h.get('first_sell') else None,xfer=h.get('xfer_to') or []))
pv=sorted(P.values())
def perm_p(k,obs,N=4000):
    if k==0: return 1
    ge=sum(1 for _ in range(N) if sum(random.sample(pv,k))>=obs)
    return (ge+1)/(N+1)
rows=[]
for w,L in R.items():
    k=len(L); s=sum(x['cpnl'] for x in L)
    wins=[x for x in L if x['cpnl']>0]; loss=[x for x in L if x['cpnl']<=0]
    vw=sum(x['val'] for x in wins)/len(wins) if wins else 0; vl=sum(x['val'] for x in loss)/len(loss) if loss else 0
    rows.append(dict(w=w,k=k,held=len(H[w]),cpnl=round(s,1),share=round(sum(max(0,x['cpnl']) for x in L)/totp,3),
                     p=perm_p(k,s) if k>=2 else None,size_win=round(vw,2),size_loss=round(vl,2),
                     own=round(sum(x['profit'] for x in L),2),snipe=sum(bool(x['snipe']) for x in L),L=L))
rows.sort(key=lambda r:(r['p'] if r['p'] is not None else 2, -r['cpnl']))
json.dump(rows,open('score4.json','w'))
print(f'coins analysed {n} (Cupsey pnl {sum(P.values()):.0f} SOL, wins {sum(p>0 for p in P.values())}) | wallets with >=1 candidate role {len(R)}, >=2 {sum(r["k"]>=2 for r in rows)}, >=3 {sum(r["k"]>=3 for r in rows)}')
print('wallet     roles/held  Cupsey-pnl-on-its-coins  share  p      size win/loss  own-profit  snipe')
for r in [r for r in rows if r['k']>=2][:30]:
    print(f"{r['w'][:8]}  {r['k']:3d}/{r['held']:<3d}   {r['cpnl']:8.1f}            {r['share']:.2f}  {r['p']:.3f}  {r['size_win']:5.2f}/{r['size_loss']:<5.2f}    {r['own']:7.2f}   {r['snipe']}")
