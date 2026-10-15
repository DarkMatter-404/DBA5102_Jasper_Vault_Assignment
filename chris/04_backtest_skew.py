"""Book-skew pricing layer: backtest on training orders.

Rule (a layer on top of any base price):
    multiplier = 1 + k_contra * max(-s, 0) - k_crowd * max(s, 0)      when the open book >= MIN_BOOK BTC, else 1
where s = signed imbalance from the order's perspective (s > 0: the order adds to the dominant open side).
k_contra raises the price of orders that go against the crowd (they paid 1.3x fair value in training);
k_crowd discounts orders that join the crowd (they paid 0.8-0.9x fair value) - this half is the risky one.

Protocol: parameters chosen on February-June, reported on July. The pattern itself was seen on all months,
so July tests the parameter choice, not the discovery; the per-month table in 02/03 shows July alone agrees.
Demand rules follow Maksim's conventions so results are comparable across the team:
  conservative(e): rises lose orders with weight (P/A)^-e, cuts win none
  symmetric(e):    rises lose and cuts win, weight (P/A)^-e capped at 1.5
Risk metric added: peak |net delta| of the accepted book (BTC), because a crowd discount sells more of one side.
"""
import sys, itertools, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
d = pd.read_pickle(sys.argv[1]).sort_values('createdAt').reset_index(drop=True)
MIN_BOOK = 1.0
d['date'] = d.createdAt.dt.date
tr = d.createdAt < '2026-07-01'; te = ~tr
def skew_mult(df, k_contra, k_crowd):
    s = df.s_add.values; on = (df.open_total_btc.values >= MIN_BOOK)
    return np.where(on, 1 + k_contra*np.maximum(-s, 0) - k_crowd*np.maximum(s, 0), 1.0)
def peak_net_delta(df, w):
    """peak absolute net delta (BTC) of the book when each order is kept with weight w (expected volume)."""
    t0 = df.createdAt.values; t1 = df.closedAt.values; sign = np.where(df.is_call.values, -0.5, 0.5)*df.q.values*w
    ev = pd.DataFrame({'t': np.concatenate([t0, t1]), 'd': np.concatenate([sign, -sign])}).sort_values('t')
    return np.abs(ev.d.cumsum()).max()
def evaluate(df, price, label):
    A = df.prem.values; pay = df.pay.values; rel = price/A; rows = []
    for rule, e in [('none', 0), ('conservative', 1), ('conservative', 2), ('symmetric', 1)]:
        if rule == 'none': w = np.ones_like(rel)
        elif rule == 'conservative': w = np.where(rel > 1, rel**(-e), 1.0)
        else: w = np.minimum(rel**(-e), 1.5)
        prem_c = (price*w).sum(); pay_c = (pay*w).sum()
        day = pd.DataFrame({'p': (price - pay)*w, 'dt': df.date}).groupby('dt').p.sum()
        dd = (day.cumsum().cummax() - day.cumsum()).max()
        rows.append(dict(policy=label, rule=f'{rule}{e if rule!="none" else ""}', premium=prem_c, profit=prem_c - pay_c, LR=pay_c/prem_c,
                         prem_kept=prem_c/A.sum(), orders_kept=w.mean(), avg_rel=np.average(rel, weights=A), share_cheaper=(rel < 1).mean(),
                         worst_day=day.min(), max_dd=dd, sd_day=day.std(), peak_delta_btc=peak_net_delta(df, w)))
    return rows
# ---- 1. choose k on Feb-Jun (conservative e=1 profit), grid
grid = []
for kc, kw in itertools.product([0, 0.1, 0.2, 0.3, 0.4, 0.5], [0, 0.05, 0.1, 0.15, 0.2]):
    r = evaluate(d[tr], d[tr].prem.values*skew_mult(d[tr], kc, kw), f'k_contra={kc},k_crowd={kw}')
    grid.append(dict(k_contra=kc, k_crowd=kw, profit_cons1=r[1]['profit'], profit_cons2=r[2]['profit'], profit_sym1=r[3]['profit'], prem_kept=r[1]['prem_kept'], peak_delta=r[3]['peak_delta_btc']))
G = pd.DataFrame(grid); base_tr = evaluate(d[tr], d[tr].prem.values, 'actual')[1]['profit']
print('=== Feb-Jun: actual pricing profit (conservative e=1):', round(base_tr))
print('profit under conservative e=1, by k (rows k_contra, cols k_crowd):'); print(G.pivot(index='k_contra', columns='k_crowd', values='profit_cons1').round(0))
print('profit under symmetric e=1 (cuts win volume):'); print(G.pivot(index='k_contra', columns='k_crowd', values='profit_sym1').round(0))
print('peak |net delta| BTC under symmetric e=1:'); print(G.pivot(index='k_contra', columns='k_crowd', values='peak_delta').round(2))
best = G.sort_values('profit_cons1', ascending=False).iloc[0]; print('\nchosen on Feb-Jun (conservative e=1):', best.to_dict())
# ---- 2. July test
t = d[te]
res = evaluate(t, t.prem.values, 'actual pricing')
kc, kw = best.k_contra, best.k_crowd
m_full = skew_mult(t, kc, kw); res += evaluate(t, t.prem.values*m_full, f'skew k_contra={kc} k_crowd={kw}')
m_contra = skew_mult(t, kc, 0.0); res += evaluate(t, t.prem.values*m_contra, f'contrarian loading only k={kc}')
m_sym = skew_mult(t, 0.3, 0.15); res += evaluate(t, t.prem.values*m_sym, 'symmetric skew 0.3/0.15')
# flat raise matched to the same total premium as the contrarian-only policy (no demand response)
flat = (t.prem*m_contra).sum()/t.prem.sum(); res += evaluate(t, t.prem.values*flat, f'flat x{flat:.3f} (same total as contrarian-only)')
R = pd.DataFrame(res)
print('\n=== July (out of sample for the parameter choice). Layer applied on top of actual prices.')
print(R.to_string(index=False))
# ---- 3. same layer on a fair-value base (Black-Scholes with HAR vol forecast fitted Feb-Jun, x1.25) to show it is additive
fv = t.fair_har.values*1.25
res2 = evaluate(t, fv, 'fair value x1.25 (no skew)') + evaluate(t, fv*m_contra, f'fair value x1.25 + contrarian loading k={kc}') + evaluate(t, fv*m_sym, 'fair value x1.25 + symmetric skew 0.3/0.15')
print('\n=== July, layer on a fair-value base instead of actual prices'); print(pd.DataFrame(res2).to_string(index=False))
# ---- 4. where the loading lands: share of July orders / premium touched
touched = (m_contra > 1); print(f'\ncontrarian loading applied to {touched.mean():.1%} of July orders, {t.prem[touched].sum()/t.prem.sum():.1%} of premium; their realised LR under actual prices: {t.pay[touched].sum()/t.prem[touched].sum():.2f} vs {t.pay[~touched].sum()/t.prem[~touched].sum():.2f} for the rest')
out = t[['createdAt', 'productType', 'is_call', 'q', 'prem', 'pay', 'open_total_btc', 'imb', 's_add']].copy(); out['mult_contra'] = m_contra; out['mult_sym'] = m_sym
out.to_csv('results/july_skew_orders.csv', index=False); R.to_csv('results/july_policies.csv', index=False); G.to_csv('results/grid_febjun.csv', index=False)
