"""Paired day-bootstrap 90% intervals for profit differences vs JV (C0) on the same panels.
Resamples UTC creation days within each month (2,000 draws, seed 0), identical draws for every model.
Run: python3 -I bootstrap_diffs.py
"""
import pickle, numpy as np, pandas as pd
SP = '/tmp/claude-0/-home-claude/ac6d6fb2-071e-5acb-9735-f66862273856/scratchpad/'
P = pickle.load(open(SP + 'amanrun/aman/panels_dump.pkl', 'rb'))['panels']
df = pd.concat(P.values(), ignore_index=True); df['pay'] = df.realizedProfit_USDC
fv = df.fv.values
df['q_F1_t10'] = np.maximum(df.q_F1 * 1.10, fv)
df['q_F1_t05'] = np.maximum(df.q_F1 * 1.05, fv)
df['q_blend_F1M'] = np.sqrt(df.q_F1 * df.q_M)
df['q_FV115'] = fv * 1.15
A = df.q_C0.values

def w(r, rule):
    if rule == 'none': return np.ones_like(r)
    if rule == 'cons_e1': return np.minimum(1 / r, 1)
    if rule == 'cons_e2': return np.minimum(r ** -2, 1)
    if rule == 'keep_1.10': return (r <= 1.10).astype(float)
    if rule == 'keep_1.25': return (r <= 1.25).astype(float)

rng = np.random.default_rng(0); NB = 2000
out = []
for per, months in [('Jul', ['2026-07']), ('May+Jun', ['2026-05', '2026-06'])]:
    sub = df[df.month.isin(months)].copy()
    days_by_month = {m: np.array(sorted(sub[sub.month == m].day.unique())) for m in months}
    draws = {m: rng.integers(0, len(d), (NB, len(d))) for m, d in days_by_month.items()}
    for model in ['q_F1', 'q_M', 'q_S', 'q_F0', 'q_F1_t05', 'q_F1_t10', 'q_blend_F1M', 'q_FV115']:
        for rule in ['none', 'cons_e1', 'cons_e2', 'keep_1.10', 'keep_1.25']:
            p = sub[model].values; a = sub.q_C0.values; pay = sub.pay.values
            d_order = w(p / a, rule) * (p - pay) - (a - pay)
            daily = pd.Series(d_order).groupby(sub.day.values).sum()
            sims = np.zeros(NB)
            for m in months:
                dv = daily.reindex(days_by_month[m]).values
                sims += dv[draws[m]].sum(axis=1)
            out.append(dict(period=per, model=model[2:], rule=rule, diff=d_order.sum(), lo90=np.quantile(sims, .05), hi90=np.quantile(sims, .95), p_pos=(sims > 0).mean()))
res = pd.DataFrame(out); res.to_csv(SP + 'audit/bootstrap_vs_JV.csv', index=False)
pd.set_option('display.width', 200)
for per in ['Jul', 'May+Jun']:
    print(f'\n== {per}: model minus JV profit, 90% day-bootstrap interval ==')
    t = res[res.period == per].copy()
    t['txt'] = t.apply(lambda r: f"{r['diff']:+,.0f} [{r.lo90:+,.0f}, {r.hi90:+,.0f}]", axis=1)
    print(t.pivot(index='model', columns='rule', values='txt')[['none', 'cons_e1', 'cons_e2', 'keep_1.10', 'keep_1.25']])
