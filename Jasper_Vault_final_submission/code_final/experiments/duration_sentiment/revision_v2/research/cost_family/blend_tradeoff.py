#!/usr/bin/env python3
"""Fixed blend-grid tradeoff; no retrospective July optimization.

Development rule: each April-June fold retains >=95% of historical order count
under assumed elasticity four. Among feasible weights, maximize summed
April-June gross margin at elasticity four. All four weights are reported.
Same-retention uniform is diagnostic and uses evaluation quote mix, not outcomes.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from budget_neutral_study import lower_tail_mean, paired_bootstrap

OUT=Path(__file__).resolve().parents[3]/'output/v2/research/cost_family'  # code_final: Jay's folder
OUT.mkdir(parents=True,exist_ok=True)


def main():
    q=pd.read_csv(OUT/'budget_neutral_quotes.csv')
    # Recover the exact prior monthly label boundaries used in the study.
    old=pd.read_csv(OUT/'all_predictions.csv')
    allowed=old[old.model.eq('baseline')][['source_row','period']]
    q=q.merge(allowed,on=['source_row','period'],validate='one_to_one')
    rows=[]; dailyrows=[]; bootstrap=[]; rng=np.random.default_rng(271828)
    for period,g in q.groupby('period'):
        ref=g.premiumAmount_USDC.to_numpy(float); y=g.realizedProfit_USDC.to_numpy(float)
        raw=g.train_normalized_multiplier.to_numpy(float)
        for w in [0,.25,.5,1]:
            mult=1+w*(raw-1)
            for e in [0,1,2,4]:
                r=np.minimum(1,mult**-e)
                retained=float(r.mean())
                policies={'tenor200_blend':(mult,r), 'recorded':(np.ones(len(g)),np.ones(len(g)))}
                if e>0:
                    u=retained**(-1/e)
                    policies['uniform_same_order_retention']=(np.full(len(g),u),np.full(len(g),retained))
                daily={}
                for policy,(m,retention) in policies.items():
                    premium=retention*m*ref;payout=retention*y;margin=premium-payout
                    byday=pd.DataFrame({'day':g.day,'margin':margin}).groupby('day').margin.sum().sort_index()
                    daily[policy]=byday.to_numpy(float)
                    rows.append({'period':period,'weight':w,'elasticity':e,'policy':policy,
                        'n':len(g),'mean_multiplier':float(np.mean(m)),
                        'premium_weighted_multiplier':float(np.sum(ref*m)/np.sum(ref)),
                        'retained_order_share':float(np.mean(retention)),
                        'scenario_gross_margin_USDC':float(margin.sum()),'scenario_premium_USDC':float(premium.sum()),
                        'scenario_payout_USDC':float(payout.sum()),
                        'worst_creation_cohort_margin_USDC':float(byday.min()),
                        'lower20pct_creation_cohort_mean_USDC':lower_tail_mean(byday)})
                    dr=byday.reset_index();dr['period']=period;dr['weight']=w;dr['elasticity']=e;dr['policy']=policy
                    dailyrows.append(dr)
                if period=='2026-07' and w>0:
                    for comparator in ['recorded','uniform_same_order_retention']:
                        if comparator in daily:
                            result=paired_bootstrap(daily['tenor200_blend'],daily[comparator],rng)
                            bootstrap.append({'period':period,'weight':w,'elasticity':e,'comparator':comparator,**result})
    result=pd.DataFrame(rows);result.to_csv(OUT/'blend_retention_tradeoff.csv',index=False)
    pd.concat(dailyrows,ignore_index=True).to_csv(OUT/'blend_retention_daily.csv',index=False)
    (OUT/'blend_retention_bootstrap.json').write_text(json.dumps(bootstrap,indent=2))
    dev=result[result.period.ne('2026-07') & result.elasticity.eq(4) & result.policy.eq('tenor200_blend')]
    selection=dev.groupby('weight').agg(min_month_retention=('retained_order_share','min'),
        total_scenario_gross_margin_USDC=('scenario_gross_margin_USDC','sum'))
    selection['feasible']=selection.min_month_retention>=.95
    selected=float(selection[selection.feasible].sort_values('total_scenario_gross_margin_USDC',ascending=False).index[0])
    selection.to_csv(OUT/'blend_development_selection.csv')
    (OUT/'blend_selection_rule.json').write_text(json.dumps({
        'weights':[0,.25,.5,1], 'retention_constraint':'Each April-June development month retains at least95% of historical order count under assumed e=4.',
        'objective':'Maximize sum of April-June scenario gross margins at assumed e=4 among feasible weights.',
        'selected_weight':selected, 'limitations':'Proposed commercial assumption; e is not estimated. July retrospective only. Never pick another weight from July outcomes.'},indent=2))
    print('DEVELOPMENT SELECTION\n',selection.to_string())
    print('\nDEVELOPMENT EACH FOLD e4\n',dev[['period','weight','retained_order_share','scenario_gross_margin_USDC']].to_string(index=False))
    print('\nJULY e4\n',result[result.period.eq('2026-07') & result.elasticity.eq(4)].to_string(index=False))
    print('\nSelected:',selected)


if __name__=='__main__':main()
