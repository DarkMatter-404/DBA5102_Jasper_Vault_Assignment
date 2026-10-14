"""Declared cost-plus pricing grid; explicit conversion assumptions, no causal claims."""
from pathlib import Path
import json
import numpy as np,pandas as pd
OUT=Path(__file__).resolve().parents[3]/'jay/output/v2/research/decision_study';OUT.mkdir(parents=True,exist_ok=True)
RULE={'cost_model':'base_prior200, selected only on April-June cost deviance','target_loss_ratios':[.85,.90,.95],'weights':[0,.25,.5,1.],'full_adjustment_caps':[.90,1.10],'conversion_elasticities':[0,1,2,4],'selection':'Max min-e April-June aggregate gross-margin gain, e=1,2,4; each-month e4 order retention>=95%; each-month aggregate quote premium increase<=2%; at least10% of development quotes discounted for nonzero policies. Ties choose zero then smaller weight.','disclosure':'All rules/design assumptions declared before this grid evaluation. July is retrospective already inspected. Homogeneous retention with unchanged conditional payouts is an assumption, not estimated demand.'}
(OUT/'protocol.json').write_text(json.dumps(RULE,indent=2))
d=pd.read_csv(OUT.parent/'base_study/predictions.csv');d=d[d.model.eq('base_prior200')].copy()
rows=[];pred=[]
for lr in RULE['target_loss_ratios']:
 for w in RULE['weights']:
  if w==0 and lr!=.85:continue
  policy='unchanged' if w==0 else f'costplus_lr{lr}_w{w}'
  for month,g in d.groupby('month'):
   b=g.premiumAmount_USDC.to_numpy();y=g.realizedProfit_USDC.to_numpy();c=g.expected_payout.to_numpy()
   pure=np.clip(c/lr,.9*b,1.1*b);p=b+w*(pure-b);m=p/b;uniform=p.sum()/b.sum()
   pp=g.copy();pp['policy']=policy;pp['premium']=p;pred.append(pp)
   for e in RULE['conversion_elasticities']:
    q=np.minimum(1,m**(-e));ret=q.mean();gm=np.sum(q*(p-y));base=np.sum(b-y)
    same_rev_q=min(1,uniform**(-e));same_rev_gm=same_rev_q*(uniform*b.sum()-y.sum())
    u=1 if e==0 else ret**(-1/e)
    same_ret_gm=ret*(u*b.sum()-y.sum())
    rows.append({'policy':policy,'lr':lr,'w':w,'month':month,'e':e,'n':len(g),'retention':ret,'baseline_premium':b.sum(),'premium_sum':p.sum(),'quoted_premium_change':uniform-1,'discount_share':np.mean(m<1-1e-10),'gross_margin':gm,'baseline_gross_margin':base,'gain':gm-base,'equal_revenue_uniform_gm':same_rev_gm,'same_retention_uniform_multiplier':u,'same_retention_uniform_gm':same_ret_gm,'gain_vs_same_retention_uniform':gm-same_ret_gm})
r=pd.DataFrame(rows);r.to_csv(OUT/'scenarios.csv',index=False);pd.concat(pred).to_csv(OUT/'quotes.csv',index=False)
dev=r[(r.month!='2026-07')&(r.e>0)]
sel=[]
for name,g in dev.groupby('policy'):
 eligible=(g[g.e==4].retention.min()>=.95-1e-10 and g.quoted_premium_change.max()<=.02+1e-10 and (name=='unchanged' or g.drop_duplicates('month').discount_share.mean()>=.10))
 sel.append({'policy':name,'eligible':eligible,'worst_scenario_total_gain':g.groupby('e').gain.sum().min(),'min_month_retention_e4':g[g.e==4].retention.min(),'max_month_premium_increase':g.quoted_premium_change.max(),'mean_discount_share':g.drop_duplicates('month').discount_share.mean(),'w':g.w.iloc[0]})
s=pd.DataFrame(sel).sort_values(['eligible','worst_scenario_total_gain','w'],ascending=[False,False,True]);s.to_csv(OUT/'selection.csv',index=False)
chosen=s[s.eligible].iloc[0].policy
(OUT/'selected.json').write_text(json.dumps({'policy':chosen,'protocol':RULE},indent=2))
print(s.to_string(index=False))
print(r[(r.policy==chosen)&(r.month=='2026-07')].to_string(index=False))
