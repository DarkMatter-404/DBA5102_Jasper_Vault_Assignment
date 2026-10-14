"""Exploratory API-base study. July is a previously inspected retrospective test."""
from pathlib import Path
import json, sys
import numpy as np
import pandas as pd
from scipy.optimize import brentq
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'jay'))
import pp_pricing as old

OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/base_study'
OUT.mkdir(parents=True,exist_ok=True)
SPECS=[{'anchor':a,'prior':k} for a in ['base','blend','paid'] for k in [0,200,1000]]
# Fixed before evaluating these candidates: nine coarse credibility models.
PROTOCOL={'family':SPECS,'development_months':['2026-04','2026-05','2026-06'],'score':'Mean fold weighted-Poisson deviance divided by calibrated-paid benchmark; one winner frozen before July report','july_status':'Retrospective re-evaluation; July already inspected in prior model study','base_semantics':'Order-sized API amount (quantity times API quote); requires PP conversion/timestamp confirmation','pricing':'Predefined multipliers 0.90-1.10; train-price-neutral normalizer; eta 0.5; all scenarios shown, not conversion estimates'}
(OUT/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2))

def name(spec):return spec['anchor']+'_prior'+str(spec['prior'])
def fit(d,spec):
 y=d.realizedProfit_USDC.to_numpy();b=d.api_base_USDC.to_numpy();p=d.premiumAmount_USDC.to_numpy()
 kb=y.sum()/b.sum();kp=y.sum()/p.sum()
 mix={'base':0.,'blend':.5,'paid':1.}[spec['anchor']]
 a=mix*kp*p+(1-mix)*kb*b
 pooled=y.sum()/a.sum()
 rates={}
 for tenor in [1800,3600,7200,14400,28800,43200,86400]:
  mask=d.productType.to_numpy()==tenor
  exposure=a[mask].sum()
  if spec['prior']==0 or not mask.any():rates[str(tenor)]=pooled
  else:
   prior=spec['prior']*np.mean(a)
   rates[str(tenor)]=(y[mask].sum()+prior*pooled)/(exposure+prior)
 # Exact total calibration on the fit sample after partial pooling.
 corr=np.array([rates[str(t)] for t in d.productType])*a
 scale=y.sum()/corr.sum()
 return {**spec,'mix':mix,'kb':kb,'kp':kp,'rates':rates,'scale':scale,'n':len(d)}
def predict(m,d):
 a=m['mix']*m['kp']*d.premiumAmount_USDC.to_numpy()+(1-m['mix'])*m['kb']*d.api_base_USDC.to_numpy()
 return a*np.array([m['rates'].get(str(t),1.) for t in d.productType])*m['scale']
def price(m,tr,te):
 p=tr.premiumAmount_USDC.to_numpy();c=predict(m,tr);r=c/(m['kp']*p)
 f=lambda z: np.sum(p*np.clip(z*np.sqrt(r),.9,1.1))-p.sum()
 normal=brentq(f,.00001,100)
 pt=te.premiumAmount_USDC.to_numpy();ct=predict(m,te)
 return pt*np.clip(normal*np.sqrt(ct/(m['kp']*pt)),.9,1.1),normal
def commercial(d,pred,pname):
 b=d.premiumAmount_USDC.to_numpy();y=d.realizedProfit_USDC.to_numpy();m=pred/b
 uniform=pred.sum()/b.sum()
 rows=[]
 for e in [0,1,2,4]:
  for policy,mult in [(pname,m),('equal_average_uniform',np.repeat(uniform,len(m))),('paid_reference',np.ones(len(m)))]:
   r=np.minimum(1,mult**(-e))
   rows.append({'policy':policy,'elasticity':e,'retention':r.mean(),'premium_total_unthinned':float((b*mult).sum()),'gross_margin':float(np.sum(r*(b*mult-y))),'retained_payout':float(np.sum(r*y)),'share_discount':float(np.mean(mult<1-1e-10))})
 return rows

d=pd.read_pickle(OUT.parent/'enriched_features.pkl')
d=d[d.analysis_valid&d.base_valid].copy()
rows=[];predrows=[];fitmodels={};decisions=[]
for month in PROTOCOL['development_months']+['2026-07']:
 start=pd.Timestamp(month+'-01',tz='UTC');end=start+pd.offsets.MonthBegin(1)
 tr=d[(d.createdAt<start)&(d.closedAt<start)]
 te=d[(d.createdAt>=start)&(d.createdAt<end)]
 if month!='2026-07':te=te[te.closedAt<end]
 for spec in SPECS:
  mod=fit(tr,spec);pr=predict(mod,te);met=old.metrics(te,pr)
  rows.append({'month':month,'model':name(spec),'train_n':len(tr),**met})
  tmp=te[['source_row','month','productType','optionType','premiumAmount_USDC','api_base_USDC','realizedProfit_USDC']].copy();tmp['model']=name(spec);tmp['expected_payout']=pr
  premium,normal=price(mod,tr,te);tmp['candidate_premium']=premium;predrows.append(tmp)
  fitmodels[month+'_'+name(spec)]={**mod,'price_normalizer':normal}
  if month=='2026-07':
   decisions.extend([dict(month=month,model=name(spec),**r) for r in commercial(te,premium,name(spec))])
 if month!='2026-07':continue
 dev=pd.DataFrame(rows);dev=dev[dev.month.ne('2026-07')]
 ref=dev[dev.model.eq('paid_prior0')].set_index('month')
 for col in ['RMSE_USDC','notional_weighted_poisson_deviance']:
  dev[col+'_relative']=dev[col]/dev.month.map(ref[col])
 selection=dev.groupby('model').agg(mean_deviance_relative=('notional_weighted_poisson_deviance_relative','mean'),mean_rmse_relative=('RMSE_USDC_relative','mean')).sort_values('mean_deviance_relative')
 selection.to_csv(OUT/'selection.csv')
 selected=selection.index[0]
 (OUT/'selected.json').write_text(json.dumps({'selected':selected,'protocol':PROTOCOL},indent=2))
pd.DataFrame(rows).to_csv(OUT/'metrics.csv',index=False)
pd.concat(predrows).to_csv(OUT/'predictions.csv',index=False)
pd.DataFrame(decisions).to_csv(OUT/'july_commercial_all.csv',index=False)
(OUT/'fitted_models.json').write_text(json.dumps(fitmodels,indent=2))
print(selection.to_string())
res=pd.DataFrame(rows)
print(res[res.month.eq('2026-07')][['model','RMSE_USDC','calibration_ratio_predicted_to_actual','notional_weighted_poisson_deviance']].to_string(index=False))
print(pd.DataFrame(decisions).query('model==@selected').to_string(index=False))
