import json,time,sys
from concurrent.futures import ThreadPoolExecutor
from rpctrades import sigs, rpc
from prec_rpc import hist
SOL='So11111111111111111111111111111111111111112'
CUPW=['6DQAGJT7VZPVBsuG4kn3AvpyHCEi7B2RFFvMZdbqQqqP','2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f']
w=sys.argv[1]
H,n,miss=hist(w)
t0=min(x[0] for x in H)-3600_000
CB={}
for c in CUPW:
    h,_,_=hist(c,maxs=3000)
    for tm,m,buy in h:
        if buy and tm>=t0: CB[m]=min(CB.get(m,1e20),tm)
fb={};fs={}
for tm,m,buy in H:
    if buy: fb[m]=min(fb.get(m,1e20),tm)
    else: fs[m]=max(fs.get(m,0),tm)
f=lambda ms:time.strftime('%m-%d %H:%M:%S',time.gmtime(ms/1000))
print(f'{w[:8]}: {len(fb)} coins; Cupsey coins in window {len(CB)}, Cupsey data until {f(max(CB.values()))}')
k=0
for m,tm in sorted(fb.items(),key=lambda x:x[1]):
    c=CB.get(m); tag=''
    if c: d=(c-tm)/1000; tag=f'CUPSEY {"AFTER" if d>0 else "before"} it by {abs(d):.0f}s'; k+=d>0
    print(f'  {f(tm)} {m[:8]} sold-last {f(fs[m]) if m in fs else "-"}  {tag}')
print('Cupsey followed',k,'of',len(fb))
