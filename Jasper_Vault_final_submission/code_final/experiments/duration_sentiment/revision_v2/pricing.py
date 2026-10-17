#!/usr/bin/env python3
"""Jasper PP research v2: duration credibility with an analytic price bound.

This is an offline, recorded-premium-anchored assignment candidate. Retention is
an assumed scenario, not estimated demand; July has already been inspected.
The actual API-base experiment is reported separately on its matched population.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq

JAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(JAY))
import pp_pricing as v1

SEED = 271828
TENORS = [1800, 3600, 7200, 14400, 28800, 43200, 86400]


def write_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')


def analytic_weight(rho=.95, emax=4., upper=1.15):
    """For q(m)=min(1,m^-e), guarantee q>=rho if 0<=e<=emax.

    This is a mathematical scenario bound only, never a claim about actual demand.
    """
    if not (0 < rho <= 1 and np.isfinite(rho) and emax > 0 and np.isfinite(emax)
            and upper > 1 and np.isfinite(upper)):
        raise ValueError('Require 0 < rho <= 1, emax > 0 and raw upper > 1.')
    return float(min(1., (rho**(-1./emax)-1.)/(upper-1.)))


def validate_model(model):
    if model.get('schema') != 'jasper-pp-duration-credibility-v2':
        raise ValueError('Unsupported v2 model schema')
    p = model['pricing']
    if not (0 < p['raw_lower'] <= 1 < p['raw_upper']):
        raise ValueError('Invalid multiplier bounds')
    expected = analytic_weight(p['assumed_min_retention'], p['assumed_max_elasticity'], p['raw_upper'])
    if not np.isclose(p['weight'], expected, rtol=1e-12, atol=1e-12):
        raise ValueError('Stored weight does not satisfy the declared analytic rule')
    vals = [model['pooled_payout_to_premium'], p['train_normalizer'], *model['tenor_ratios'].values()]
    if not np.isfinite(vals).all() or min(vals) <= 0:
        raise ValueError('Model ratios and normalizer must be positive finite values')
    if model.get('reference_kind') != 'recorded_premium_proxy':
        raise ValueError('This candidate requires the explicit recorded-premium reference')


def cost(model, frame):
    ratios = frame.productType.map(lambda t: model['tenor_ratios'].get(str(int(t)), model['pooled_payout_to_premium'])).to_numpy(float)
    return frame.premiumAmount_USDC.to_numpy(float)*ratios


def multiplier(model, frame):
    validate_model(model)
    p = model['pricing']
    ratios = frame.productType.map(lambda t: model['tenor_ratios'].get(str(int(t)), model['pooled_payout_to_premium'])).to_numpy(float)
    raw = np.clip(p['train_normalizer']*np.sqrt(ratios/model['pooled_payout_to_premium']), p['raw_lower'], p['raw_upper'])
    return 1+p['weight']*(raw-1)


def fit(frame, cutoff, prior_order_equivalents=200., rho=.95, emax=4.):
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None: cutoff = cutoff.tz_localize('UTC')
    else: cutoff = cutoff.tz_convert('UTC')
    tr = frame[frame.analysis_valid & frame.createdAt.lt(cutoff) & frame.closedAt.lt(cutoff)].copy()
    if len(tr) == 0 or tr.realizedProfit_USDC.sum() <= 0:
        raise ValueError('Need eligible settled labels with positive aggregate payouts before cutoff')
    if not np.isfinite(prior_order_equivalents) or prior_order_equivalents <= 0:
        raise ValueError('Prior order equivalents must be positive and finite')
    r0 = float(tr.realizedProfit_USDC.sum()/tr.premiumAmount_USDC.sum())
    h = float(prior_order_equivalents*tr.premiumAmount_USDC.mean())
    grouped = tr.groupby('productType').agg(premium=('premiumAmount_USDC','sum'), payout=('realizedProfit_USDC','sum'), n=('source_row','size'))
    ratios = {str(t): float((grouped.loc[t,'payout']+h*r0)/(grouped.loc[t,'premium']+h)) if t in grouped.index else r0 for t in TENORS}
    m = {'schema':'jasper-pp-duration-credibility-v2', 'reference_kind':'recorded_premium_proxy',
         'model_status':'research_candidate_not_approved_for_live_deployment',
         'pooled_payout_to_premium':r0, 'prior_order_equivalents':float(prior_order_equivalents),
         'prior_premium_exposure_USDC':h, 'tenor_ratios':ratios,
         'training_rows':len(tr), 'cutoff_utc':str(cutoff),
         'latest_training_creation':str(tr.createdAt.max()), 'latest_training_settlement':str(tr.closedAt.max()),
         'feature_clock':'createdAt', 'max_timestamp_gap_seconds':120,
         'pricing':{'raw_lower':.85,'raw_upper':1.15,'assumed_max_elasticity':float(emax),
                    'assumed_min_retention':float(rho),'weight':analytic_weight(rho,emax,1.15)}}
    b = tr.premiumAmount_USDC.to_numpy(float)
    score = np.sqrt(cost(m,tr)/(r0*b))
    c = brentq(lambda x: np.sum(b*np.clip(x*score,.85,1.15))-b.sum(), .0001, 1000.)
    m['pricing']['train_normalizer'] = float(c)
    m['pricing']['minimum_multiplier'] = float(1+m['pricing']['weight']*(.85-1))
    m['pricing']['maximum_multiplier'] = float(1+m['pricing']['weight']*(1.15-1))
    m['assumptions'] = [
        'Reference must be an observable current quote at inference; historical paid premium is a proxy.',
        'q(m,e)=min(1,m^-e), 0<=e<=emax, is assumed, not identified from accepted orders.',
        'Discounts introduce no new customers in the conservative scenario.',
        'Conditional payouts and behavior are held fixed; adverse selection is unmeasured.',
        'Caps and retention floor are proposed design choices, not Jasper scoring rules.',
        'Training premium neutrality does not imply future premium neutrality.',
        'No funding, fees, hedges, inventory, capital or operating costs are included.',
        'July was previously inspected; results are retrospective research evidence.'
    ]
    validate_model(m)
    return m


def quotes(model, data):
    """Row-local inference. Outcome columns do not enter this function."""
    validate_model(model)
    out = data[['source_row','createdAt','productType','premiumAmount_USDC']].copy()
    out = out.rename(columns={'premiumAmount_USDC':'reference_premium_USDC'})
    out['expected_payout_USDC'] = np.nan
    out['recommended_multiplier'] = np.nan
    out['recommended_premium_USDC'] = np.nan
    out['assumed_retention_at_emax'] = np.nan
    out['is_before_model_cutoff'] = data.createdAt.lt(pd.Timestamp(model['cutoff_utc']))
    out['status'] = 'no_quote_invalid_contract_or_reference'
    contract = data.contract_valid & data.reference_valid
    valid = data.quote_valid
    fallback = contract & ~valid
    # Preserve row continuity but explicitly label unsupported price fallbacks.
    out.loc[fallback,'recommended_multiplier'] = 1.
    out.loc[fallback,'recommended_premium_USDC'] = data.loc[fallback,'premiumAmount_USDC']
    out.loc[fallback,'status'] = 'reference_fallback_requote_before_live_use'
    if valid.any():
        mult = multiplier(model,data.loc[valid])
        out.loc[valid,'expected_payout_USDC'] = cost(model,data.loc[valid])
        out.loc[valid,'recommended_multiplier'] = mult
        out.loc[valid,'recommended_premium_USDC'] = mult*data.loc[valid,'premiumAmount_USDC'].to_numpy()
        out.loc[valid,'assumed_retention_at_emax'] = np.minimum(1., mult**(-model['pricing']['assumed_max_elasticity']))
        out.loc[valid,'status'] = 'research_candidate_with_assumed_demand'
        out.loc[valid & out.is_before_model_cutoff,'status'] = 'historical_diagnostic_model_used_later_labels'
    return out.sort_values('source_row').reset_index(drop=True)


def lower_tail_mean(x):
    """Mean of the lowest 20% of cohorts, with fractional boundary weight."""
    x = np.sort(np.asarray(x,float)); mass=.2*len(x)
    if mass == 0: raise ValueError('Need at least one creation cohort')
    whole=int(np.floor(mass)); fraction=mass-whole
    return float((x[:whole].sum()+(fraction*x[whole] if fraction>1e-12 else 0))/mass)


def scenario_tables(model, frame, period):
    b = frame.premiumAmount_USDC.to_numpy(float); y = frame.realizedProfit_USDC.to_numpy(float)
    m = multiplier(model,frame); avg = float(np.sum(m*b)/b.sum())
    rows, daily = [], []
    for e in [0,1,2,4]:
        q = np.minimum(1.,m**(-e)); retained = float(q.mean())
        policies = {'v2_candidate':(m,q), 'recorded_reference':(np.ones(len(m)),np.ones(len(m))),
                    'uniform_equal_quoted_premium':(np.full(len(m),avg),np.full(len(m),min(1.,avg**(-e))))}
        if e > 0:
            u = retained**(-1./e)
            policies['uniform_equal_order_retention'] = (np.full(len(m),u),np.full(len(m),retained))
        for name,(mult,ret) in policies.items():
            margin = ret*(b*mult-y)
            byday = pd.DataFrame({'day':frame.day,'gross_margin_USDC':margin}).groupby('day',as_index=False).sum()
            rows.append({'period':period,'elasticity':e,'policy':name,'orders':len(frame),
                         'mean_order_retention':float(ret.mean()), 'minimum_order_retention':float(ret.min()),
                         'notional_retention':float(np.average(ret,weights=frame.notional_USDC)),
                         'quoted_premium_change':float(np.sum(mult*b)/b.sum()-1),
                         'discounted_order_share':float(np.mean(mult<1-1e-10)),
                         'gross_margin_USDC':float(margin.sum()),'scenario_premium_USDC':float(np.sum(ret*b*mult)),
                         'scenario_payout_USDC':float(np.sum(ret*y)),
                         'worst_creation_cohort_margin_USDC':float(byday.gross_margin_USDC.min()),
                         'lower20pct_creation_cohort_mean_USDC':lower_tail_mean(byday.gross_margin_USDC)})
            byday['period']=period;byday['elasticity']=e;byday['policy']=name;daily.append(byday)
    return pd.DataFrame(rows),pd.concat(daily,ignore_index=True)


def bootstrap_commercial(daily, iterations=2000):
    """Paired UTC-day bootstrap; freezes diagnostic uniform quotes in each resample."""
    rng = np.random.default_rng(SEED); rows=[]
    july=daily[daily.period.eq('2026-07')]
    for e,g in july.groupby('elasticity'):
        wide=g.pivot(index='day',columns='policy',values='gross_margin_USDC')
        for comparator in [c for c in wide if c!='v2_candidate']:
            delta=(wide.v2_candidate-wide[comparator]).to_numpy()
            draws=delta[rng.integers(0,len(delta),size=(iterations,len(delta)))].sum(axis=1)
            rows.append({'elasticity':int(e),'comparator':comparator,'gross_margin_difference_USDC':float(delta.sum()),
                         'conditional_95pct_low':float(np.quantile(draws,.025)),
                         'conditional_95pct_high':float(np.quantile(draws,.975))})
    return rows


def analyze(args):
    out=Path(args.outdir);out.mkdir(parents=True,exist_ok=True)
    market=v1.read_market(args.market);d=v1.features(args.orders,market)
    metrics=[];scenarios=[];days=[];models={}
    for month in ['2026-04','2026-05','2026-06','2026-07']:
        start=pd.Timestamp(month+'-01',tz='UTC');end=start+pd.offsets.MonthBegin(1)
        m=fit(d,start);models[month]=m
        test=d[d.analysis_valid & d.createdAt.ge(start) & d.createdAt.lt(end)]
        if month!='2026-07':test=test[test.closedAt.lt(end)]
        baseline=test.premiumAmount_USDC.to_numpy()*m['pooled_payout_to_premium']
        for name,c in [('calibrated_recorded_reference',baseline),('duration_credibility_200',cost(m,test))]:
            metrics.append({'period':month,'model':name,'training_rows':m['training_rows'],**v1.metrics(test,c)})
        sr,dy=scenario_tables(m,test,month);scenarios.append(sr);days.append(dy)
        if month=='2026-07':
            q=quotes(m,test);q.to_csv(out/'july_recommendations.csv',index=False)
            tier=pd.DataFrame({'productType':TENORS,'tenor_hours':np.array(TENORS)/3600.,'payout_to_reference_ratio':[m['tenor_ratios'][str(t)] for t in TENORS]})
            sample=pd.DataFrame({'productType':TENORS,'premiumAmount_USDC':np.ones(7)})
            tier['recommended_multiplier']=multiplier(m,sample);tier.to_csv(out/'frozen_tenor_rates.csv',index=False)
    result=pd.concat(scenarios,ignore_index=True);daily=pd.concat(days,ignore_index=True)
    pd.DataFrame(metrics).to_csv(out/'cost_metrics.csv',index=False)
    result.to_csv(out/'commercial_scenarios.csv',index=False);daily.to_csv(out/'creation_cohort_margins.csv',index=False)
    write_json(out/'conditional_bootstrap.json',bootstrap_commercial(daily))
    write_json(out/'frozen_july_model.json',models['2026-07'])
    write_json(out/'preblind_research_model.json',fit(d,'2026-07-31T17:11:48Z'))
    write_json(out/'fold_models.json',models)
    manifest={str(Path(f).name):{'bytes':Path(f).stat().st_size,'sha256':hashlib.sha256(Path(f).read_bytes()).hexdigest()} for f in [args.orders,args.market]}
    write_json(out/'input_manifest.json',manifest)
    write_json(out/'protocol.json',{'cost_model':'Duration credibility, 200 prior average-premium order equivalents; selected in separate seven-model April-June study.',
               'price_rule':'Fixed analytic weight from rho=.95, emax=4, upper raw multiplier1.15. Designed after July diagnostics; parameters are explicit design assumptions, not optimized July weights or an untouched validation result.',
               'evaluation':'April-June rolling-origin settled-label development; July retrospective because already inspected.',
               'comparators':'Recorded reference; equal aggregate quoted-premium uniform; equal mean-order-retention uniform. Uniform matches use evaluation quote mix, so are diagnostic, not frozen deployable policies.',
               'scenario_boundary':'Homogeneous assumed demand, fixed conditional payouts, no extra buyers after discounts, all costs excluded.',
               'bootstrap':'2000 paired UTC order-creation-day samples, conditional on fitted models, demand assumptions and frozen diagnostic uniform quotes; no model-selection or full cross-day uncertainty.',
               'capital_boundary':'Creation-cohort losses are not settlement cashflow, mark-to-market or full portfolio risk.'})
    print(result[result.period.eq('2026-07') & result.elasticity.eq(4)][['policy','gross_margin_USDC','mean_order_retention','quoted_premium_change']].to_string(index=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ['analyze','train','predict']:
        p=sub.add_parser(command);p.add_argument('--orders',required=True);p.add_argument('--market',required=True)
        if command=='analyze':p.add_argument('--outdir',required=True)
        if command=='train':p.add_argument('--cutoff',required=True);p.add_argument('--model-out',required=True);p.add_argument('--rho',type=float,default=.95);p.add_argument('--emax',type=float,default=4.)
        if command=='predict':p.add_argument('--model',required=True);p.add_argument('--output',required=True)
    a=parser.parse_args()
    if a.command=='analyze':analyze(a);return
    model=json.loads(Path(a.model).read_text()) if a.command=='predict' else None
    data=v1.features(a.orders,v1.read_market(a.market))
    if a.command=='train':write_json(a.model_out,fit(data,a.cutoff,rho=a.rho,emax=a.emax))
    else:
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        quotes(model,data).to_csv(a.output,index=False)


if __name__=='__main__':main()
