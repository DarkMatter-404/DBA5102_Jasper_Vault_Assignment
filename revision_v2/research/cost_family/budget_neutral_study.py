#!/usr/bin/env python3
"""Declared tenor200 pricing diagnostics, without July-driven policy tuning.

Day-batch neutral is an explanatory batch allocation, not a usable sequential
quote engine: future orders on the same day are unavailable at the first quote.
All quote-valid orders enter the normalizer, regardless of outcome availability.
Uniform same-volume-revenue uses evaluation-period quote premiums, not payouts.
Elasticities are scenarios among historical buyers, not estimated demand.
"""
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import study

OUT=Path(__file__).resolve().parents[4]/'jay/output/v2/research/cost_family'
OUT.mkdir(parents=True,exist_ok=True)
SEED=271828
N_BOOT=2000


def normalizer(ref, score):
    return brentq(lambda c:np.sum(ref*np.clip(c*score,.85,1.15))-ref.sum(),.0001,1000)


def quote_batch_adjustment(quote_inputs):
    """Input has only source_row/day/reference/risk-score; no realized labels."""
    out=[]
    for day,q in quote_inputs.groupby('day'):
        ref=q.reference.to_numpy(float); score=q.score.to_numpy(float)
        c=normalizer(ref,score)
        p=q[['source_row','day']].copy()
        p['day_batch_neutral_multiplier']=np.clip(c*score,.85,1.15)
        p['day_normalizer']=c
        out.append(p)
    return pd.concat(out,ignore_index=True)


def lower_tail_mean(values, fraction=.2):
    values=np.sort(np.asarray(values,float)); mass=len(values)*fraction
    full=int(np.floor(mass)); partial=mass-full
    total=values[:full].sum()
    if partial>1e-12:total+=partial*values[full]
    return float(total/mass)


def paired_bootstrap(proposed, comparator, rng):
    # Daily arrays have equal, aligned quote-creation dates. We condition on
    # already fitted pricing policies and assumed retention, not on actual A/B.
    differences=[]
    for _ in range(N_BOOT):
        draw=rng.integers(0,len(proposed),len(proposed))
        p,c=proposed[draw],comparator[draw]
        differences.append([p.sum()-c.sum(),p.min()-c.min(),lower_tail_mean(p)-lower_tail_mean(c)])
    d=np.asarray(differences)
    return {
        'gross_margin_difference_USDC':float(proposed.sum()-comparator.sum()),
        'gross_margin_difference_95pct_USDC':np.quantile(d[:,0],[.025,.975]).tolist(),
        'worst_cohort_difference_USDC':float(proposed.min()-comparator.min()),
        'worst_cohort_difference_95pct_USDC':np.quantile(d[:,1],[.025,.975]).tolist(),
        'lower_20pct_cohort_mean_difference_USDC':lower_tail_mean(proposed)-lower_tail_mean(comparator),
        'lower_20pct_cohort_mean_difference_95pct_USDC':np.quantile(d[:,2],[.025,.975]).tolist(),
    }


