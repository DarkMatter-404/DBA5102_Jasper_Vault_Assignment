"""Is the contrarian loading better than a flat raise of the same size? (the only question that matters once
a demand rule with elasticity <= 1 makes any price rise profitable)

For k in a grid: targeted = actual price x (1 + k*max(-s,0)) on books >= 1 BTC; flat = actual price x c with c chosen
so both have the same total premium before demand response. Compared on Feb-Jun and on July under several rules,
including a strict threshold (order lost if priced more than 25% above today) that punishes large targeted rises.
Also: Spearman rank correlation between price and payout (does the layer order risk better?).
"""
import sys, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
d = pd.read_pickle(sys.argv[1]).sort_values('createdAt').reset_index(drop=True); d['date'] = d.createdAt.dt.date
def mult(df, k): s = df.s_add.values; return np.where(df.open_total_btc.values >= 1.0, 1 + k*np.maximum(-s, 0), 1.0)
def profit(df, price, rule):
    A = df.prem.values; rel = price/A
    if rule == 'cons1': w = np.where(rel > 1, rel**-1, 1.0)
    elif rule == 'cons2': w = np.where(rel > 1, rel**-2, 1.0)
    elif rule == 'cons3': w = np.where(rel > 1, rel**-3, 1.0)
    elif rule == 'strict25': w = (rel <= 1.25).astype(float)
    elif rule == 'strict10': w = (rel <= 1.10).astype(float)
    return ((price - df.pay.values)*w).sum(), w.mean()
rows = []
for period, df in [('Feb-Jun', d[d.createdAt < '2026-07-01']), ('Jul', d[d.createdAt >= '2026-07-01'])]:
    base = {r: profit(df, df.prem.values, r)[0] for r in ['cons1', 'cons2', 'cons3', 'strict25', 'strict10']}
    for k in [0.2, 0.3, 0.5]:
        m = mult(df, k); c = (df.prem*m).sum()/df.prem.sum()
        for r in ['cons1', 'cons2', 'cons3', 'strict25', 'strict10']:
            pt, wt = profit(df, df.prem.values*m, r); pf, wf = profit(df, df.prem.values*c, r)
            rows.append(dict(period=period, k=k, flat_equiv=round(c, 3), rule=r, actual=base[r], targeted=pt, flat=pf, targeted_minus_flat=pt - pf, orders_kept_targeted=wt, orders_kept_flat=wf))
R = pd.DataFrame(rows); print(R.to_string(index=False))
print('\n=== ranking: Spearman(price, payout)')
for period, df in [('Feb-Jun', d[d.createdAt < '2026-07-01']), ('Jul', d[d.createdAt >= '2026-07-01'])]:
    print(period, ' actual:', round(df[['prem', 'pay']].corr('spearman').iloc[0, 1], 4), ' actual x skew(0.5):', round(pd.Series(df.prem.values*mult(df, 0.5)).corr(df.pay.reset_index(drop=True), method='spearman'), 4),
          ' fair:', round(df[['fair_har', 'pay']].corr('spearman').iloc[0, 1], 4), ' fair x skew(0.5):', round(pd.Series(df.fair_har.values*mult(df, 0.5)).corr(df.pay.reset_index(drop=True), method='spearman'), 4))
print('\n=== July: loss ratio by class under actual prices (is the signal still there out of sample?)')
j = d[(d.createdAt >= '2026-07-01') & (d.open_total_btc >= 1)].copy(); j['cls'] = pd.cut(j.s_add, [-1.01, -0.15, 0.15, 1.01], labels=['reduces', 'neutral', 'adds'])
g = j.groupby('cls', observed=True).agg(n=('prem', 'size'), prem=('prem', 'sum'), pay=('pay', 'sum'), fair=('fair_har', 'sum')); g['LR'] = g.pay/g.prem; g['pay/fair'] = g.pay/g.fair; print(g)
R.to_csv('results/targeted_vs_flat.csv', index=False)
