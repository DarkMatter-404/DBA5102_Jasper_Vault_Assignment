"""Four declared shallow residual trees; a limited nonlinear challenge."""
from pathlib import Path
import json, sys
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))  # code_final: Jay's folder
import pp_pricing as old
OUT=Path(__file__).resolve().parents[2]/'output/v2/research/tree_study';OUT.mkdir(parents=True,exist_ok=True)
SPEC=[(a,l) for a in ['paid','api_base'] for l in ['poisson','squared_error']]
PARAM={'max_iter':60,'learning_rate':.05,'max_leaf_nodes':4,'min_samples_leaf':100,'l2_regularization':20.,'early_stopping':False,'random_state':271828}
FEATURES=['log_tenor','put','log_vol_ratio','signed_momentum_60','log_notional','log_quote_anchor_ratio']
(OUT/'protocol.json').write_text(json.dumps({'specs':SPEC,'params':PARAM,'features':FEATURES,'selection':'April-June equal-fold mean deviance relative to calibrated paid; eligibility mean RMSE relative <=1, max deviance relative<=1.10','July':'Already inspected; retrospective only'},indent=2))
d=pd.read_pickle(OUT.parent/'enriched_features.pkl');d=d[d.analysis_valid&d.base_valid].copy()
d['log_notional']=np.log(d.notional_USDC)
d['log_quote_anchor_ratio']=np.log(d.recorded_bps/d.api_base_bps).clip(0,3)
rows=[];prs=[]
for month in ['2026-04','2026-05','2026-06','2026-07']:
 start=pd.Timestamp(month+'-01',tz='UTC');end=start+pd.offsets.MonthBegin(1)
 tr=d[(d.createdAt<start)&(d.closedAt<start)]
 te=d[(d.createdAt>=start)&(d.createdAt<end)]
 if month!='2026-07':te=te[te.closedAt<end]
 ratio=tr.realizedProfit_USDC.sum()/tr.premiumAmount_USDC.sum()
 rows.append(dict(month=month,model='calibrated_paid',**old.metrics(te,te.premiumAmount_USDC.to_numpy()*ratio)))
 for a,loss in SPEC:
  col='premiumAmount_USDC' if a=='paid' else 'api_base_USDC'
  b=tr[col].to_numpy();y=tr.realizedProfit_USDC.to_numpy()/b
  model=HistGradientBoostingRegressor(loss=loss,**PARAM).fit(tr[FEATURES],y,sample_weight=b/b.mean())
  train_c=np.maximum(model.predict(tr[FEATURES]),1e-6)*b
  scale=tr.realizedProfit_USDC.sum()/train_c.sum()
  c=np.maximum(model.predict(te[FEATURES]),1e-6)*te[col].to_numpy()*scale
  name=a+'_'+loss
  rows.append(dict(month=month,model=name,**old.metrics(te,c)))
  pp=te[['source_row','month','day','productType','premiumAmount_USDC','realizedProfit_USDC']].copy();pp['model']=name;pp['expected_payout']=c;prs.append(pp)
r=pd.DataFrame(rows);r.to_csv(OUT/'metrics.csv',index=False)
pd.concat(prs).to_csv(OUT/'predictions.csv',index=False)
ref=r[r.model.eq('calibrated_paid')].set_index('month')
for k in ['notional_weighted_poisson_deviance','RMSE_USDC']:r[k+'_relative']=r[k]/r.month.map(ref[k])
sel=r[r.month.ne('2026-07')].groupby('model').agg(mean_dev=('notional_weighted_poisson_deviance_relative','mean'),max_dev=('notional_weighted_poisson_deviance_relative','max'),mean_rmse=('RMSE_USDC_relative','mean')).sort_values('mean_dev')
sel['eligible']=(sel.mean_rmse<=1)&(sel.max_dev<=1.1);sel.to_csv(OUT/'selection.csv')
print(sel.to_string());print(r[r.month.eq('2026-07')][['model','RMSE_USDC','calibration_ratio_predicted_to_actual','notional_weighted_poisson_deviance']].to_string(index=False))