def main():
    models=json.loads((OUT/'fitted_models.json').read_text())
    data=study.pp.features(study.ROOT/'data/en/pp_transactions_training.csv',study.pp.read_market(study.ROOT/'data/en/btc_market_history.csv'))
    results=[]; audit=[]; boot=[]; alldaily=[]; allquotes=[]
    rng=np.random.default_rng(SEED)
    for month in ['2026-04','2026-05','2026-06','2026-07']:
        start=pd.Timestamp(month+'-01',tz='UTC'); end=start+pd.offsets.MonthBegin(1)
        train=study.pp.train_before(data,start)
        full=data[data.quote_valid & data.createdAt.ge(start) & data.createdAt.lt(end)].copy()
        test=full[full.label_valid].copy()
        if month!='2026-07':test=test[test.closedAt.lt(end)]
        model=models[month+'_tenor200']
        model['tenor_ratios']={int(k):v for k,v in model['tenor_ratios'].items()}
        trref=train.premiumAmount_USDC.to_numpy(float)
        train_score=np.sqrt(study.predict(model,train)/(model['global_ratio']*trref))
        c=normalizer(trref,train_score)
        fullref=full.premiumAmount_USDC.to_numpy(float)
        fullscore=np.sqrt(study.predict(model,full)/(model['global_ratio']*fullref))
        frozenmult=np.clip(c*fullscore,.85,1.15)
        q=pd.DataFrame({'source_row':full.source_row,'day':full.day,'reference':fullref,'score':fullscore})
        adjusted=quote_batch_adjustment(q)
        full=full.merge(adjusted,on=['source_row','day'],validate='one_to_one')
        full['train_normalized_multiplier']=frozenmult
        uniform_ratio=float(np.sum(frozenmult*fullref)/fullref.sum())
        # Use the full quote cohort consistently: some quote-valid orders have
        # missing or invalid labels and must still enter a quote-only normalizer.
        full['uniform_same_revenue_multiplier']=uniform_ratio
        full['recorded_multiplier']=1.
        evalrows=test[['source_row']].merge(full,on='source_row',validate='one_to_one')
        cols=['source_row','createdAt','day','productType','premiumAmount_USDC','realizedProfit_USDC',
              'train_normalized_multiplier','uniform_same_revenue_multiplier','day_batch_neutral_multiplier']
        detail=full[cols].copy();detail['period']=month;allquotes.append(detail)
        neutral_total=float(np.sum(fullref*full.day_batch_neutral_multiplier))
        daily_neutral_errors=(full.assign(delta=full.premiumAmount_USDC*(full.day_batch_neutral_multiplier-1)).groupby('day').delta.sum())
        audit.append({'period':month,'train_n':len(train),'quote_valid_n':len(full),'evaluated_labels_n':len(evalrows),
            'quote_reference_premiums_USDC':float(fullref.sum()),
            'day_batch_neutral_premiums_USDC':neutral_total,
            'max_abs_daily_budget_error_USDC':float(daily_neutral_errors.abs().max()),
            'uniform_same_revenue_multiplier_full_quote_cohort':uniform_ratio,
            'frozen_train_normalizer':c})
        perioddaily={}
        for e in [0,1,2,4]:
            for policy in ['recorded','train_normalized','uniform_same_revenue','day_batch_neutral']:
                m=evalrows[policy+'_multiplier'].to_numpy(float)
                ref=evalrows.premiumAmount_USDC.to_numpy(float); y=evalrows.realizedProfit_USDC.to_numpy(float)
                retention=np.minimum(1,m**-e)
                revenue=retention*m*ref; payout=retention*y; margin=revenue-payout
                d=pd.DataFrame({'day':evalrows.day,'revenue':revenue,'payout':payout,'margin':margin,'retained_orders':retention})
                d=d.groupby('day').sum().sort_index()
                perioddaily[(e,policy)]=d.margin.to_numpy(float)
                d['period']=month;d['assumed_elasticity']=e;d['policy']=policy;alldaily.append(d.reset_index())
                results.append({'period':month,'role':'retrospective_July' if month=='2026-07' else 'cross_fitted_development',
                    'policy':policy,'assumed_elasticity':e,'n_orders':len(evalrows),
                    'mean_multiplier':float(m.mean()),'premium_weighted_multiplier':float(np.sum(m*ref)/ref.sum()),
                    'assumed_retained_order_share':float(retention.mean()),
                    'scenario_premium_USDC':float(revenue.sum()),'scenario_payout_USDC':float(payout.sum()),
                    'scenario_gross_margin_USDC':float(margin.sum()),'worst_creation_cohort_margin_USDC':float(d.margin.min()),
                    'lower_20pct_creation_cohort_mean_USDC':lower_tail_mean(d.margin),
                    'loss_creation_cohorts':int((d.margin<0).sum()),'creation_cohorts':len(d)})
        for e in [0,1,2,4]:
            for proposed in ['train_normalized','day_batch_neutral']:
                for comparator in ['recorded','uniform_same_revenue']:
                    result=paired_bootstrap(perioddaily[(e,proposed)],perioddaily[(e,comparator)],rng)
                    boot.append({'period':month,'proposed':proposed,'comparator':comparator,'assumed_elasticity':e,**result})
    result=pd.DataFrame(results);result.to_csv(OUT/'budget_neutral_metrics.csv',index=False)
    pd.concat(alldaily,ignore_index=True).to_csv(OUT/'budget_neutral_daily.csv',index=False)
    pd.concat(allquotes,ignore_index=True).to_csv(OUT/'budget_neutral_quotes.csv',index=False)
    (OUT/'budget_neutral_audit.json').write_text(json.dumps(audit,indent=2))
    (OUT/'budget_neutral_bootstrap.json').write_text(json.dumps({'seed':SEED,'resamples':N_BOOT,
        'method':'Paired UTC order-creation day resamples; conditional on frozen model, quotes and retention scenario. Bounds do not include policy selection or demand identification uncertainty.',
        'lower_tail_definition':'Average of worst 20% of daily gross margins, with fractional weight on the boundary day.',
        'results':boot},indent=2))
    print(result[result.period.eq('2026-07')].to_string(index=False))
    print('\nDEVELOPMENT GROSS MARGIN')
    print(result[result.period.ne('2026-07')].pivot(index=['period','assumed_elasticity'],columns='policy',values='scenario_gross_margin_USDC').to_string())
    print('\nAUDIT',json.dumps(audit,indent=2))


if __name__=='__main__':main()
