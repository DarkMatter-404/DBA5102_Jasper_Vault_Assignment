"""Build the per-order feature table used by the book analysis from the supplied files.

Usage:  python 00_prepare_features.py ../data/with_base_premium/pp_transactions_training.csv \
                                      ../data/with_base_premium/btc_market_history.csv  work/orders.pkl

Steps
 1. Join every order to the one-minute BTC candles: spot at creation (open of the creation minute), price at close
    and at expiry, trailing realised volatility over 1h/4h/24h/7d, trailing returns, time-of-day.
 2. Direction-neutral fair value per order: Black-Scholes (r = 0) with a volatility forecast from a HAR-style
    regression of log realised volatility over the protection window on the trailing volatilities, hour of day,
    weekend flag and product length. The regression is fitted on orders created before 1 July 2026 only and
    scaled so that fitted fair values match payouts on those orders; later orders are out of sample.
 3. Exclusions: 54 orders without a recorded outcome; orders whose expiry precedes creation or whose duration is
    more than 50 percent away from the product length (data errors).
Only data available before each order's creation enters its features; the payout at close is used only as the
outcome. No validation data is read.
"""
import sys, numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LinearRegression
orders_csv, btc_csv, out = sys.argv[1], sys.argv[2], sys.argv[3]
df = pd.read_csv(orders_csv)
for c in ['createdAt', 'closedAt', 'expirationDate']: df[c] = pd.to_datetime(df[c])
btc = pd.read_csv(btc_csv, usecols=['open_time_utc', 'open', 'high', 'low', 'close'])
btc['t'] = pd.to_datetime(btc.open_time_utc, utc=True).dt.tz_localize(None); btc = btc.sort_values('t').reset_index(drop=True)
t = btc.t.values; close = btc.close.values; openp = btc.open.values
def idx_at(ts): return np.searchsorted(t, ts.values.astype('datetime64[ns]'), side='right') - 1
df['dur_s'] = (df.expirationDate - df.createdAt).dt.total_seconds()
bad = (df.dur_s < 0) | ((df.dur_s - df.productType).abs() > 0.5*df.productType) | df.realizedProfit_USDC.isna()
print('excluded orders:', int(bad.sum()), 'of', len(df)); df = df[~bad].copy()
i0 = idx_at(df.createdAt); iexp = idx_at(df.expirationDate); icl = idx_at(df.closedAt)
df['S0'] = openp[i0]; df['S_exp'] = close[iexp]; df['S_close'] = close[icl]
df['is_call'] = df.optionType == 0; df['q'] = df.quantity_BTC; df['prem'] = df.premiumAmount_USDC; df['pay'] = df.realizedProfit_USDC
df['otm_pct'] = np.where(df.is_call, df.strikePrice/df.S0 - 1, 1 - df.strikePrice/df.S0)*100
lr2 = np.nan_to_num(np.diff(np.log(close), prepend=np.nan)**2); cs = np.cumsum(lr2)
def rv(w): a = np.clip(i0 - w, 0, None); return np.sqrt((cs[i0] - cs[a])/w*525600)
for w, name in [(60, 'rv1h'), (240, 'rv4h'), (1440, 'rv24h'), (10080, 'rv7d')]: df[name] = rv(w)
dur_min = np.maximum((df.productType//60).values, 1); iend = np.minimum(i0 + dur_min, len(close) - 1)
df['rv_fwd'] = np.sqrt((cs[iend] - cs[i0])/dur_min*525600)          # realised over the window: target of the forecast, never a feature
def ret(w): a = np.clip(i0 - w, 0, None); return (close[i0]/close[a] - 1)*100
df['ret1h'] = ret(60); df['ret4h'] = ret(240); df['ret24h'] = ret(1440)
df['hour_utc'] = df.createdAt.dt.hour; df['dow'] = df.createdAt.dt.dayofweek; df['month'] = df.createdAt.dt.to_period('M')
df['band'] = pd.cut(df.hour_utc, [-1, 7, 12, 16, 23], labels=['00-07', '08-12', '13-16', '17-23'])
df['size_b'] = pd.cut(df.q, [0, 0.002, 0.01, 0.05, 0.2, 0.5, 1, 10])
df['early'] = (df.expirationDate - df.closedAt).dt.total_seconds() > 60
df['intr_exp'] = np.where(df.is_call, np.maximum(df.S_exp - df.strikePrice, 0), np.maximum(df.strikePrice - df.S_exp, 0))*df.q
# volatility forecast (HAR + hour + weekend + product), fitted before 1 June 2026
X = pd.DataFrame({'l1': np.log(df.rv1h), 'l4': np.log(df.rv4h), 'l24': np.log(df.rv24h), 'l7': np.log(df.rv7d)})
X = pd.concat([X, pd.get_dummies(df.hour_utc, prefix='h', drop_first=True).astype(float), pd.get_dummies(df.productType, prefix='p', drop_first=True).astype(float), (df.dow >= 5).astype(float).rename('wknd')], axis=1)
fit = (df.createdAt < '2026-07-01').values  # HAR fitted on Feb-Jun (July is the holdout month)
har = LinearRegression().fit(X[fit], np.log(df.rv_fwd[fit])); df['sig_hat'] = np.exp(har.predict(X))
def bs(S, K, T, sig, call):
    T = np.maximum(T, 1e-9); sig = np.maximum(sig, 1e-6); d1 = (np.log(S/K) + 0.5*sig**2*T)/(sig*np.sqrt(T)); d2 = d1 - sig*np.sqrt(T)
    return np.where(call, S*norm.cdf(d1) - K*norm.cdf(d2), K*norm.cdf(-d2) - S*norm.cdf(-d1))
T = df.productType.values/(365*24*3600)
fair0 = bs(df.S0.values, df.strikePrice.values, T, df.sig_hat.values, df.is_call.values)*df.q.values
k = df.pay[fit].sum()/fair0[fit].sum(); df['fair_har'] = fair0*k
print('fair-value scale factor (payout / BS on fit period):', round(k, 3))
df = df.sort_values('createdAt').reset_index(drop=True)
df.to_pickle(out); print('wrote', out, df.shape)
