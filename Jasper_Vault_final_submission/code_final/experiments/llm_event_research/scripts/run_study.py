"""Offline, deterministic chronological experiment; no network or API key required."""
import sys, json, time, hashlib, platform, argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
import scipy, sklearn
from etl.data import Market,orders,audit,QUOTE_FIELDS
from etl.events import Events,ARMS
from etl.hazard import Hazard
from etl.simulator import Simulator
from etl.evaluation import policy_search,apply_policy,metrics,paired_bootstrap

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False))

def run(args):
    started=time.time(); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    raw=ROOT/'data/raw'
    market=Market(args.market or raw/'btc_market_history.csv.gz')
    train=orders(raw/'pp_transactions_training.csv'); val=orders(raw/'pp_transactions_validation.csv')
    events=Events(args.events or ROOT/'data/events/recorded_events.jsonl',args.clock)
    dump(out/'data_audit.json',audit(train,val,market)); dump(out/'event_audit.json',events.audit())
    results=[]; models=[]
    folds=[('development_may','2026-05-01','2026-06-01'),('development_june','2026-06-01','2026-07-01'),('test_july','2026-07-01','2026-08-01')]
    for fold,begin,end in folds:
        cutoff=pd.Timestamp(begin,tz='UTC')
        hazard=Hazard().fit(train,market,cutoff); sim=Simulator(market,events,hazard,cutoff)
        models.append({'fold':fold,**sim.meta})
        d=train[train.scorable & (train.createdAt>=cutoff) & (train.createdAt<pd.Timestamp(end,tz='UTC'))]
        print(f'{fold}: {len(d)} quotes, {sim.meta["archive_paths"]} past paths',flush=True)
        label=d.set_index('row_id').realizedProfit_USDC
        rows=[]
        # Only quote fields reach the predictor. Outcome is used solely in proper-score calculation.
        for j,r in enumerate(d[QUOTE_FIELDS].itertuples(index=False)):
            for p in sim.predict(r,outcome=float(label.loc[r.row_id])):rows.append({**p,'fold':fold})
            if (j+1)%500==0:print(f'  {j+1}/{len(d)}',flush=True)
        f=pd.DataFrame(rows).merge(d[['row_id','closedAt','quantity_BTC','strikePrice','productType','optionType','premiumAmount_USDC','realizedProfit_USDC','apiBasePrice_per_BTC_USDC']],on='row_id',validate='many_to_one')
        results.append(f)
    pred=pd.concat(results,ignore_index=True)
    policy_cutoff=pd.Timestamp('2026-07-01',tz='UTC')
    dev=pred[(pred.fold!='test_july') & (pred.arm=='market_only') & (pred.closedAt<policy_cutoff)]
    policy,grid=policy_search(dev)
    policy.update({'policy_available_from':str(policy_cutoff),'development_rows':len(dev),
                   'last_policy_outcome':str(dev.closedAt.max())})
    dump(out/'price_policy.json',policy); grid.to_csv(out/'policy_search.csv',index=False)
    pred=apply_policy(pred,policy); pred.to_csv(out/'scored_predictions.csv',index=False)
    summary={fold:{arm:metrics(g) for arm,g in f.groupby('arm')} for fold,f in pred.groupby('fold')}
    test=pred[pred.fold=='test_july']; boot=paired_bootstrap(test)
    dump(out/'metrics.json',summary); dump(out/'paired_day_bootstrap.json',boot)
    uplift=summary['test_july']['verified_research']['gross_profit_e0']-summary['test_july']['market_only']['gross_profit_e0']
    ntest=summary['test_july']['verified_research']['orders']
    pd.DataFrame([{'incremental_cost_per_order_USDC':c,'july_orders':ntest,
        'news_uplift_before_cost':uplift,'news_uplift_after_cost':uplift-c*ntest}
        for c in [0,.005,.01,.02,.05,.1]]).to_csv(out/'research_cost_sensitivity.csv',index=False)
    # Fixed cut at first validation creation. Never use validation settlement clocks.
    cutoff=val.loc[val.valid_quote,'createdAt'].min()
    hazard=Hazard().fit(train,market,cutoff); sim=Simulator(market,events,hazard,cutoff)
    models.append({'fold':'blind_validation',**sim.meta})
    rows=[]; v=val[val.valid_quote]
    print(f'blind_validation: {len(v)} quotes; outcomes intentionally unavailable',flush=True)
    for j,r in enumerate(v[QUOTE_FIELDS].itertuples(index=False)):
        rows.extend(sim.predict(r))
        if (j+1)%1000==0: print(f'  {j+1}/{len(v)}',flush=True)
    vp=pd.DataFrame(rows).merge(v[['row_id','quantity_BTC','strikePrice','productType','optionType','apiBasePrice_per_BTC_USDC']],on='row_id',validate='many_to_one')
    vp=apply_policy(vp,policy); vp.to_csv(out/'validation_predictions.csv',index=False)
    vs={arm:{'orders':len(g),'fresh_market_orders':int(g.fresh_market.sum()),'fallback_orders':int((~g.fresh_market).sum()),
        'quoted_total':float(g.quoted_premium.sum()),'median_quote':float(g.quoted_premium.median()),
        'changed_by_event':int((g.event_weight>0).sum()),'max_event_weight':float(g.event_weight.max()),
        'outcome_metrics_available':False} for arm,g in vp.groupby('arm')}
    dump(out/'validation_summary.json',vs); dump(out/'model_fit_audit.json',models)
    segments=[]
    for dim,col in [('duration','productType'),('direction','optionType'),('event_context','event_category')]:
        for (arm,value),g in test.groupby(['arm',col]):
            segments.append({'dimension':dim,'value':str(value),'arm':arm,**metrics(g)})
    pd.DataFrame(segments).to_csv(out/'july_segments.csv',index=False)
    # Fitted-market volatility bands are descriptive segments; no model selection.
    mt=test[test.arm=='market_only']; edges=mt.vol_per_sqrt_minute.quantile([1/3,2/3]).to_numpy()
    ss=[]
    for arm,g in test.groupby('arm'):
        band=np.digitize(g.vol_per_sqrt_minute,edges)
        for k in range(3):
            q=g[band==k]
            if len(q):ss.append({'market_band':['calm','middle','volatile'][k],'arm':arm,**metrics(q)})
    pd.DataFrame(ss).to_csv(out/'july_market_segments.csv',index=False)
    # Matched event-effect rows make it possible to inspect every changed price.
    base=test[test.arm=='market_only'].set_index('row_id')
    verified=test[test.arm=='verified_research'].set_index('row_id').copy()
    verified['premium_difference']=verified.quoted_premium-base.quoted_premium
    verified['crps_difference']=verified.crps-base.crps
    verified[verified.event_weight>0].reset_index().to_csv(out/'july_event_quote_changes.csv',index=False)
    strict=Events(ROOT/'data/events/recorded_events.jsonl','observed')
    checks={'observed_clock_historical_contexts':sum(strict.context(t,'verified_research') is not None for t in pd.concat([train.createdAt,val.createdAt])),
        'max_probability_mass_error':float(pred.mass_error.max()),
        'all_archive_outcomes_before_cutoff':all(pd.Timestamp(m['last_archive_outcome'])<pd.Timestamp(m['fit_cutoff']) for m in models),
        'validation_no_actual_outcome_columns':not any(c in vp.columns for c in ['closedAt','realizedProfit_USDC','premiumAmount_USDC']),
        'positive_finite_validation_premiums':bool(np.isfinite(vp.quoted_premium).all() and (vp.quoted_premium>0).all())}
    dump(out/'integrity_checks.json',checks)
    files=[ROOT/'docs/EXPERIMENT_PROTOCOL.md',ROOT/'docs/IMPLEMENTATION_DECISIONS.md',Path(args.events or ROOT/'data/events/recorded_events.jsonl')]
    dump(out/'run_manifest.json',{'run_started_utc':pd.Timestamp(started,unit='s',tz='UTC').isoformat(),
        'duration_seconds':round(time.time()-started,2),'clock':args.clock,'seed':417,
        'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,
        'frozen_files':{str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(json.dumps({'policy':policy,'july_verified':summary['test_july']['verified_research'],'paired':boot},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'results'))
    p.add_argument('--clock',choices=['publication_proxy','observed'],default='publication_proxy')
    p.add_argument('--market');p.add_argument('--events')
    run(p.parse_args())
