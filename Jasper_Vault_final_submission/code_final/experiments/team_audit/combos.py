"""Deployable combination policies on the same panels (no use of JV's actual price as an input).
Book state uses the expiry-proxy book (no closedAt).  Run: python3 -I combos.py
"""
import pickle, numpy as np, pandas as pd
import os; from pathlib import Path  # code_final path fix: work folder set at run time
SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work')) + '/'
R = str(next(p for p in Path(__file__).resolve().parents if (p / 'data' / 'with_base_premium').is_dir())) + '/'
P = pickle.load(open(SP + 'amanrun/aman/panels_dump.pkl', 'rb'))['panels']
df = pd.concat(P.values(), ignore_index=True); df['pay'] = df.realizedProfit_USDC

# expiry-proxy book, keyed on original training row index
t = pd.read_csv(R + 'data/with_base_premium/pp_transactions_training.csv', parse_dates=['createdAt', 'expirationDate'])
t['row'] = t.index
ct = t.createdAt.values.astype('datetime64[ns]'); en = t.expirationDate.values.astype('datetime64[ns]')
q = t.quantity_BTC.values; call = t.optionType.values == 0
oc = np.zeros(len(t)); op = np.zeros(len(t))
for i in range(len(t)):
    m = (ct < ct[i]) & (en > ct[i]); oc[i] = q[m & call].sum(); op[i] = q[m & ~call].sum()
tot = oc + op; imb = np.where(tot > 0, (oc - op) / np.where(tot > 0, tot, 1), 0.0)
t['s_add'] = np.where(call, imb, -imb); t['book_btc'] = tot
df = df.merge(t[['row', 's_add', 'book_btc']], on='row', how='left')
load = np.where(df.book_btc >= 1, 1 + 0.3 * np.maximum(-df.s_add, 0), 1.0)
df['load'] = load
fv = df.fv.values; R0 = df.q_R0.values; M = df.q_M.values; S = df.q_S.values; F1 = df.q_F1.values

cands = {
    'C0': df.q_C0.values, 'F1': F1, 'M': M, 'S': S,
    'F1_t10': np.maximum(F1 * 1.10, fv),
    'F1_t10+load': np.maximum(F1 * 1.10, fv) * load,
    'M+load': M * load,
    'M_cap1.3R0_fl1.10FV': np.maximum(np.minimum(M, 1.3 * R0), 1.10 * fv),
    'M_cap1.4R0_fl1.10FV': np.maximum(np.minimum(M, 1.4 * R0), 1.10 * fv),
    'M_cap1.4R0+load': np.maximum(np.minimum(M, 1.4 * R0), 1.10 * fv) * load,
    'sqrt(M*S)': np.sqrt(M * S),
    'sqrt(M*S)_clip[.85,1.4]R0': np.clip(np.sqrt(M * S), 0.85 * R0, 1.4 * R0),
    'FV1.20': fv * 1.20, 'FV1.20+load': fv * 1.20 * load,
    'FV1.25_fl_base': M,  # alias check
}
def w(r, rule):
    return {'none': np.ones_like(r), 'cons_e1': np.minimum(1 / r, 1), 'cons_e2': np.minimum(r ** -2, 1),
            'keep_1.00': (r <= 1).astype(float), 'keep_1.10': (r <= 1.10).astype(float), 'keep_1.25': (r <= 1.25).astype(float)}[rule]
rows = []
for per, months in [('Jul', ['2026-07']), ('May+Jun', ['2026-05', '2026-06'])]:
    msk = df.month.isin(months).values; a = df.q_C0.values[msk]; pay = df.pay.values[msk]; day = df.day.values[msk]
    for nm, p in cands.items():
        p = p[msk]; r = p / a; d = dict(period=per, model=nm, price_vs_JV=p.sum() / a.sum(), cheaper=(p < a).mean(), LR=pay.sum() / p.sum())
        for rule in ['none', 'cons_e1', 'cons_e2', 'keep_1.00', 'keep_1.10', 'keep_1.25']:
            ww = w(r, rule); d[rule] = (ww * (p - pay)).sum()
        d['worst_day'] = pd.Series(w(r, 'cons_e2') * (p - pay)).groupby(day).sum().min()
        rows.append(d)
res = pd.DataFrame(rows); res.to_csv(SP + 'audit/combos_scores.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 20)
for per in ['Jul', 'May+Jun']:
    print(f'\n== {per} ==')
    print(res[res.period == per].set_index('model').drop(columns='period').round(3).to_string(float_format=lambda x: f'{x:,.3f}' if abs(x) < 10 else f'{x:,.0f}'))
print('\nload coverage: share of orders loaded', (load > 1).mean().round(3), ' mean load on loaded', load[load > 1].mean().round(3))
