"""Reconstruct Jasper Vault's open protection book at the moment each training order was created.

Only training orders are used. For order i, the book is the set of orders j created before i and
still open at i's creation time (closedAt_j > createdAt_i). This is information JV has at quote time:
whether a protection is still open is known; nothing about its eventual payout is used.

Outputs: book.pkl with per-order book state and flow features.
"""
import sys, numpy as np, pandas as pd
IN, OUT = sys.argv[1], sys.argv[2]
d = pd.read_pickle(IN).sort_values('createdAt').reset_index(drop=True)
d = d[['createdAt','closedAt','expirationDate','productType','is_call','q','strikePrice','S0','prem','pay','fair_har','sig_hat',
       'rv1h','rv24h','ret1h','ret4h','ret24h','hour_utc','dow','band','month','otm_pct']].copy()
t_open = d.createdAt.values.astype('datetime64[ns]').astype('int64')
t_close = d.closedAt.values.astype('datetime64[ns]').astype('int64')
q = d.q.values; call = d.is_call.values.astype(bool); usd = (d.q*d.strikePrice).values
n = len(d)
C = np.zeros(n); P = np.zeros(n); Cusd = np.zeros(n); Pusd = np.zeros(n); nopen = np.zeros(n, dtype=int)
flow4_c = np.zeros(n); flow4_p = np.zeros(n); flow24_c = np.zeros(n); flow24_p = np.zeros(n)
H4 = 4*3600*10**9; H24 = 24*3600*10**9
for i in range(n):
    ti = t_open[i]
    # open book strictly before this order: created earlier (ties: earlier index) and not yet closed
    m = (np.arange(n) < i) & (t_close > ti)
    C[i] = q[m & call].sum(); P[i] = q[m & ~call].sum(); Cusd[i] = usd[m & call].sum(); Pusd[i] = usd[m & ~call].sum(); nopen[i] = m.sum()
    f4 = (np.arange(n) < i) & (t_open >= ti - H4); f24 = (np.arange(n) < i) & (t_open >= ti - H24)
    flow4_c[i] = q[f4 & call].sum(); flow4_p[i] = q[f4 & ~call].sum(); flow24_c[i] = q[f24 & call].sum(); flow24_p[i] = q[f24 & ~call].sum()
d['open_call_btc']=C; d['open_put_btc']=P; d['open_call_usd']=Cusd; d['open_put_usd']=Pusd; d['n_open']=nopen
d['open_total_btc']=C+P
# imbalance in [-1,1]: +1 = book is all calls (JV loses if BTC rises), -1 = all puts
d['imb'] = np.where(C+P>0, (C-P)/np.maximum(C+P,1e-12), 0.0)
# JV net delta in BTC (ATM delta ~0.5): short call -> -0.5q, short put -> +0.5q
d['jv_net_delta_btc'] = 0.5*(P - C)
# signed score from the perspective of the incoming order: >0 means the order adds to the dominant side
d['s_add'] = np.where(call, d.imb, -d.imb)
d['flow4_net'] = flow4_c - flow4_p; d['flow24_net'] = flow24_c - flow24_p
d['flow4_imb'] = np.where(flow4_c+flow4_p>0, (flow4_c-flow4_p)/np.maximum(flow4_c+flow4_p,1e-12), 0.0)
d['flow24_imb'] = np.where(flow24_c+flow24_p>0, (flow24_c-flow24_p)/np.maximum(flow24_c+flow24_p,1e-12), 0.0)
d['s_flow24'] = np.where(call, d.flow24_imb, -d.flow24_imb)
d.to_pickle(OUT)
pd.set_option('display.width',200); pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
print('orders', n)
print(d[['open_total_btc','n_open','imb','jv_net_delta_btc','s_add','flow24_imb']].describe(percentiles=[.05,.25,.5,.75,.95]).T)
print('\nshare of orders with |imb|>0.5 and open book >= 1 BTC:', ((d.imb.abs()>0.5)&(d.open_total_btc>=1)).mean().round(3))
print('share of premium arriving when |imb|>0.5 and open book >= 1 BTC:', (d.prem[(d.imb.abs()>0.5)&(d.open_total_btc>=1)].sum()/d.prem.sum()).round(3))
print('\nopen book size by month (BTC, mean / p95):'); print(d.groupby('month').open_total_btc.agg(['mean', lambda s: s.quantile(.95), 'max']).round(2))
print('\nmean |imb| by month (premium-weighted):'); print(d.groupby('month').apply(lambda t: np.average(t.imb.abs(), weights=t.prem), include_groups=False).round(3))
