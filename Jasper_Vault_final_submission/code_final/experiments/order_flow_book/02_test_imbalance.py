"""Does the state of JV's book predict payouts?

Tests (training orders only):
 1. Orders that add to the dominant open side vs orders that reduce it: loss ratio and payout / fair value.
 2. Does the book imbalance predict the direction of the BTC move over the protection window?
 3. Daily P&L vs how one-sided the book was that day.
Intervals: bootstrap over calendar days (whole days resampled), 90 percent.
"""
import sys, numpy as np, pandas as pd
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 30); pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
d = pd.read_pickle(sys.argv[1]); d['date'] = d.createdAt.dt.date
rng = np.random.default_rng(7)
def boot_ratio(df, num, den, B=1000):
    days = df.date.unique(); g = df.groupby('date')[[num, den]].sum()
    vals = []
    for _ in range(B):
        smp = g.loc[rng.choice(days, len(days), replace=True)]
        vals.append(smp[num].sum()/smp[den].sum())
    return np.percentile(vals, [5, 95])
def table(df, col, bins, labels):
    df = df.copy(); df['g'] = pd.cut(df[col], bins, labels=labels)
    rows = []
    for k, t in df.groupby('g', observed=True):
        lo, hi = boot_ratio(t, 'pay', 'fair_har'); lo2, hi2 = boot_ratio(t, 'pay', 'prem')
        rows.append(dict(group=k, n=len(t), premium=t.prem.sum(), loss_ratio=t.pay.sum()/t.prem.sum(), lr_90=f'[{lo2:.2f},{hi2:.2f}]',
                         pay_over_fair=t.pay.sum()/t.fair_har.sum(), pof_90=f'[{lo:.2f},{hi:.2f}]'))
    return pd.DataFrame(rows)
MIN_BOOK = 1.0   # BTC; below this the book is too small for the imbalance to mean anything
big = d[d.open_total_btc >= MIN_BOOK]
print(f'orders with open book >= {MIN_BOOK} BTC: {len(big)} of {len(d)} ({big.prem.sum()/d.prem.sum():.0%} of premium)')
print('\n=== 1a. by signed imbalance from the order\'s perspective (s_add > 0: order adds to the dominant side)')
print(table(big, 's_add', [-1.01, -0.5, -0.15, 0.15, 0.5, 1.01], ['strongly reduces', 'reduces', 'neutral', 'adds', 'strongly adds']).to_string(index=False))
print('\n=== 1b. same, using 24h net flow instead of the open book')
print(table(d, 's_flow24', [-1.01, -0.5, -0.15, 0.15, 0.5, 1.01], ['against flow (strong)', 'against flow', 'neutral', 'with flow', 'with flow (strong)']).to_string(index=False))
print('\n=== 1c. adds vs reduces, by product length (open book >= 1 BTC)')
big = big.copy(); big['cls'] = np.where(big.s_add > 0.15, 'adds', np.where(big.s_add < -0.15, 'reduces', 'neutral'))
g = big.groupby(['productType', 'cls']).agg(n=('prem', 'size'), prem=('prem', 'sum'), pay=('pay', 'sum'), fair=('fair_har', 'sum'))
g['LR'] = g.pay/g.prem; g['pay/fair'] = g.pay/g.fair; print(g[['n', 'prem', 'LR', 'pay/fair']].unstack('cls').round(2))
print('\n=== 1d. by month (open book >= 1 BTC)')
g = big.groupby(['month', 'cls']).agg(n=('prem', 'size'), prem=('prem', 'sum'), pay=('pay', 'sum'), fair=('fair_har', 'sum'))
g['pay/fair'] = g.pay/g.fair; print(g[['n', 'prem', 'pay/fair']].unstack('cls').round(2))

print('\n=== 2. does the imbalance predict the direction of the move?')
# adverse move indicator per order: for a call, BTC up over the window hurts JV; for a put, BTC down.
# use payout>0 as the realised adverse outcome and compare rates
big['paid'] = big.pay > 0
print('share of orders that paid out: adds %.3f, neutral %.3f, reduces %.3f' % tuple(big.groupby('cls').paid.mean()[['adds', 'neutral', 'reduces']]))
# correlation between book imbalance and the forward 4h return (sign test): positive imb = call-heavy = JV loses if BTC rises
r = d[d.open_total_btc >= MIN_BOOK]
print('Spearman corr(imb, ret over next window via payout side):')
# Use fwd return computed from S_close vs strike as proxy: adverse_move = (S_close-strike)/strike for calls, (strike-S_close)/strike for puts
d2 = pd.read_pickle(sys.argv[2])[['createdAt', 'S_close', 'S_exp']]
r = r.merge(d2, on='createdAt', how='left')
r['fwd_exp_ret'] = np.log(r.S_exp/r.strikePrice)
print('  corr(imb, log return to expiry) =', round(r[['imb', 'fwd_exp_ret']].corr('spearman').iloc[0, 1], 4), ' n =', len(r))
print('  corr(flow24_imb, log return to expiry) =', round(r[['flow24_imb', 'fwd_exp_ret']].corr('spearman').iloc[0, 1], 4))
print('  corr(ret24h (past), imb) =', round(r[['ret24h', 'imb']].corr('spearman').iloc[0, 1], 4), ' (do users herd into the side that just moved against them?)')
print('  corr(ret4h (past), flow24_imb) =', round(r[['ret4h', 'flow24_imb']].corr('spearman').iloc[0, 1], 4))

print('\n=== 3. daily P&L vs one-sidedness of the book')
day = d.groupby('date').agg(prem=('prem', 'sum'), pay=('pay', 'sum'), abs_imb=('imb', lambda s: np.average(s.abs(), weights=d.loc[s.index, 'prem']) if d.loc[s.index, 'prem'].sum() > 0 else np.nan), book=('open_total_btc', 'mean'))
day['pnl'] = day.prem - day.pay; day = day[day.prem > 200]
day['imb_q'] = pd.qcut(day.abs_imb, 4, labels=['balanced', 'q2', 'q3', 'one-sided'])
print(day.groupby('imb_q', observed=True).agg(days=('pnl', 'size'), prem=('prem', 'sum'), pnl=('pnl', 'sum'), LR=('pay', lambda s: s.sum()/day.loc[s.index, 'prem'].sum()), worst=('pnl', 'min'), sd=('pnl', 'std')).round(2))
print('\nworst 10 days: P&L and premium-weighted |imbalance| that day')
print(day.sort_values('pnl').head(10)[['prem', 'pay', 'pnl', 'abs_imb', 'book']].round(2))
d.to_pickle(sys.argv[1])
