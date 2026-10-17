"""Does the crowded-side effect survive when the open book is built WITHOUT closedAt?
Proxy book: earlier orders whose contractual expirationDate is after the new order's createdAt (held-to-expiry
assumption). This needs no outcome column, so it can be built on the blind file without touching closedAt.
Compared with Chris's book (uses earlier orders' actual close times).  Run: python3 -I book_proxy_check.py
"""
import pickle, numpy as np, pandas as pd
SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'
R = '/home/claude/dba5102_jasper_vault_assignment/'
t = pd.read_csv(R + 'data/with_base_premium/pp_transactions_training.csv', parse_dates=['createdAt', 'closedAt', 'expirationDate'])
t = t[t.realizedProfit_USDC.notna()].reset_index(drop=True)
t['notional'] = t.quantity_BTC * t.strikePrice
t = t.sort_values('createdAt').reset_index(drop=True)

def build_book(end_col):
    """open call / put BTC before each order using end_col as the time an earlier order stops counting."""
    ct = t.createdAt.values.astype('datetime64[ns]'); en = t[end_col].values.astype('datetime64[ns]')
    q = t.quantity_BTC.values; call = (t.optionType.values == 0)
    oc = np.zeros(len(t)); op = np.zeros(len(t))
    for i in range(len(t)):
        m = (ct < ct[i]) & (en > ct[i])
        oc[i] = q[m & call].sum(); op[i] = q[m & ~call].sum()
    return oc, op

for label, col in [('expiry proxy (no closedAt)', 'expirationDate'), ('actual close (Chris)', 'closedAt')]:
    oc, op = build_book(col)
    tot = oc + op
    imb = np.where(tot > 0, (oc - op) / np.where(tot > 0, tot, 1), 0.0)
    s_add = np.where(t.optionType.values == 0, imb, -imb)
    d = t.assign(tot=tot, s_add=s_add)
    d['side'] = np.where(tot < 1, 'book<1BTC', np.where(s_add > 0.5, 'strongly joins', np.where(s_add > 0.0, 'joins', np.where(s_add < -0.5, 'strongly opposes', np.where(s_add < 0, 'opposes', 'neutral')))))
    g = d.groupby('side').apply(lambda x: pd.Series(dict(n=len(x), prem=x.premiumAmount_USDC.sum(), LR=x.realizedProfit_USDC.sum() / x.premiumAmount_USDC.sum())), include_groups=False)
    print(f'\n== {label} ==')
    print(g.round(3).loc[[s for s in ['strongly opposes', 'opposes', 'neutral', 'joins', 'strongly joins', 'book<1BTC'] if s in g.index]])
    d['month'] = d.createdAt.dt.to_period('M').astype(str)
    d['cls'] = np.where(tot < 1, 'small', np.where(s_add > 0.2, 'joins', np.where(s_add < -0.2, 'opposes', 'neutral')))
    m = d[d.month >= '2026-05'].groupby(['month', 'cls']).apply(lambda x: x.realizedProfit_USDC.sum() / x.premiumAmount_USDC.sum(), include_groups=False).unstack().round(2)
    print('loss ratio by month (|s_add|>0.2 split):'); print(m)
    d.to_pickle(SP + f"audit/book_{'proxy' if col == 'expirationDate' else 'actual'}.pkl")
