"""Which execution fingerprints are over-represented among profitable early sellers vs control,
and do they recur in BOTH halves (on fresh wallets)?"""
import json,collections,math
J=[j for j in json.load(open('fp_jobs.json')) if j.get('fp')]
NAMES={'6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P':'pump','pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA':'pumpswap',
 'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4':'jupiter','LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo':'meteora-dlmm'}
def keyset(f):
    tipd=[d for d,_ in f['tips']]
    return {
     'router':tuple(sorted({NAMES.get(p,p[:8]) for p in f['progs']})),
     'cu':(f['cul'],f['cup']),
     'tipdest':tuple(sorted(d[:8] for d in tipd)) or ('none',),
     'tipamt':tuple(sorted(a for _,a in f['tips'])) or (0,),
     'combo':(tuple(sorted({NAMES.get(p,p[:8]) for p in f['progs']})),f['cul'],f['cup'],tuple(sorted(a for _,a in f['tips']))),
    }
tot=collections.Counter(j['grp'] for j in J); print('fingerprinted',tot)
for dim in ('router','cu','tipdest','tipamt','combo'):
    C=collections.defaultdict(lambda:collections.defaultdict(set))
    for j in J: C[keyset(j['fp'])[dim]][(j['grp'],j['half'])].add(j['w'])
    rows=[]
    for k,d in C.items():
        h=len(d[('HIT','old')]|d[('HIT','new')]); c=len(d[('CTRL','old')]|d[('CTRL','new')])
        if h<4: continue
        # rate ratio vs control with add-one smoothing
        rr=(h/tot['HIT'])/((c+1)/tot['CTRL'])
        rows.append((rr,h,c,len(d[('HIT','old')]),len(d[('HIT','new')]),k))
    rows.sort(key=lambda r:-r[0])
    print(f'\n== {dim}: top over-represented among HIT (wallet counts)')
    for rr,h,c,ho,hn,k in rows[:12]: print(f'  x{rr:5.1f} hit {h:3d} (old {ho} new {hn}) ctrl {c:3d}  {k}')
