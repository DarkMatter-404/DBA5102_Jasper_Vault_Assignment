#!/usr/bin/env python3
"""Diagnostics for declared candidates; no candidate reselection on July."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import study

OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'  # code_final: Jay's folder
OUT.mkdir(parents=True,exist_ok=True)
models=json.loads((OUT/'fitted_models.json').read_text())
data=study.pp.features(study.ROOT/'data/en/pp_transactions_training.csv',study.pp.read_market(study.ROOT/'data/en/btc_market_history.csv'))
train=study.pp.train_before(data,'2026-07-01')
test=data[data.analysis_valid & data.month.eq('2026-07')].copy()
base=study.predict(models['2026-07_baseline'],test)
rng=np.random.default_rng(271828)
boot=[]; scenarios=[]
for name in ['tenor200','tenor500','recency60','state_no_side_ridge100']:
    model=models['2026-07_'+name]
    # JSON object keys must be integers for mapping productType.
    if 'tenor_ratios' in model:model['tenor_ratios']={int(k):v for k,v in model['tenor_ratios'].items()}
    pred=study.predict(model,test)
    frame=test[['day','realizedProfit_USDC']].copy()
    frame['base_sse']=(base-test.realizedProfit_USDC.to_numpy())**2
    frame['candidate_sse']=(pred-test.realizedProfit_USDC.to_numpy())**2
    frame['n']=1
    day=frame.groupby('day')[['base_sse','candidate_sse','n']].sum()
    draws=[]
    for i in range(2000):
        d=day.iloc[rng.integers(0,len(day),len(day))].sum()
        draws.append(float(np.sqrt(d.candidate_sse/d.n)-np.sqrt(d.base_sse/d.n)))
    boot.append({'model':name,'RMSE_diff':float(np.sqrt(frame.candidate_sse.mean())-np.sqrt(frame.base_sse.mean())),
        'conditional_day_bootstrap_95pct':np.quantile(draws,[.025,.975]).tolist()})
    kappa=model['global_ratio']; trref=train.premiumAmount_USDC.to_numpy()
    trrisk=study.predict(model,train); score=np.sqrt(trrisk/(kappa*trref))
    normalizer=brentq(lambda c:np.sum(trref*np.clip(c*score,.85,1.15))-trref.sum(),.0001,1000)
    mult=np.clip(normalizer*np.sqrt(pred/(kappa*test.premiumAmount_USDC.to_numpy())),.85,1.15)
    for e in [0,1,2,4]:
        retained=np.minimum(1,mult**-e)
        scenarios.append({'model':name,'assumed_elasticity':e,'mean_multiplier':float(mult.mean()),
            'premium_weighted_multiplier':float(np.sum(mult*test.premiumAmount_USDC)/test.premiumAmount_USDC.sum()),
            'retained_orders_share':float(retained.mean()),
            'scenario_gross_margin_USDC':float(np.sum(retained*(mult*test.premiumAmount_USDC-test.realizedProfit_USDC))),
            'historic_gross_margin_USDC':float(np.sum(test.premiumAmount_USDC-test.realizedProfit_USDC))})
    detail=test[['source_row','createdAt','day','productType','optionType','premiumAmount_USDC','realizedProfit_USDC']].copy()
    detail['cost_prediction']=pred;detail['candidate_multiplier']=mult
    detail.to_csv(OUT/f'july_{name}_quotes.csv',index=False)
(OUT/'conditional_day_bootstrap.json').write_text(json.dumps(boot,indent=2))
pd.DataFrame(scenarios).to_csv(OUT/'unchanged_pricing_layer_scenarios.csv',index=False)
print(json.dumps(boot,indent=2));print(pd.DataFrame(scenarios).to_string(index=False))
