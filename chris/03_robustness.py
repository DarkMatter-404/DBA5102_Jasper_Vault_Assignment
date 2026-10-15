"""Robustness of the 'crowded side pays less' result.

Alternative explanations checked:
 A. Behaviour, not risk: orders on the crowded side are closed early with zero payout (users close the perp and
    forfeit protection), so realised payout is low although the risk was not. Test with the European counterfactual
    (intrinsic value at expiry) instead of the realised payout.
 B. Size: driven by a few large orders. Test by size tier and on equal-weighted (per-order) ratios.
 C. Mechanism: users herd into protection after the move (book follows past returns) and the move then partly
    reverts. Test with past-return conditioning.
"""
import sys, numpy as np, pandas as pd
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 30); pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
b = pd.read_pickle(sys.argv[1]); s = pd.read_pickle(sys.argv[2])[['createdAt', 'intr_exp', 'early', 'size_b', 'S_exp']]
d = b.merge(s, on='createdAt', how='left')
d = d[d.open_total_btc >= 1.0].copy()
d['cls'] = pd.cut(d.s_add, [-1.01, -0.15, 0.15, 1.01], labels=['reduces', 'neutral', 'adds'])
d['forfeit'] = d.early & (d.pay == 0) & (d.intr_exp > 0)   # closed early, got nothing, but would have paid at expiry
def summ(g):
    out = g.agg(n=('prem', 'size'), prem=('prem', 'sum'), pay=('pay', 'sum'), eur=('intr_exp', 'sum'), fair=('fair_har', 'sum'),
                early_share=('early', 'mean'), forfeit_share=('forfeit', 'mean'))
    out['pay/fair'] = out.pay/out.fair; out['european/fair'] = out.eur/out.fair; out['LR'] = out.pay/out.prem; out['LR_european'] = out.eur/out.prem
    return out
print('=== A. realised vs European counterfactual, by class')
print(summ(d.groupby('cls', observed=True))[['n', 'prem', 'LR', 'LR_european', 'pay/fair', 'european/fair', 'early_share', 'forfeit_share']])
print('\n=== B1. by size tier x class: pay/fair (premium-weighted)')
g = summ(d.groupby(['size_b', 'cls'], observed=True)); print(g['pay/fair'].unstack('cls').round(2)); print('premium:'); print(g['prem'].unstack('cls').round(0))
print('\n=== B2. equal-weighted per-order ratio pay/fair (median and mean, per class)')
d['r'] = d.pay/d.fair_har
print(d.groupby('cls', observed=True).r.agg(['median', 'mean', lambda x: (x > 0).mean()]).rename(columns={'<lambda_0>': 'share_paid'}).round(3))
print('\n=== B3. drop the single largest day by premium in each month: pay/fair by class')
top_days = d.assign(date=d.createdAt.dt.date).groupby(['month', 'date']).prem.sum().groupby('month').idxmax().apply(lambda x: x[1])
dd = d[~d.createdAt.dt.date.isin(set(top_days))]
print(summ(dd.groupby('cls', observed=True))[['n', 'prem', 'pay/fair', 'european/fair']])
print('\n=== C1. how the book forms: book imbalance vs past 24h return (call-heavy after rises?)')
d['r24_b'] = pd.cut(d.ret24h, [-99, -2, -0.5, 0.5, 2, 99], labels=['<-2%', '-2..-0.5', '-0.5..0.5', '0.5..2', '>2%'])
print(d.groupby('r24_b', observed=True).agg(n=('imb', 'size'), mean_imb=('imb', 'mean'), call_share_of_new_orders=('is_call', 'mean')).round(3))
print('\n=== C2. forward return to expiry (bp, mean) by book imbalance bucket: does the crowd get the direction right?')
d['imb_b'] = pd.cut(d.imb, [-1.01, -0.5, -0.15, 0.15, 0.5, 1.01], labels=['put-heavy', 'put-lean', 'balanced', 'call-lean', 'call-heavy'])
d['fwd_bp'] = np.log(d.S_exp/d.strikePrice)*1e4
print(d.groupby('imb_b', observed=True).agg(n=('fwd_bp', 'size'), mean_fwd_bp=('fwd_bp', 'mean'), median_fwd_bp=('fwd_bp', 'median'), share_up=('fwd_bp', lambda x: (x > 0).mean())).round(2))
print('(call-heavy book = many shorts protected; if the crowd were right BTC would rise, mean_fwd_bp > 0)')
print('\n=== C3. the contrarian orders: who are they? size and product mix of "reduces" vs "adds"')
print(pd.crosstab(d.cls, d.size_b, values=d.prem, aggfunc='sum', normalize='index').round(2))
print(pd.crosstab(d.cls, d.productType, values=d.prem, aggfunc='sum', normalize='index').round(2))
