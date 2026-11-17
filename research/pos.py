import json,collections
SOL='So11111111111111111111111111111111111111112'
def positions(tr):
    P=collections.defaultdict(lambda:{'buys':[],'sells':[]})
    for t in tr:
        if t['from']['address']==SOL: P[t['to']['address']]['buys'].append((t['time'],t['from']['amount'],t['to'].get('marketCap'),t['tx']))
        elif t['to']['address']==SOL: P[t['from']['address']]['sells'].append((t['time'],t['to']['amount'],t['from'].get('marketCap'),t['tx']))
    return P
