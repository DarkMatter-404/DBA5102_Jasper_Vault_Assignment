"""Same-holdout scoring of candidate pricing policies on Aman's per-order panels.

Panels: /scratchpad/amanrun/aman/panels_dump.pkl  (May, June, July 2026; 5,806 orders;
every candidate priced walk-forward on identical orders; q_C0 = JV's actual premium).

Demand rules (A = JV actual premium, P = candidate premium, r = P/A):
  none        w = 1
  cons_e1     w = min(r^-1, 1)      price rises lose orders, cuts win none
  cons_e2     w = min(r^-2, 1)
  smooth_e1   w = min(r^-1, 3)      cuts win volume (Maksim's smooth rule)
  keep_1.10   w = 1 if r <= 1.10 else 0
  keep_1.25   w = 1 if r <= 1.25 else 0
  keep_1.00   w = 1 if r <= 1.00 else 0
Profit = sum w (P - payout).  Loss ratio = sum w payout / sum w P.
Run:  python3 -I score_panels.py
"""
import pickle, sys
import numpy as np, pandas as pd

SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'
OUT = SP + 'audit/'
with open(SP + 'amanrun/aman/panels_dump.pkl', 'rb') as f:
    P = pickle.load(f)['panels']
df = pd.concat(P.values(), ignore_index=True)
df['pay'] = df['realizedProfit_USDC'].astype(float)
A = df['q_C0'].values

# ---- extra candidate policies built from the panel columns ---------------------------------
fv = df['fv'].values
base = df['q_C1'].values            # NaN where no API base
has_base = ~np.isnan(base)
# Maksim without base floor (pure FV x 1.25)
df['q_M_nofloor'] = fv * 1.25
# F1 with Maksim's base floor added
df['q_F1_basefloor'] = np.where(has_base, np.maximum(df['q_F1'].values, base), df['q_F1'].values)
# F1 lifted 10% (theta_level = +0.10, as in Aman's frontier, floor unchanged)
df['q_F1_t10'] = np.maximum(df['q_F1'].values * 1.10, fv)
# F1 at +5%
df['q_F1_t05'] = np.maximum(df['q_F1'].values * 1.05, fv)
# Fair value x 1.10 and x 1.15 (lower margins than Maksim's 1.25), no floor
df['q_FV110'] = fv * 1.10
df['q_FV115'] = fv * 1.15
# Geometric blend of F1 and M
df['q_blend_F1M'] = np.sqrt(df['q_F1'].values * df['q_M'].values)
# M capped at 1.25 x estimated reference (R0) and floored at FV
df['q_M_cap125R0'] = np.maximum(np.minimum(df['q_M'].values, 1.25 * df['q_R0'].values), fv)
# F1 with a wider band 0.8-1.4 : rebuild from p_ref and fv/n ; n unknown per fold -> use shape_raw_n
sh = df['shape_raw_n'].values
df['q_F1_wide'] = np.maximum(df['p_ref'].values * np.clip(sh, 0.8, 1.4), fv)
df['q_F1_wide15'] = np.maximum(df['p_ref'].values * np.clip(sh, 0.8, 1.5), fv)
df['q_F1_wide_t05'] = np.maximum(df['p_ref'].values * np.clip(sh, 0.8, 1.4) * 1.05, fv)

CANDS = ['q_C0', 'q_R0', 'q_F0', 'q_F1', 'q_F1nf', 'q_M', 'q_S', 'q_M_nofloor', 'q_F1_basefloor',
         'q_F1_t05', 'q_F1_t10', 'q_FV110', 'q_FV115', 'q_blend_F1M', 'q_M_cap125R0',
         'q_F1_wide', 'q_F1_wide15', 'q_F1_wide_t05']

def weights(r, rule):
    if rule == 'none': return np.ones_like(r)
    if rule == 'cons_e1': return np.minimum(r ** -1.0, 1.0)
    if rule == 'cons_e2': return np.minimum(r ** -2.0, 1.0)
    if rule == 'smooth_e1': return np.minimum(r ** -1.0, 3.0)
    if rule.startswith('keep_'):
        k = float(rule.split('_')[1]); return (r <= k + 1e-12).astype(float)
    raise ValueError(rule)

