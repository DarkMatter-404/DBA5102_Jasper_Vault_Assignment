#!/usr/bin/env python3
"""Small, declared revision family; original EN data, completed labels only.

Run with primary-runtime Python from repository workspace. Every experiment is
reported. April-May-June are rolling-origin development folds, and July is a
retrospective sensitivity sample because it has already been inspected.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = next((p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir()), Path(__file__).resolve().parents[4])  # code_final path fix
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # code_final: Jay's folder
import pp_pricing as pp
OUT = Path(__file__).resolve().parents[3] / 'output/v2/research/cost_family'
OUT.mkdir(parents=True, exist_ok=True)
CANDIDATES = ['baseline', 'recency60', 'tenor200', 'tenor500',
              'state_no_side_ridge10', 'state_no_side_ridge100', 'state_no_side_ridge10_blend25']
STATE = ['log_tenor', 'log_vol_ratio', 'signed_momentum_60']


def fit(train, name, cutoff):
    base = float(train.realizedProfit_USDC.sum() / train.premiumAmount_USDC.sum())
    model = {'name': name, 'global_ratio': base, 'n': len(train), 'cutoff': str(cutoff)}
    if name == 'baseline': return model
    if name == 'recency60':
        age = (pd.Timestamp(cutoff) - train.createdAt).dt.total_seconds()/86400
        w = np.exp(-np.log(2)*age/60.)
        model['global_ratio'] = float(np.sum(w*train.realizedProfit_USDC)/np.sum(w*train.premiumAmount_USDC))
        return model
    if name.startswith('tenor'):
        prior_orders = int(name[5:])
        # The prior is an exposure equal to 200 or 500 average-premium orders.
        # That prior carries the pooled claims/premium ratio; no side coefficient.
        prior_exposure = prior_orders * train.premiumAmount_USDC.mean()
        grouped = train.groupby('productType').agg(p=('premiumAmount_USDC', 'sum'), y=('realizedProfit_USDC', 'sum'))
        model['tenor_ratios'] = {int(k): float((r.y+prior_exposure*base)/(r.p+prior_exposure)) for k,r in grouped.iterrows()}
        model['prior_exposure_USDC'] = float(prior_exposure)
        return model
    alpha = 100. if 'ridge100' in name else 10.
    x0 = train[STATE].to_numpy(float)
    center, scale = x0.mean(axis=0), x0.std(axis=0)
    scale[scale<1e-10] = 1.
    x = np.column_stack([np.ones(len(train)), (x0-center)/scale])
    a = train.recorded_bps.to_numpy(float)
    y = train.payout_bps.to_numpy(float)
    w = train.notional_USDC.to_numpy(float)
    w = w / w.sum()
    def objective(beta):
        eta = np.log(a)+x@beta
        mu = np.exp(np.clip(eta,-30,30))
        val = np.sum(w*(mu-y*eta))+.5*alpha*np.sum(beta[1:]**2)
        grad = x.T@(w*(mu-y)); grad[1:] += alpha*beta[1:]
        return val, grad
    init = np.zeros(x.shape[1]); init[0] = np.log(base)
    opt = minimize(objective,init,jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-12,'gtol':1e-8})
    if not opt.success and np.max(np.abs(opt.jac)) > 1e-4: raise ValueError(opt.message)
    model.update(beta=opt.x.tolist(), center=center.tolist(), scale=scale.tolist(), alpha=alpha,
                 features=STATE, blend=.25 if name.endswith('blend25') else 1.)
    return model


def predict(model, data):
    ref = data.premiumAmount_USDC.to_numpy(float)
    pooled = ref*model['global_ratio']
    if 'tenor_ratios' in model:
        return ref*data.productType.map(model['tenor_ratios']).fillna(model['global_ratio']).to_numpy(float)
    if 'beta' in model:
        x = np.column_stack([np.ones(len(data)), (data[STATE].to_numpy()-model['center'])/model['scale']])
        corrected = ref*np.exp(np.clip(x@np.array(model['beta']),-15,15))
        return (1-model['blend'])*pooled+model['blend']*corrected
    return pooled


def main():
    protocol = {
        'candidates': CANDIDATES,
        'training': 'Expanding prior orders with createdAt AND closedAt before each monthly cutoff.',
        'development': ['2026-04', '2026-05', '2026-06'],
        'validation_labels': 'Only within-month orders settled before the following monthly cutoff.',
        'selection': 'Lowest equal-month mean weighted-Poisson-deviance ratio to baseline, among models with worst-fold deviance ratio <=1.10 and average RMSE ratio <=1; ties use baseline.',
        'July': 'Retrospective sensitivity only. This period was examined during previous work; no untouched holdout remains.',
        'pricing': 'Cost estimates are not prices. A cost prediction win alone does not establish commercial improvement.',
    }
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    data = pp.features(ROOT/'data/en/pp_transactions_training.csv', pp.read_market(ROOT/'data/en/btc_market_history.csv'))
    rows, models, predictions = [], {}, []
    for month in ['2026-04','2026-05','2026-06','2026-07']:
        start = pd.Timestamp(month+'-01',tz='UTC'); end = start+pd.offsets.MonthBegin(1)
        train = pp.train_before(data,start)
        valid = data[data.analysis_valid & data.createdAt.ge(start) & data.createdAt.lt(end)]
        # Original July report included eventual labels through August 1. Use
        # the same original July evaluation sample; development folds require
        # labels known before the next fold starts.
        if month != '2026-07': valid = valid[valid.closedAt.lt(end)]
        for name in CANDIDATES:
            model = fit(train,name,start)
            pred = predict(model,valid)
            rows.append({'period':month,'sample_role':'retrospective' if month=='2026-07' else 'development',
                         'model':name,'n_train':len(train), **pp.metrics(valid,pred)})
            models[month+'_'+name] = model
            detail = valid[['source_row','createdAt','closedAt','day','productType','optionType','premiumAmount_USDC','realizedProfit_USDC','notional_USDC']].copy()
            detail['predicted_cost_USDC'] = pred; detail['period'] = month; detail['model'] = name
            predictions.append(detail)
    result = pd.DataFrame(rows)
    result.to_csv(OUT/'all_fold_metrics.csv',index=False)
    pred = pd.concat(predictions,ignore_index=True); pred.to_csv(OUT/'all_predictions.csv',index=False)
    baselines = result[result.model.eq('baseline')].set_index('period')
    result['deviance_ratio_to_baseline'] = result.apply(lambda r:r.notional_weighted_poisson_deviance/baselines.loc[r.period,'notional_weighted_poisson_deviance'],axis=1)
    result['rmse_ratio_to_baseline'] = result.apply(lambda r:r.RMSE_USDC/baselines.loc[r.period,'RMSE_USDC'],axis=1)
    selection = result[result.sample_role.eq('development')].groupby('model').agg(
        mean_deviance_ratio=('deviance_ratio_to_baseline','mean'),
        worst_deviance_ratio=('deviance_ratio_to_baseline','max'),
        mean_rmse_ratio=('rmse_ratio_to_baseline','mean'))
    selection['eligible'] = (selection.worst_deviance_ratio<=1.10)&(selection.mean_rmse_ratio<=1)
    selection = selection.sort_values('mean_deviance_ratio')
    selection.to_csv(OUT/'development_selection.csv')
    chosen = selection[selection.eligible].index[0]
    (OUT/'fitted_models.json').write_text(json.dumps(models,indent=2))
    (OUT/'selected.json').write_text(json.dumps({'selected':chosen,'warning':protocol['July'],
        'frozen_July_model':models['2026-07_'+chosen]},indent=2))
    print(selection.to_string())
    print('\nALL FOLD RESULTS')
    print(result[['period','model','n_train','n','RMSE_USDC','notional_weighted_poisson_deviance','calibration_ratio_predicted_to_actual']].to_string(index=False))
    print('\nSelected on April-May-June:',chosen)


if __name__ == '__main__': main()
