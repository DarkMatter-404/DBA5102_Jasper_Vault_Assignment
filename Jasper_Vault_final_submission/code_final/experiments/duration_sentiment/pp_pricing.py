#!/usr/bin/env python3
"""Jasper PP: chronological expected-payout benchmark and bounded price allocation.

This estimates E[gross payout | a historically purchased order, quote information].
It is not a risk-neutral option value and does not identify price-demand causality.
Only pandas/numpy/scipy/matplotlib are required. No outcomes enter feature creation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize, brentq
from scipy.special import ndtr

SEED = 271828
FEATURES = {
    'scalar': [],
    'structure': ['log_tenor', 'put'],
    'state': ['log_tenor', 'put', 'log_vol_ratio', 'signed_momentum_60'],
}


def read_market(path):
    m = pd.read_csv(path)
    m['bar_close'] = pd.to_datetime(m['close_time_utc'], utc=True)
    m = m.sort_values('bar_close').drop_duplicates('bar_close')
    r = np.log(m['close']).diff()
    gap = m['bar_close'].diff().dt.total_seconds().ne(60)
    r = r.mask(gap)
    for n in (60, 1440):
        m[f'v{n}'] = r.pow(2).rolling(n, min_periods=n).mean()
    m['return_60'] = np.log(m['close'] / m['close'].shift(60))
    m['market_price'] = m['close']
    return m[['bar_close', 'market_price', 'v60', 'v1440', 'return_60']]


def features(path, market, max_lag=120, feature_clock='createdAt'):
    p = pd.read_csv(path)
    p['source_row'] = np.arange(len(p))
    for c in ['createdAt', 'expirationDate', 'closedAt']:
        if c not in p: p[c] = pd.NaT
        p[c] = pd.to_datetime(p[c], utc=True, errors='coerce')
    if 'realizedProfit_USDC' not in p: p['realizedProfit_USDC'] = np.nan
    for c in ['premiumAmount_USDC', 'productType', 'quantity_BTC', 'strikePrice', 'optionType']:
        p[c] = pd.to_numeric(p[c], errors='coerce')
    p['feature_time'] = p.createdAt
    if feature_clock == 'nominal_start':
        nominal_start = p.expirationDate-pd.to_timedelta(p.productType, unit='s')
        p['feature_time'] = pd.concat([p.createdAt, nominal_start], axis=1).min(axis=1)
    missing_quote = p.feature_time.isna()
    good = pd.merge_asof(p.loc[~missing_quote].sort_values('feature_time'), market,
                        left_on='feature_time', right_on='bar_close', direction='backward')
    p = pd.concat([good, p.loc[missing_quote]], ignore_index=True).sort_values('source_row')
    p['notional_USDC'] = p.quantity_BTC * p.strikePrice
    p['tenor_minutes'] = p.productType / 60
    p['lag_seconds'] = p.productType - (p.expirationDate - p.createdAt).dt.total_seconds()
    p['market_age_seconds'] = (p.feature_time - p.bar_close).dt.total_seconds()
    p['variance_blend'] = .5 * p.v60 + .5 * p.v1440
    # All orders are ATM per class notes; venue basis is not treated as moneyness.
    z = np.sqrt(p.variance_blend * p.tenor_minutes)
    p['anchor_bps'] = np.maximum(1e4 * (2 * ndtr(z / 2) - 1), .000001)
    p['recorded_bps'] = p.premiumAmount_USDC / p.notional_USDC * 1e4
    p['payout_bps'] = p.realizedProfit_USDC / p.notional_USDC * 1e4
    p['log_tenor'] = np.log(p.tenor_minutes / 120)
    p['put'] = p.optionType
    p['log_vol_ratio'] = .5 * np.log(p.v60 / p.v1440)
    p['signed_momentum_60'] = (1 - 2 * p.optionType) * p.return_60 / np.sqrt(60*p.v60)
    # Hard bounds fixed a priori; scale fitting uses train data only.
    p['log_vol_ratio'] = p.log_vol_ratio.clip(-2.5, 2.5)
    p['signed_momentum_60'] = p.signed_momentum_60.clip(-4, 4)
    p['reference_valid'] = p.premiumAmount_USDC.gt(0) & np.isfinite(p.premiumAmount_USDC)
    p['contract_valid'] = (p.createdAt.notna() & p.expirationDate.gt(p.createdAt)
        & p.quantity_BTC.gt(0) & p.strikePrice.gt(0)
        & p.optionType.isin([0, 1]) & p.productType.isin([1800,3600,7200,14400,28800,43200,86400])
        & np.isfinite(p[['quantity_BTC','strikePrice','notional_USDC']].to_numpy(float)).all(axis=1))
    p['quote_time_valid'] = p.lag_seconds.between(0, max_lag)
    p['market_valid'] = (p.market_age_seconds.between(0, 60)
        & np.isfinite(p[FEATURES['state']+['anchor_bps']].to_numpy(float)).all(axis=1))
    p['quote_valid'] = (p.reference_valid & p.contract_valid & p.quote_time_valid & p.market_valid
        & np.isfinite(p.recorded_bps))
    p['label_valid'] = (p.realizedProfit_USDC.notna() & p.realizedProfit_USDC.ge(0)
        & p.closedAt.notna() & p.closedAt.ge(p.createdAt))
    p['analysis_valid'] = p.quote_valid & p.label_valid
    p['day'] = p.createdAt.dt.strftime('%Y-%m-%d')
    p['month'] = p.createdAt.dt.strftime('%Y-%m')
    return p.reset_index(drop=True)


def fit(train, anchor, feature_set, alpha):
    names = FEATURES[feature_set]
    x = train[names].to_numpy(float)
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-12] = 1.
    x = (x-center)/scale
    x = np.column_stack([np.ones(len(x)), x])
    y = train.payout_bps.to_numpy(float)
    a = train[anchor].to_numpy(float)
    # Notional weights make the score responsive to portfolio dollar claims.
    w = train.notional_USDC.to_numpy(float)
    w = w / w.sum()
    initial = np.zeros(x.shape[1])
    initial[0] = np.log(np.sum(w*y)/np.sum(w*a))
    def objective(beta):
        eta = np.log(a) + x @ beta
        mu = np.exp(np.clip(eta, -30, 30))
        penalty = .5*alpha*np.sum(beta[1:]**2)
        value = np.sum(w*(mu-y*eta)) + penalty
        grad = x.T @ (w*(mu-y))
        grad[1:] += alpha*beta[1:]
        return value, grad
    opt = minimize(objective, initial, jac=True, method='L-BFGS-B',
                   options={'maxiter':1000,'ftol':1e-12,'gtol':1e-8})
    if not opt.success and np.max(np.abs(opt.jac)) > 1e-4:
        raise RuntimeError(opt.message)
    return {'anchor':anchor, 'feature_set':feature_set, 'features':names,
            'alpha':float(alpha), 'center':center.tolist(), 'scale':scale.tolist(),
            'beta':opt.x.tolist(), 'train_rows':len(train),
            'fit_last_createdAt':str(train.createdAt.max()),
            'fit_last_closedAt':str(train.closedAt.max()),
            'optimizer_success':bool(opt.success)}


def predict_rate(model, data):
    x = (data[model['features']].to_numpy(float)-np.array(model['center']))/np.array(model['scale'])
    x = np.column_stack([np.ones(len(x)), x])
    return data[model['anchor']].to_numpy(float)*np.exp(np.clip(x@np.array(model['beta']),-15,15))


def metrics(data, pred):
    y = data.realizedProfit_USDC.to_numpy(float)
    pred = np.maximum(np.asarray(pred,float),1e-10)
    rate = pred/data.notional_USDC.to_numpy(float)*1e4
    yr = data.payout_bps.to_numpy(float)
    w = data.notional_USDC.to_numpy(float)
    term = np.where(yr>0, yr*np.log(np.maximum(yr,1e-20)/rate), 0)
    return {'n':len(data),'actual_payout_USDC':y.sum(),'predicted_payout_USDC':pred.sum(),
        'calibration_ratio_predicted_to_actual':pred.sum()/y.sum(),
        'MAE_USDC':np.mean(np.abs(pred-y)),'RMSE_USDC':np.sqrt(np.mean((pred-y)**2)),
        'notional_weighted_MAE_bps':np.average(np.abs(rate-yr),weights=w),
        'notional_weighted_poisson_deviance':2*np.average(term-yr+rate,weights=w)}


def train_before(data, cutoff):
    t = pd.Timestamp(cutoff)
    t = t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')
    return data[data.analysis_valid & data.createdAt.lt(t) & data.closedAt.lt(t)].copy()


def pricing_settings(model, train, eta=.5, lower=.85, upper=1.15):
    risk = predict_rate(model,train)*train.notional_USDC.to_numpy()/1e4
    ref = train.premiumAmount_USDC.to_numpy(float)
    loss_ratio = train.realizedProfit_USDC.sum()/ref.sum()
    score = np.maximum(risk/(loss_ratio*ref),1e-6)**eta
    root = brentq(lambda c: np.sum(ref*np.clip(c*score,lower,upper))-ref.sum(),.0001,1e4)
    return {'eta':eta, 'lower':lower, 'upper':upper, 'normalizer':root,
            'training_claims_to_recorded_premium':loss_ratio,
            'calibration_rows':len(train), 'premium_neutral_on':'fit sample only',
            'description':'Paid-price proxy. Caps and eta are design assumptions, not estimated demand constraints.'}


def quote_predictions(data, model):
    out = data[['source_row','createdAt','optionType','productType','premiumAmount_USDC']].copy()
    out['expected_payout_USDC'] = np.nan
    out['pricing_multiplier'] = np.nan
    out['challenger_multiplier'] = np.nan
    out['challenger_premium_USDC'] = np.nan
    out['recommended_premium_USDC'] = np.nan
    out['status'] = 'no_quote_invalid_reference'
    out.loc[data.reference_valid & ~data.contract_valid,'status'] = 'no_quote_invalid_contract'
    can_reference = data.reference_valid & data.contract_valid
    out.loc[can_reference,'pricing_multiplier'] = 1.
    out.loc[can_reference,'challenger_multiplier'] = 1.
    out.loc[can_reference,'challenger_premium_USDC'] = data.loc[can_reference,'premiumAmount_USDC']
    out.loc[can_reference,'recommended_premium_USDC'] = data.loc[can_reference,'premiumAmount_USDC']
    out.loc[can_reference,'status'] = 'fallback_recorded_price_market_data_invalid'
    out.loc[can_reference & ~data.quote_time_valid,'status'] = 'fallback_recorded_price_ambiguous_quote_time'
    valid = data.quote_valid
    risk = predict_rate(model,data.loc[valid])*data.loc[valid,'notional_USDC'].to_numpy()/1e4
    ref = data.loc[valid,'premiumAmount_USDC'].to_numpy(float)
    s = model['pricing']
    mult = np.clip(s['normalizer']*(np.maximum(risk/(s['training_claims_to_recorded_premium']*ref),1e-6))**s['eta'],s['lower'],s['upper'])
    out.loc[valid,'expected_payout_USDC'] = risk
    out.loc[valid,'challenger_multiplier'] = mult
    out.loc[valid,'challenger_premium_USDC'] = ref*mult
    weight=float(model.get('overlay_weight',0.))
    if not 0 <= weight <= 1: raise ValueError('overlay_weight must be between 0 and 1')
    if weight>0:
        out.loc[valid,'pricing_multiplier'] = 1+weight*(mult-1)
        out.loc[valid,'recommended_premium_USDC'] = ref*(1+weight*(mult-1))
        out.loc[valid,'status'] = 'experimental_model_recorded_premium_proxy'
    else:
        out.loc[valid,'status'] = 'gate_closed_retain_recorded_premium'
    return out.sort_values('source_row')


def dump_json(path, data):
    Path(path).write_text(json.dumps(data,indent=2,default=lambda x: x.item() if isinstance(x,np.generic) else str(x)))


def analyze(args):
    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    market = read_market(args.market)
    data = features(args.orders, market)
    valid = data[data.analysis_valid].copy()
    audit = {
        'raw_order_rows':len(data),'label_nonmissing':int(data.realizedProfit_USDC.notna().sum()),
        'missing_outcome_and_close':int((data.realizedProfit_USDC.isna() & data.closedAt.isna()).sum()),
        'zero_payouts_raw':int(data.realizedProfit_USDC.eq(0).sum()),
        'closes_before_creation':int(data.closedAt.lt(data.createdAt).sum()),
        'expirations_before_creation':int(data.expirationDate.lt(data.createdAt).sum()),
        'nominal_duration_gap_over_120s':int(data.lag_seconds.gt(120).sum()),
        'valid_analysis_rows':len(valid),'excluded_union':len(data)-len(valid),
        'valid_zero_payout_share':float(valid.realizedProfit_USDC.eq(0).mean()),
        'close_over_60s_before_expiry_share':float((valid.closedAt<valid.expirationDate-pd.Timedelta(seconds=60)).mean()),
        'raw_nonmissing_outcome_premium_USDC':float(data.loc[data.realizedProfit_USDC.notna(),'premiumAmount_USDC'].sum()),
        'valid_premium_USDC':float(valid.premiumAmount_USDC.sum()),
        'valid_payout_USDC':float(valid.realizedProfit_USDC.sum()),
        'valid_gross_margin_USDC':float((valid.premiumAmount_USDC-valid.realizedProfit_USDC).sum()),
        'market_rows':len(market),'market_first_close':str(market.bar_close.min()),'market_last_close':str(market.bar_close.max()),
        'quote_feature_rule':'Only bars with close_time_utc <= createdAt. Max market age 60 seconds.',
        'timestamp_rule':'expiry>created; 0<=productType-(expiry-created)<=120 seconds; close>=created for labelled analysis.',
        'target_definition':'Gross payout per notes; conditional on historical buyer/early-close mix.',
        'assumptions':['All ATM per class notes','premiumAmount_USDC is observed paid premium, not verified internal Base Premium','createdAt approximates quote time; up to 120 seconds of nominal-time discrepancy accepted','No fees, funding, hedge P&L, capacity or capital included in gross margin']}
    dump_json(out/'data_audit.json',audit)
    data.loc[~data.analysis_valid, ['source_row','createdAt','closedAt','expirationDate','lag_seconds','quote_valid','label_valid']].to_csv(out/'excluded_rows.csv',index=False)
    month = valid.groupby('month').agg(orders=('source_row','size'),premium_USDC=('premiumAmount_USDC','sum'),payout_USDC=('realizedProfit_USDC','sum'),notional_USDC=('notional_USDC','sum'))
    month['gross_margin_USDC']=month.premium_USDC-month.payout_USDC
    month['claims_to_premium']=month.payout_USDC/month.premium_USDC
    month.to_csv(out/'monthly_summary.csv')
    duration = valid.groupby('productType').agg(orders=('source_row','size'),premium_USDC=('premiumAmount_USDC','sum'),payout_USDC=('realizedProfit_USDC','sum'))
    duration['claims_to_premium']=duration.payout_USDC/duration.premium_USDC
    duration.to_csv(out/'duration_summary.csv')
    train = train_before(data,'2026-06-01')
    dev = valid[valid.createdAt.ge(pd.Timestamp('2026-06-01',tz='UTC')) & valid.createdAt.lt(pd.Timestamp('2026-07-01',tz='UTC')) & valid.closedAt.lt(pd.Timestamp('2026-07-01',tz='UTC'))].copy()
    test = valid[valid.createdAt.ge(pd.Timestamp('2026-07-01',tz='UTC'))].copy()
    split = {'training':{'n':len(train),'first':str(train.createdAt.min()),'last':str(train.createdAt.max()),'latest_label':str(train.closedAt.max())},
        'development':{'n':len(dev),'first':str(dev.createdAt.min()),'last':str(dev.createdAt.max()),'latest_label':str(dev.closedAt.max())},
        'July_holdout':{'n':len(test),'first':str(test.createdAt.min()),'last':str(test.createdAt.max()),'latest_label':str(test.closedAt.max())}}
    # Freeze candidates before looking at July. Selection uses June weighted Poisson deviance.
    candidate_rows=[]; candidates={}
    for anchor in ['recorded_bps','anchor_bps']:
        for feature_set in FEATURES:
            for alpha in ([0.] if feature_set=='scalar' else [.1,1.,10.]):
                name=f'{anchor}_{feature_set}_ridge{alpha:g}'
                model=fit(train,anchor,feature_set,alpha)
                pred=predict_rate(model,dev)*dev.notional_USDC.to_numpy()/1e4
                candidate_rows.append({'model':name,**metrics(dev,pred)})
                candidates[name]=model
    selection=pd.DataFrame(candidate_rows).sort_values('notional_weighted_poisson_deviance')
    selection.to_csv(out/'june_model_selection.csv',index=False)
    winner=selection.iloc[0].model
    final_train=train_before(data,'2026-07-01')
    models={}
    for name,m in candidates.items():
        models[name]=fit(final_train,m['anchor'],m['feature_set'],m['alpha'])
    selected=models[winner]
    selected['selected_by']='June notional-weighted quasi-Poisson deviance, candidate set fixed before July evaluation'
    selected['selected_name']=winner
    selected['pricing']=pricing_settings(selected,final_train)
    selected['analysis_cutoff']='2026-07-01T00:00:00Z'
    selected['max_timestamp_gap_seconds']=120
    selected['feature_clock']='createdAt'
    selected['overlay_weight']=1.
    selected['deployment_warning']='Experimental July evaluation artifact only. Deployment model disables overlay after failed July gate.'
    dump_json(out/'frozen_july_model.json',selected)
    # Only predeclared comparators; no July-driven model revision.
    benchmark_names=['recorded_bps_scalar_ridge0','anchor_bps_scalar_ridge0',winner]
    benchmark_names=list(dict.fromkeys(benchmark_names))
    predictions={'recorded_price_as_cost_proxy':test.premiumAmount_USDC.to_numpy(),
                 'constant_notional_rate':np.repeat(final_train.realizedProfit_USDC.sum()/final_train.notional_USDC.sum(),len(test))*test.notional_USDC.to_numpy()}
    for name in benchmark_names:
        predictions[name]=predict_rate(models[name],test)*test.notional_USDC.to_numpy()/1e4
    # Best independent-anchor candidate selected on June, even if not champion.
    independent=selection[selection.model.str.startswith('anchor_bps')].iloc[0].model
    if independent not in predictions:
        predictions[independent]=predict_rate(models[independent],test)*test.notional_USDC.to_numpy()/1e4
    # Secondary family diagnostic: best recorded-price state/structure model by the same June rule.
    best_recorded=selection[selection.model.str.startswith('recorded_bps')].iloc[0].model
    if best_recorded not in predictions:
        predictions[best_recorded]=predict_rate(models[best_recorded],test)*test.notional_USDC.to_numpy()/1e4
    results=pd.DataFrame([{'model':name,**metrics(test,pred)} for name,pred in predictions.items()])
    results.to_csv(out/'july_holdout_metrics.csv',index=False)
    detail=test[['source_row','createdAt','closedAt','optionType','productType','quantity_BTC','notional_USDC','premiumAmount_USDC','realizedProfit_USDC','day']].copy()
    for name,pred in predictions.items():detail[name]=pred
    quotes=quote_predictions(data,selected)
    quotes.to_csv(out/'training_rows_with_frozen_july_quotes.csv',index=False)
    detail=detail.merge(quotes[['source_row','pricing_multiplier','recommended_premium_USDC']],on='source_row',validate='one_to_one')
    detail.to_csv(out/'july_holdout_predictions.csv',index=False)
    # Paired day-block bootstrap: preserves within-day dependence; conditional on fitted model.
    comparator='recorded_bps_scalar_ridge0'
    rng=np.random.default_rng(SEED)
    daily=detail.groupby('day').apply(lambda g:pd.Series({'n':len(g),
        'sse_champion':np.sum((g[winner]-g.realizedProfit_USDC)**2),
        'sse_comparator':np.sum((g[comparator]-g.realizedProfit_USDC)**2),
        'ae_champion':np.sum(np.abs(g[winner]-g.realizedProfit_USDC)),
        'ae_comparator':np.sum(np.abs(g[comparator]-g.realizedProfit_USDC)),
        'actual_payout':g.realizedProfit_USDC.sum(),'predicted':g[winner].sum()}),include_groups=False)
    boots=[]
    for _ in range(2000):
        a=daily.iloc[rng.integers(0,len(daily),len(daily))].sum()
        boots.append([np.sqrt(a.sse_champion/a.n)-np.sqrt(a.sse_comparator/a.n),
            (a.ae_champion-a.ae_comparator)/a.n,a.predicted/a.actual_payout])
    boot=np.array(boots)
    ci={'method':'2000 paired UTC-day resamples, seed 271828; conditional on fitted model; 31 days, not independent trades',
        'RMSE_difference_champion_minus_calibrated_recorded_95pct':np.quantile(boot[:,0],[.025,.975]).tolist(),
        'MAE_difference_champion_minus_calibrated_recorded_95pct':np.quantile(boot[:,1],[.025,.975]).tolist(),
        'champion_calibration_ratio_95pct':np.quantile(boot[:,2],[.025,.975]).tolist()}
    dump_json(out/'july_bootstrap.json',ci)
    # Commercial sensitivity. Assumed retention among historical buyers, never estimated demand.
    scenarios=[]
    for elasticity in [0,1,2,4]:
        mult=detail.pricing_multiplier.to_numpy()
        # Markdown increases do not invent additional buyers; price increases thin current buyers.
        retained=np.minimum(1.,mult**(-elasticity))
        scenarios.append({'assumed_elasticity':elasticity,'expected_retained_orders':retained.sum(),
            'retention_share':retained.mean(),
            'scenario_revenue_USDC':np.sum(retained*detail.recommended_premium_USDC),
            'scenario_payout_USDC':np.sum(retained*detail.realizedProfit_USDC),
            'scenario_gross_margin_USDC':np.sum(retained*(detail.recommended_premium_USDC-detail.realizedProfit_USDC)),
            'historic_gross_margin_USDC':np.sum(detail.premiumAmount_USDC-detail.realizedProfit_USDC)})
    pd.DataFrame(scenarios).to_csv(out/'july_assumed_retention_scenarios.csv',index=False)
    # Order-creation cohort downside stress. Eventual payouts are attributed to opening date.
    # These are not settlement cashflows, daily mark-to-market P&L or inventory risk measures.
    day_result=detail.groupby('day').agg(recorded_premium=('premiumAmount_USDC','sum'),proposed_premium=('recommended_premium_USDC','sum'),payout=('realizedProfit_USDC','sum'))
    day_result['recorded_gross_margin']=day_result.recorded_premium-day_result.payout
    day_result['proposed_fixed_volume_gross_margin']=day_result.proposed_premium-day_result.payout
    day_result['time_basis']='UTC order-creation cohort; premium minus eventual payout'
    day_result.to_csv(out/'july_daily_margin.csv')
    stress=[]
    for name,price in [('recorded',detail.premiumAmount_USDC),('proposed_fixed_volume',detail.recommended_premium_USDC)]:
        for payout_scale in [1,1.25,1.5,2]:
            gm=price-payout_scale*detail.realizedProfit_USDC
            byday=gm.groupby(detail.day).sum()
            stress.append({'pricing':name,'payout_multiplier':payout_scale,'gross_margin_USDC':gm.sum(),
                'worst_day_gross_margin_USDC':byday.min(),'loss_days':int(byday.lt(0).sum()),
                'time_basis':'UTC order-creation cohort; not settlement cashflow or mark-to-market'})
    pd.DataFrame(stress).to_csv(out/'payout_stress.csv',index=False)
    summary={'selected_model':winner,'best_independent_candidate':independent,'best_recorded_candidate':best_recorded,'split':split,
        'refit_rows_for_July':len(final_train),'pricing_settings':selected['pricing'],
        'July_mean_multiplier':float(detail.pricing_multiplier.mean()),
        'July_premium_weighted_multiplier':float(detail.recommended_premium_USDC.sum()/detail.premiumAmount_USDC.sum()),
        'July_share_price_increases':float(detail.pricing_multiplier.gt(1+1e-8).mean()),
        'July_share_price_decreases':float(detail.pricing_multiplier.lt(1-1e-8).mean()),
        'July_share_at_lower_cap':float(np.isclose(detail.pricing_multiplier,.85).mean()),
        'July_share_at_upper_cap':float(np.isclose(detail.pricing_multiplier,1.15).mean()),
        'July_premium_USDC':float(detail.premiumAmount_USDC.sum()),'July_proposed_fixed_volume_premium_USDC':float(detail.recommended_premium_USDC.sum()),
        'July_payout_USDC':float(detail.realizedProfit_USDC.sum()),'July_worst_day_recorded_gross_margin':float(day_result.recorded_gross_margin.min()),
        'daily_margin_time_basis':'UTC order-creation cohorts: recorded premium less eventual payout. Not settlement cashflow or mark-to-market portfolio risk.',
        'bootstrap':ci,'important':'No re-selection based on July. Final deployment refit is separate and July metrics do not describe that refit.'}
    dump_json(out/'analysis_summary.json',summary)
    # Deployment fit uses only labels settled before the provided cutoff, protecting the split boundary.
    # The source guide splits July 31 at 17:11:48; later labels must not leak into that blind split.
    deploy_cutoff='2026-07-31T17:11:48Z'
    deploy_data=train_before(data,deploy_cutoff)
    deployment=fit(deploy_data,selected['anchor'],selected['feature_set'],selected['alpha'])
    deployment.update({'selected_name':winner,'selected_by':selected['selected_by'],'pricing':pricing_settings(deployment,deploy_data),
        'analysis_cutoff':deploy_cutoff,'max_timestamp_gap_seconds':120,'feature_clock':'createdAt',
        'overlay_weight':0.,'gate_reason':'July selected challenger underperforms calibrated recorded-price cost benchmark and worsens gross-margin retention scenarios. No demonstrated improvement.'})
    dump_json(out/'deployment_model.json',deployment)
    # Portable chart outputs for deck construction.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(9,4.4))
    names=['Calibrated paid premium','Calibrated volatility anchor','Selected risk model']
    ids=['recorded_bps_scalar_ridge0','anchor_bps_scalar_ridge0',winner]
    vals=[results.loc[results.model.eq(i),'RMSE_USDC'].iloc[0] for i in ids]
    ax.barh(names,vals,color=['#728394','#B0BFCB','#0D8077']); ax.invert_yaxis()
    for i,v in enumerate(vals):ax.text(v+.8,i,f'{v:.2f}',va='center')
    ax.set_xlabel('July payout prediction RMSE (USDC per order; lower is better)')
    ax.set_xlim(0,max(vals)*1.16); fig.tight_layout();fig.savefig(out/'july_rmse.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.4))
    ax.plot(month.index,month.claims_to_premium,color='#0D8077',marker='o',linewidth=2)
    ax.axhline(1,color='#C35151',linestyle='--');ax.set_ylabel('Payouts / recorded premiums');ax.set_xlabel('Order creation month; audited sample')
    fig.tight_layout();fig.savefig(out/'monthly_claims_ratio.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.4))
    x=np.arange(len(day_result));ax.bar(x,day_result.recorded_gross_margin,color=np.where(day_result.recorded_gross_margin>=0,'#0D8077','#C35151'))
    ax.set_xticks(x[::5]);ax.set_xticklabels(day_result.index[::5],rotation=20);ax.set_ylabel('Cohort premium − eventual payout (USDC)');ax.set_xlabel('July order-creation date (UTC); no operating or hedge costs')
    fig.tight_layout();fig.savefig(out/'july_daily_gross_margin.png',dpi=180);plt.close(fig)
    print(json.dumps(summary,indent=2))
    print(results.to_string(index=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for cmd in ['analyze','train','predict']:
        p=sub.add_parser(cmd)
        p.add_argument('--orders',required=True);p.add_argument('--market',required=True)
        if cmd=='analyze':p.add_argument('--outdir',required=True)
        elif cmd=='train':
            p.add_argument('--template-model',required=True,help='Frozen model specification; no tuning here.')
            p.add_argument('--cutoff',required=True,help='Train only on orders AND outcomes before UTC cutoff.')
            p.add_argument('--model-out',required=True)
        else:
            p.add_argument('--model',required=True);p.add_argument('--output',required=True)
            p.add_argument('--experimental-overlay',action='store_true',help='Research only: override failed deployment gate to inspect experimental quotes.')
    args=parser.parse_args()
    if args.command=='analyze':analyze(args);return
    model=json.loads(Path(args.template_model if args.command=='train' else args.model).read_text())
    data=features(args.orders,read_market(args.market),model.get('max_timestamp_gap_seconds',120),model.get('feature_clock','createdAt'))
    if args.command=='train':
        sample=train_before(data,args.cutoff)
        result=fit(sample,model['anchor'],model['feature_set'],model['alpha'])
        result.update({'pricing':pricing_settings(result,sample),'analysis_cutoff':args.cutoff,
            'selected_name':model.get('selected_name'),'selected_by':model.get('selected_by'),
            'max_timestamp_gap_seconds':model.get('max_timestamp_gap_seconds',120),
            'feature_clock':model.get('feature_clock','createdAt'),'overlay_weight':0.,
            'gate_reason':'Refitting does not establish deployment success. Requires fresh validation.'})
        dump_json(args.model_out,result)
        print(f'Saved model fitted on {len(sample)} settled, eligible orders to {args.model_out}')
    else:
        if args.experimental_overlay:model['overlay_weight']=1.
        result=quote_predictions(data,model)
        result.to_csv(args.output,index=False)
        n_fallback=int(result.status.str.startswith('fallback_').sum())
        n_no_quote=int(result.status.str.startswith('no_quote_').sum())
        print(f'Saved {len(result)} rows in source order to {args.output}; {int(data.quote_valid.sum())} quote-valid model rows, {n_fallback} assignment fallbacks, {n_no_quote} no-quote rows.')


if __name__=='__main__':main()
