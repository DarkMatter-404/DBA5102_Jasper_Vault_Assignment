"""When the crowd is right. The contrarian pattern is a mean-reversion bet; it fails on days when the move continues
(a trending market such as August 2026 in the validation period). How often did that happen in training, and how
much of the losses did those days carry?

Definition (per calendar day, orders with book >= 1 BTC): 'crowd-right day' if the orders that added to the
dominant side paid out more than their premium (LR_adds > 1).
"""
import sys, numpy as np, pandas as pd
pd.set_option('display.width', 220); pd.set_option('display.float_format', lambda x: f'{x:,.2f}')
d = pd.read_pickle(sys.argv[1]); d['date'] = d.createdAt.dt.date
b = d[d.open_total_btc >= 1].copy(); b['cls'] = pd.cut(b.s_add, [-1.01, -0.15, 0.15, 1.01], labels=['reduces', 'neutral', 'adds'])
day = b.pivot_table(index='date', columns='cls', values=['prem', 'pay'], aggfunc='sum', observed=True).fillna(0)
day.columns = [f'{a}_{c}' for a, c in day.columns]
allday = d.groupby('date').agg(prem_all=('prem', 'sum'), pay_all=('pay', 'sum')); day = day.join(allday)
day['pnl_all'] = day.prem_all - day.pay_all
day = day[day.prem_adds > 100]
day['LR_adds'] = day.pay_adds/day.prem_adds; day['LR_reduces'] = day.pay_reduces/day.prem_reduces.replace(0, np.nan)
day['crowd_right'] = day.LR_adds > 1
g = day.groupby('crowd_right').agg(days=('pnl_all', 'size'), prem=('prem_all', 'sum'), pnl=('pnl_all', 'sum'), worst=('pnl_all', 'min'), mean_pnl=('pnl_all', 'mean'),
                                   LR_adds=('pay_adds', lambda s: s.sum()/day.loc[s.index, 'prem_adds'].sum()), LR_reduces=('pay_reduces', lambda s: s.sum()/day.loc[s.index, 'prem_reduces'].sum()))
print('=== days split by whether the crowded side paid out (training, days with >= 100 USDC of crowd premium)'); print(g)
print('\nshare of days crowd-right: %.0f%%; share of total P&L on those days: %s' % (100*day.crowd_right.mean(), f"{day.pnl_all[day.crowd_right].sum():,.0f} of {day.pnl_all.sum():,.0f}"))
print('\n=== the 8 worst days overall: were they crowd-right days?')
print(day.sort_values('pnl_all').head(8)[['prem_all', 'pnl_all', 'LR_adds', 'LR_reduces', 'crowd_right']])
# daily BTC move on those days vs others (trend proxy): use abs 24h return of orders that day
mv = d.groupby('date').ret24h.apply(lambda s: s.abs().mean()); day['abs_ret24h'] = mv
print('\nmean |24h return| (pct) at order time: crowd-right days %.2f vs other days %.2f' % (day.loc[day.crowd_right, 'abs_ret24h'].mean(), day.loc[~day.crowd_right, 'abs_ret24h'].mean()))
# does a simple trend filter flag them in advance? share of crowd-right days among days where |ret24h| > 2% at the median order
day['trend_flag'] = day.abs_ret24h > 2
print(pd.crosstab(day.trend_flag, day.crowd_right, margins=True))
day.to_csv('results_crowd_right_days.csv')