RULES = ['none', 'cons_e1', 'cons_e2', 'smooth_e1', 'keep_1.00', 'keep_1.10', 'keep_1.25']

def gini(p, a, pay):
    """Ordered Lorenz Gini (Frees et al. 2011): sort by p/a ascending; x = cum share of a, y = cum share of payout."""
    r = p / a
    o = np.argsort(r, kind='mergesort')
    x = np.concatenate([[0], np.cumsum(a[o]) / a.sum()])
    y = np.concatenate([[0], np.cumsum(pay[o]) / pay.sum()])
    return 2 * np.trapezoid(x - y, x)

def score(sub, col, rule):
    p = sub[col].values; a = sub['q_C0'].values; pay = sub['pay'].values
    w = weights(p / a, rule)
    pnl = w * (p - pay)
    daily = pd.Series(pnl).groupby(sub['day'].values).sum()
    return dict(
        profit=pnl.sum(), premium_kept=(w * p).sum(), loss_ratio=(w * pay).sum() / max((w * p).sum(), 1e-9),
        price_vs_JV=p.sum() / a.sum(), share_cheaper=(p < a).mean(), orders_kept=w.mean(),
        jv_premium_kept=(w * a).sum() / a.sum(), worst_day=daily.min(), sd_day=daily.std(),
        gini=gini(p, a, pay) if rule == 'none' else np.nan)

def table(sub, label):
    rows = []
    for c in CANDS:
        for rule in RULES:
            d = score(sub, c, rule); d.update(model=c.replace('q_', ''), rule=rule, period=label); rows.append(d)
    return pd.DataFrame(rows)

periods = {'Jul': df[df.month == '2026-07'], 'May+Jun': df[df.month.isin(['2026-05', '2026-06'])],
           'May': df[df.month == '2026-05'], 'Jun': df[df.month == '2026-06'], 'May-Jul': df}
res = pd.concat([table(s, k) for k, s in periods.items()], ignore_index=True)
res.to_csv(OUT + 'same_holdout_scores.csv', index=False)

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); pd.set_option('display.max_rows', 500)
for per in ['Jul', 'May+Jun']:
    print(f'\n===== {per} : profit by demand rule (USDC) =====')
    t = res[res.period == per].pivot(index='model', columns='rule', values='profit')[RULES].round(0)
    meta = res[(res.period == per) & (res.rule == 'none')].set_index('model')[['price_vs_JV', 'share_cheaper', 'loss_ratio', 'worst_day', 'gini']]
    print(pd.concat([t, meta.round(3)], axis=1).loc[[c.replace('q_', '') for c in CANDS]])
    print('\norders kept / JV premium kept under cons_e2 and keep_1.10:')
    k = res[(res.period == per) & (res.rule.isin(['cons_e2', 'keep_1.10']))].pivot(index='model', columns='rule', values=['orders_kept', 'jv_premium_kept']).round(3)
    print(k.loc[[c.replace('q_', '') for c in CANDS]])

# per-month profit, no demand response, and worst days
print('\n===== monthly profit, no demand response =====')
print(res[(res.rule == 'none') & (res.period.isin(['May', 'Jun', 'Jul']))].pivot(index='model', columns='period', values='profit').round(0).loc[[c.replace('q_', '') for c in CANDS]])
print('\n===== monthly profit, cons_e2 =====')
print(res[(res.rule == 'cons_e2') & (res.period.isin(['May', 'Jun', 'Jul']))].pivot(index='model', columns='period', values='profit').round(0).loc[[c.replace('q_', '') for c in CANDS]])
print('\n===== monthly profit, keep_1.10 =====')
print(res[(res.rule == 'keep_1.10') & (res.period.isin(['May', 'Jun', 'Jul']))].pivot(index='model', columns='period', values='profit').round(0).loc[[c.replace('q_', '') for c in CANDS]])
