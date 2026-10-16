"""One quote with feature timing and a fail-closed stale-market guard."""
import sys,json,argparse
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import pandas as pd
from etl.data import Market,orders
from etl.events import Events
from etl.hazard import Hazard
from etl.simulator import Simulator

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--at',required=True);p.add_argument('--strike',required=True,type=float)
    p.add_argument('--quantity',required=True,type=float);p.add_argument('--hours',required=True,type=float,choices=[.5,1,2,4,8,12,24])
    p.add_argument('--side',required=True,choices=['call','put']);p.add_argument('--verified-spot',type=float)
    p.add_argument('--market',default=str(ROOT/'data/raw/btc_market_history.csv.gz'))
    p.add_argument('--events',default=str(ROOT/'data/events/recorded_events.jsonl'))
    p.add_argument('--policy',default=str(ROOT/'results/price_policy.json'))
    p.add_argument('--clock',default='observed',choices=['observed','publication_proxy'])
    p.add_argument('--allow-diagnostic-fallback',action='store_true')
    a=p.parse_args();at=pd.Timestamp(a.at)
    if at.tzinfo is None:p.error('Quote time must include timezone, e.g. Z.')
    if a.strike<=0 or a.quantity<=0:p.error('Strike and quantity must be positive.')
    market=Market(a.market);ctx=market.context(at)
    if not ctx['fresh'] and not a.allow_diagnostic_fallback:
        print(json.dumps({'status':'no_quote','reason':'Fresh completed market candle required. Last close: '+str(ctx['market_asof'])}));sys.exit(2)
    train=orders(ROOT/'data/raw/pp_transactions_training.csv')
    hazard=Hazard().fit(train,market,at);sim=Simulator(market,Events(a.events,a.clock),hazard,at)
    row=SimpleNamespace(row_id=0,createdAt=at,optionType=0 if a.side=='call' else 1,productType=int(a.hours*3600),quantity_BTC=a.quantity,strikePrice=a.strike)
    result=sim.predict(row,verified_spot=a.verified_spot)[-1];policy=json.loads(Path(a.policy).read_text())
    if at<pd.Timestamp(policy.get('policy_available_from','2026-07-01T00:00:00Z')):
        p.error('Selected policy was not available at this quote time.')
    result['premium_USDC']=(1+policy['m'])*result['mean_claim']+policy['lambda']*(result['es95']-result['mean_claim'])
    result['status']='research_only_not_approved_for_live_trading'
    print(json.dumps(result,indent=2))
