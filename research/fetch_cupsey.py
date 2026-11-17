"""Step 1: download ~30 days of trades for Cupsey's public wallets."""
import json
from st import wallet_trades
for w in ['2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f','suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK']:
    tr=wallet_trades(w, max_pages=6)
    json.dump(tr,open(f'trades_{w[:6]}.json','w')); print(w[:6],len(tr))
