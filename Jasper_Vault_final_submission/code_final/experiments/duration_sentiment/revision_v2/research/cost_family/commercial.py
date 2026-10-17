#!/usr/bin/env python3
"""Cost-aware reallocation versus same-volume uniform pricing decomposition.

Matched-revenue uniform prices use the evaluation cohort average, so they are a
diagnostic decomposition, NOT a deployable pre-frozen alternative.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import study

OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'
OUT.mkdir(parents=True,exist_ok=True)
models=json.loads((OUT/'fitted_models.json').read_text())
data=study.pp.features(study.ROOT/'data/en/pp_transactions_training.csv',study.pp.read_market(study.ROOT/'data/en/btc_market_history.csv'))
rows=[]
for month in ['2026-04','2026-05','2026-06','2026-07']:
    start=pd.Timestamp(month+'-01',tz='UTC'); end=start+pd.offsets.MonthBegin(1)
    train=study.pp.train_before(data,start)
    test=data[data.analysis_valid & data.createdAt.ge(start) & data.createdAt.lt(end)].copy()
    if month!='2026-07':test=test[test.closedAt.lt(end)]
    for name in ['tenor200','tenor500','state_no_side_ridge100']:
        model=models[month+'_'+name]
        if 'tenor_ratios' in model:model['tenor_ratios']={int(k):v for k,v in model['tenor_ratios'].items()}
        pred=study.predict(model,test)
        trref=train.premiumAmount_USDC.to_numpy(); ref=test.premiumAmount_USDC.to_numpy(); y=test.realizedProfit_USDC.to_numpy()
        score=np.sqrt(study.predict(model,train)/(model['global_ratio']*trref))
        c=brentq(lambda c:np.sum(trref*np.clip(c*score,.85,1.15))-trref.sum(),.0001,1000)
        mult=np.clip(c*np.sqrt(pred/(model['global_ratio']*ref)),.85,1.15)
        avg=np.sum(mult*ref)/ref.sum()
        historic=float(np.sum(ref-y))
        for pricing,m in [('tenor_or_state',mult),('same_fixed_volume_revenue_uniform',np.full(len(test),avg))]:
            for e in [0,1,2,4]:
                retained=np.minimum(1,m**-e)
                gross=float(np.sum(retained*(m*ref-y)))
                rows.append({'period':month,'model':name,'pricing':pricing,'assumed_elasticity':e,
                    'mean_multiplier':float(m.mean()),'premium_weighted_multiplier':avg,
                    'retained_order_share':float(retained.mean()),'scenario_gross_margin_USDC':gross,
                    'historic_gross_margin_USDC':historic,'gross_improvement_USDC':gross-historic})
out=pd.DataFrame(rows);out.to_csv(OUT/'all_fold_commercial_decomposition.csv',index=False)
print(out[(out.model.eq('tenor200')) & out.assumed_elasticity.isin([0,2,4])].to_string(index=False))
