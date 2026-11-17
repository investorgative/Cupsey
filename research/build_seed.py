import json,os,sys
sys.path.insert(0,'../shadowwatch')
os.environ.setdefault('DB_PATH','/tmp/claude-0/-home-user-Cupsey/fc612a64-6a47-591e-b18a-50ea0c3b9b1a/scratchpad/seedtmp.db')
from tracker import analyse
CUP={'6DQAGJT7VZPVBsuG4kn3AvpyHCEi7B2RFFvMZdbqQqqP','2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK','FxN3VZ4BosL5urG2yoeQ156JSdmavm9K5fdLxjkPmaMR','7NAd2EpYGGeFofpyvgehSXhH5vg6Ry6VRMW2Y6jiqCu1'}
big=json.load(open('big_tokens.json'))
entries=[];obs=[]
for fn in os.listdir('tok2'):
    k=fn[:-5]; d=json.load(open('tok2/'+fn)); e=big[k]
    cb=e['first_buy']; cs=min(e['last_sell'],cb+45*60000)
    o=analyse(k,cb,cs,d['pre']+d['hold'],CUP); obs+=o
    entries.append(dict(mint=k,cb=cb/1000,cs=e['last_sell']/1000,cupsey_sol=e['total_buy'],n_pre=len(o),n_hits=sum(x['hit'] for x in o)))
pb=json.load(open('panbao.json')); C='6DQAGJT7VZPVBsuG4kn3AvpyHCEi7B2RFFvMZdbqQqqP'
cb=min(t['time'] for t in pb if t['wallet']==C and t['type']=='buy'); cs=max(t['time'] for t in pb if t['wallet']==C and t['type']=='sell')
o=analyse('6ZbWPYxFf8XyQ6dncrPAef1yz4W9nRF6rX3CYuE7pump',cb,cs,[t for t in pb if cb-3600000<=t['time']<=cs],CUP); obs+=o
entries.append(dict(mint='6ZbWPYxFf8XyQ6dncrPAef1yz4W9nRF6rX3CYuE7pump',symbol='Pan Bao Bao',cb=cb/1000,cs=cs/1000,cupsey_sol=17.7,n_pre=len(o),n_hits=sum(x['hit'] for x in o)))
links=[]
fc=json.load(open('funder_cache.json'))
for w,r in fc.items():
    if r.get('funder'): links.append([w,r['funder'],'fund_sol',r.get('amount') or 0,r.get('first_ts')])
EZC='EzcD6Kc7GYBqBdRo6Lnv3YiwpAUtxYtb5xKWw8r7Q7H8'; SZ='3szYsTw792LHoUygwKRXEvjASZL7APGeYb87etKBAdcS'; SINK='4sAUSQFdvWRBxR8UoLBYbw8CcXuwXWxnN8pXa4mtm5nU'
for r in json.load(open('fanout_3szYsT.json')):
    links.append([r[2],SZ,'fund_'+r[1].lower(),r[3],r[0]])
links.append([SZ,EZC,'fund_usdc',42760,1794843720])
links.append(['ETqRpFdAiA1wMPQ2XxnafCdGh1qTqL8iyecbnNxXtrYh',SINK,'sink_sol',44.46,1794890024])
links.append(['ETqRpFdAiA1wMPQ2XxnafCdGh1qTqL8iyecbnNxXtrYh',SINK,'fund_sol',0.048,1794828336])
ops=[dict(address=EZC,label='Treasury EzcD6',note='Funds the 3szYs distributor (42,760 USDC on 15 Nov; 159.7 SOL on 29 Aug)'),
     dict(address=SZ,label='Distributor 3szYs',note='Funded 14 burners on 16 Nov (7×5,000 + 7×1,000 USDC) incl. ETqR; 8×20 SOL on 29 Aug'),
     dict(address=SINK,label='Gas/profit wallet 4sAUSQ',note="Paid ETqR's gas, received 44.5 SOL of its profit"),
     dict(address='EagmNy9zK7GsriqQ3uHMmHCHLKKujLf7RuZpLdQqbS5g',label='Helper EagmNy',note='Touched ETqR right after its first swap')]
extra=os.path.exists('fanout_EzcD6K.json') and json.load(open('fanout_EzcD6K.json')) or []
for r in extra: links.append([r[2],EZC,'fund_'+r[1].lower(),r[3],r[0]])
hubs=['8DfHuYFv7VQ6wgcGtVDN2vtFn5ezF52hHNtPWYcqm8hU','iGdFcQoyR2MwbXMHQskhmNsqddZ6rinsipHc4TNSdwu','6LY1JzAFVZsP2a2xKrtU6znQMQ5h4i7tocWdgrkZzkzF',
      'F7p3dFrjRTbtRp8FRF6qHLomXbKRBzpvBLjtQcfcgmNe','BmFdpraQhkiDQE6SnfG5omcA1VwzqfXrwtNYBwWTymy6','5F1seMKUqSNhv45f6FhB2cFmgJbk8U1avJw7M6TexUq1',
      '2UPzAimP45QrxJbp5GvxtGYSgdQ1yxYemL6oZrTgMt4s','DQyrAcCrDXQ7NeoqGgDCZwBvWDcYmFCjSb9JtteuvPpz']
json.dump(dict(entries=entries,obs=obs,links=links,operators=ops,hubs=hubs),open('../shadowwatch/data/tracker_seed.json','w'))
print(len(entries),'entries',len(obs),'obs',sum(o['hit'] for o in obs),'hits',len(links),'links')
