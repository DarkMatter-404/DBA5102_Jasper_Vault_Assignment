# Run after executing aman/pp_pricing.ipynb with this appended cell:  import pickle; pickle.dump({'panels': panels}, open('panels_dump.pkl','wb'))
"""All team models on the same holdout months with the same demand rules, from Aman's per-order panels
(C0 = JV actual, R0 = reference, F0, F1 = locked model, M = Maksim, S = Subham) plus chris's book-skew layer
and a few F1 variants. Training months only; validation untouched."""
import pickle, numpy as np, pandas as pd
pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40)
import os; from pathlib import Path  # code_final path fix: work folder set at run time
SP = os.environ.get('AUDIT_WORK', str(Path(__file__).resolve().parent / 'work'))
P = pickle.load(open(f'{SP}/amanrun/aman/panels_dump.pkl', 'rb'))['panels']
bk = pd.read_pickle(f'{SP}/data/book.pkl')[['createdAt', 'q', 's_add', 'open_total_btc']].rename(columns={'q': 'quantity_BTC'})
bk['createdAt'] = pd.to_datetime(bk.createdAt)
def prep(t):
    t = t.copy(); t['createdAt'] = pd.to_datetime(t.createdAt)
    t = t.merge(bk, on=['createdAt', 'quantity_BTC'], how='left')
    t['skw'] = np.where(t.open_total_btc.fillna(0) >= 1, 1 + 0.3*np.maximum(-t.s_add.fillna(0), 0), 1.0)
    return t
def rules(rel):
    return {'no demand': np.ones_like(rel), 'cons e=1': np.where(rel > 1, rel**-1, 1), 'cons e=2 (Aman central)': np.where(rel > 1, rel**-2, 1),
            'symmetric e=1': np.minimum(rel**-1, 1.5), 'keep if <=1.10x': (rel <= 1.10).astype(float), 'keep if <=1.25x': (rel <= 1.25).astype(float)}
def ev(t, price, label):
    A = t.q_C0.values; pay = t.realizedProfit_USDC.values; rel = price/A
    out = {'policy': label, 'price/JV': np.average(rel, weights=A), 'cheaper%': 100*(rel < 1).mean()}
    for k, w in rules(rel).items(): out[k] = ((price - pay)*w).sum()
    w = rules(rel)['cons e=2 (Aman central)']; day = pd.Series((price - pay)*w).groupby(t.day.values).sum()
    out['worst day (e=2)'] = day.min(); out['LR (e=2)'] = (pay*w).sum()/(price*w).sum()
    return out
def table(t, title):
    rows = [ev(t, t.q_C0.values, 'C0  JV actual price'), ev(t, t.q_F1.values, 'F1  locked (Aman)'), ev(t, t.q_M.values, 'M   Maksim'), ev(t, t.q_S.values, 'S   Subham'),
            ev(t, (t.q_F1*t.skw).values, 'F1 + contrarian loading k=0.3'),
            ev(t, (t.q_F1*1.08).values, 'F1 x1.08 (undo the -7.6% reference bias)'),
            ev(t, (t.q_F1*1.08*t.skw).values, 'F1 x1.08 + contrarian loading'),
            ev(t, np.maximum(t.q_F1.values, np.minimum(t.q_M.values, 1.25*t.q_C0.values)), 'max(F1, min(M, 1.25xJV))  [level guard]'),
            ev(t, (np.sqrt(t.q_M*t.q_S)).clip(0.85*t.q_C0, 1.4*t.q_C0).values*t.skw.values, 'Blend M/S clipped [0.85,1.4] + loading (chris, 15 Oct)'),
            ev(t, t.q_C0.values*1.08, 'Flat x1.08'), ev(t, t.q_C0.values*1.17, 'Flat x1.17 (M total)')]
    R = pd.DataFrame(rows).set_index('policy'); print(f'\n=== {title}: {len(t)} orders, JV premium {t.q_C0.sum():,.0f}, payout {t.realizedProfit_USDC.sum():,.0f}')
    print(R.to_string(float_format=lambda x: f'{x:,.3f}' if abs(x) < 10 else f'{x:,.0f}'))
    return R
jul = prep(P['2026-07']); mj = prep(pd.concat([P['2026-05'], P['2026-06']], ignore_index=True))
print('book-layer join coverage (July):', jul.s_add.notna().mean().round(3))
Rj = table(jul, 'JULY (retrospective for everyone)'); Rm = table(mj, 'MAY + JUNE (Aman development months)')
# F1 by product in July: LR and price level
g = jul.groupby('productType').apply(lambda t: pd.Series({'n': len(t), 'F1/JV': t.q_F1.sum()/t.q_C0.sum(), 'LR_JV': t.realizedProfit_USDC.sum()/t.q_C0.sum(), 'LR_F1': t.realizedProfit_USDC.sum()/t.q_F1.sum(), 'LR_M': t.realizedProfit_USDC.sum()/t.q_M.sum()}), include_groups=False)
print('\nJuly by product:'); print(g.to_string(float_format=lambda x: f'{x:,.2f}'))
jul['band'] = pd.cut(jul.createdAt.dt.hour, [-1, 7, 12, 16, 23], labels=['00-07', '08-12', '13-16', '17-23'])
g2 = jul.groupby('band', observed=True).apply(lambda t: pd.Series({'F1/JV': t.q_F1.sum()/t.q_C0.sum(), 'LR_JV': t.realizedProfit_USDC.sum()/t.q_C0.sum(), 'LR_F1': t.realizedProfit_USDC.sum()/t.q_F1.sum()}), include_groups=False)
print('\nJuly by hour band:'); print(g2.to_string(float_format=lambda x: f'{x:,.2f}'))
Rj.to_csv(f'{SP}/holdout_july_all_models.csv'); Rm.to_csv(f'{SP}/holdout_mayjun_all_models.csv')
