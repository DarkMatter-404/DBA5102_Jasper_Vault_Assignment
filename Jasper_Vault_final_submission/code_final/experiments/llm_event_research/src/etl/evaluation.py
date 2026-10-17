"""Frozen pricing policy, demand sensitivities and paired chronological comparisons."""
import numpy as np
import pandas as pd

def premiums(d,m,lam):return (1+m)*d.mean_claim + lam*(d.es95-d.mean_claim)

def retained(price,actual,elasticity):
    # We observe purchases, not rejected quotes: sensitivity, NOT fitted demand.
    return np.minimum(1,np.maximum(np.asarray(price)/np.asarray(actual),1e-9)**(-elasticity))

def policy_search(dev):
    rows=[]
    for m in [.10,.25,.50]:
        for lam in [0,.025,.05,.10]:
            p=premiums(dev,m,lam); actual=dev.premiumAmount_USDC
            total=float(p.sum()/actual.sum()); p95=float(np.quantile(p/actual,.95))
            gains=[float((retained(p,actual,e)*(p-dev.realizedProfit_USDC)).sum()-(actual-dev.realizedProfit_USDC).sum()) for e in [0,2,4]]
            rows.append({'m':m,'lambda':lam,'total_quote_ratio':total,'p95_quote_ratio':p95,
                         'gain_e0':gains[0],'gain_e2':gains[1],'gain_e4':gains[2],
                         'worst_gain':min(gains),'feasible':.8<=total<=1.2 and p95<=2})
    tab=pd.DataFrame(rows); feasible=tab[tab.feasible]
    if len(feasible):r=feasible.sort_values('worst_gain',ascending=False).iloc[0]; m,lam=float(r['m']),float(r['lambda'])
    else:m,lam=.25,.05
    return {'m':m,'lambda':lam,'development_gate_passed':bool(len(feasible)),
            'selection':'market-only May/June; no test retuning','operating_cost_assumed':0},tab

def apply_policy(d,policy):
    d=d.copy(); d['quoted_premium']=premiums(d,policy['m'],policy['lambda'])
    d['quote_per_BTC']=d.quoted_premium/d.quantity_BTC
    return d

def metrics(d):
    actual=d.premiumAmount_USDC; y=d.realizedProfit_USDC; p=d.quoted_premium
    daily=(p-y).groupby(pd.to_datetime(d.createdAt,utc=True).dt.date).sum()
    out={'orders':len(d),'actual_premium':float(actual.sum()),'payout':float(y.sum()),
        'actual_gross_profit':float((actual-y).sum()),'quoted_total':float(p.sum()),
        'quote_ratio_total':float(p.sum()/actual.sum()),'quote_ratio_median':float((p/actual).median()),
        'quote_ratio_p95':float((p/actual).quantile(.95)),
        'expected_claim_total':float(d.mean_claim.sum()),'mean_claim_mae':float(abs(d.mean_claim-y).mean()),
        'claim_calibration_ratio':float(d.mean_claim.sum()/y.sum()),
        'brier':float(((d.payout_probability-(y>1e-8))**2).mean()),
        'crps':float(d.crps.mean()),'predicted_payout_rate':float(d.payout_probability.mean()),
        'observed_payout_rate':float((y>1e-8).mean()),
        'central90_coverage':float(((y>=d.q05)&(y<=d.q95)).mean()),
        'event_orders':int((d.event_weight>0).sum()),'event_days':int(pd.to_datetime(d[d.event_weight>0].createdAt,utc=True).dt.date.nunique()),
        'event_ids':int(d.loc[d.event_weight>0,'event_id'].nunique()),
        'fresh_market_orders':int(d.fresh_market.sum()),
        'worst_daily_gross_profit':float(daily.min()),
        'worst5pct_daily_mean':float(daily.nsmallest(max(1,int(np.ceil(.05*len(daily))))).mean())}
    flat=actual*(p.sum()/actual.sum())
    for e in [0,2,4]:
        profit=float((retained(p,actual,e)*(p-y)).sum())
        flatprofit=float((retained(flat,actual,e)*(flat-y)).sum())
        out.update({f'gross_profit_e{e}':profit,f'gain_vs_actual_e{e}':profit-float((actual-y).sum()),
                    f'flat_same_total_profit_e{e}':flatprofit,f'gain_vs_flat_e{e}':profit-flatprofit,
                    f'retained_fraction_e{e}':float(retained(p,actual,e).mean())})
    matched=d.apiBasePrice_per_BTC_USDC.notna()
    b=d[matched]
    out.update({'api_comparison_orders':len(b),'api_gross_profit_matched':float((b.apiBasePrice_per_BTC_USDC*b.quantity_BTC-b.realizedProfit_USDC).sum()),
        'actual_gross_profit_matched':float((b.premiumAmount_USDC-b.realizedProfit_USDC).sum()),
        'model_gross_profit_matched':float((b.quoted_premium-b.realizedProfit_USDC).sum())})
    return out

def paired_bootstrap(test,seed=417,nboot=2000):
    a=test[test.arm=='market_only'].set_index('row_id').sort_index()
    b=test[test.arm=='verified_research'].set_index('row_id').sort_index()
    assert a.index.equals(b.index)
    z=pd.DataFrame({'day':pd.to_datetime(a.createdAt,utc=True).dt.date,'n':1,
        'crps_delta':b.crps-a.crps,'brier_delta':(b.payout_probability-(b.realizedProfit_USDC>1e-8))**2-(a.payout_probability-(a.realizedProfit_USDC>1e-8))**2})
    for e in [0,2,4]:
        z[f'profit_delta_e{e}']=retained(b.quoted_premium,b.premiumAmount_USDC,e)*(b.quoted_premium-b.realizedProfit_USDC)-retained(a.quoted_premium,a.premiumAmount_USDC,e)*(a.quoted_premium-a.realizedProfit_USDC)
    day=z.groupby('day').sum(); rng=np.random.default_rng(seed)
    ix=rng.integers(0,len(day),(nboot,len(day))); sums=day.to_numpy()[ix].sum(axis=1)
    result={'days':len(day),'bootstrap_samples':nboot,'confidence_level':.9,'method':'paired UTC-day bootstrap; overlapping multi-day shocks can reduce effective sample size'}
    for col in day.columns[1:]:
        j=day.columns.get_loc(col); vals=sums[:,j]/sums[:,0] if col in ['crps_delta','brier_delta'] else sums[:,j]
        est=float(day[col].sum()/day.n.sum()) if col in ['crps_delta','brier_delta'] else float(day[col].sum())
        result[col]={'estimate':est,'low90':float(np.quantile(vals,.05)),'high90':float(np.quantile(vals,.95))}
    return result
