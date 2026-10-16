"""Input audit and strictly backward-looking market features."""
from pathlib import Path
import numpy as np
import pandas as pd

SECONDS = 1_000_000_000
QUOTE_FIELDS = ['row_id', 'createdAt', 'optionType', 'productType', 'quantity_BTC', 'strikePrice']

def utc(x):
    return pd.to_datetime(x, format='mixed', utc=True, errors='coerce')

def orders(path):
    d = pd.read_csv(path)
    d.insert(0, 'row_id', np.arange(len(d)))
    for c in ['createdAt', 'closedAt', 'expirationDate']:
        d[c] = utc(d[c])
    d['valid_quote'] = (d.createdAt.notna() & d.optionType.isin([0, 1]) &
        d.productType.isin([1800,3600,7200,14400,28800,43200,86400]) &
        (d.quantity_BTC > 0) & (d.strikePrice > 0))
    d['scorable'] = (d.valid_quote & d.closedAt.notna() &
        (d.closedAt > d.createdAt) & d.realizedProfit_USDC.notna() &
        (d.realizedProfit_USDC >= 0) & (d.premiumAmount_USDC > 0))
    return d

def audit(train, validation, market):
    return {
        'training_rows': len(train), 'scorable_rows': int(train.scorable.sum()),
        'missing_training_outcomes': int(train.realizedProfit_USDC.isna().sum()),
        'invalid_training_chronology': int((train.closedAt.notna() & (train.closedAt <= train.createdAt)).sum()),
        'training_created_min': str(train.createdAt.min()), 'training_created_max': str(train.createdAt.max()),
        'validation_rows': len(validation), 'valid_validation_quotes': int(validation.valid_quote.sum()),
        'validation_hidden_payouts': int(validation.realizedProfit_USDC.isna().sum()),
        'validation_populated_closedAt_ignored': int(validation.closedAt.notna().sum()),
        'validation_created_min': str(validation.createdAt.min()), 'validation_created_max': str(validation.createdAt.max()),
        'training_missing_api_base': int(train.apiBasePrice_per_BTC_USDC.isna().sum()),
        'validation_missing_api_base': int(validation.apiBasePrice_per_BTC_USDC.isna().sum()),
        'market_rows': len(market.time), 'market_first_close': str(pd.Timestamp(market.time[0], tz='UTC')),
        'market_last_close': str(pd.Timestamp(market.time[-1], tz='UTC')),
        'market_gaps_over_90_seconds': int((np.diff(market.time) > 90*SECONDS).sum()),
        'validation_current_market_coverage': int(sum(market.context(t)['fresh'] for t in validation.createdAt)),
        'release_notes': ['The dictionary says validation closedAt is blank, but this file populates it. It is never passed to pricing.',
            'The enriched release excludes negative residual-markup orders upstream; results apply to this selected population.',
            'API base quotes are nearest-time matches within 120 seconds according to the guide; exact match clocks are not supplied.',
            'Class notes specify ATM. External spot is not treated as verified contract moneyness.']
    }

class Market:
    def __init__(self, path):
        d = pd.read_csv(path, usecols=['close_time_utc','close','volume'])
        d['time'] = utc(d.close_time_utc)
        d = d.sort_values('time').drop_duplicates('time')
        self.time = d.time.astype('int64').to_numpy()
        self.price = d.close.to_numpy(float)
        self.logp = np.log(self.price)
        r = pd.Series(np.r_[np.nan, np.diff(self.logp)])
        fast = r.rolling(60, min_periods=60).std(ddof=0).clip(lower=1e-7)
        slow = r.rolling(1440, min_periods=1440).std(ddof=0).clip(lower=1e-7)
        # Smooth, strictly trailing volatility. Units: per square-root minute.
        self.vol = np.sqrt(.5*fast.to_numpy()**2 + .5*slow.to_numpy()**2)
        lp = pd.Series(self.logp)
        activity = pd.Series(d.volume.to_numpy(float))
        rel = activity.rolling(60).mean() / activity.rolling(1440).mean().clip(lower=1e-12)
        self.features = np.column_stack([np.log(self.vol), np.log(fast/slow),
            (lp-lp.shift(60))/(self.vol*np.sqrt(60)),
            (lp-lp.shift(240))/(self.vol*np.sqrt(240)), np.log(rel.clip(lower=1e-5))])

    def index_before(self, t):
        return int(np.searchsorted(self.time, pd.Timestamp(t).value, side='left')-1)

    def context(self, t):
        i = self.index_before(t)
        fresh = i >= 1440 and 0 < pd.Timestamp(t).value-self.time[i] <= 90*SECONDS
        fresh = bool(fresh and np.isfinite(self.features[i]).all())
        return {'index':i, 'fresh':fresh, 'features':self.features[i] if fresh else None,
            'vol':float(self.vol[i]) if fresh else None,
            'market_asof':str(pd.Timestamp(self.time[i], tz='UTC')) if i >= 0 else None}

    def path_at(self, t, steps):
        # Used ONLY for fitting settled historical early-close labels.
        times = pd.Timestamp(t).value + np.arange(steps+1)*300*SECONDS
        ix = np.searchsorted(self.time, times, side='left')-1
        if np.any(ix < 0) or np.any(times-self.time[np.maximum(ix,0)] > 90*SECONDS):
            return None
        return self.logp[ix]-self.logp[ix[0]]

    def archive(self, cutoff):
        # 30-minute grid. Every full 24h outcome lies strictly before cutoff.
        lo = pd.Timestamp(self.time[0], tz='UTC').ceil('30min') + pd.Timedelta(days=7)
        hi = min(pd.Timestamp(cutoff)-pd.Timedelta(days=1, minutes=1),
                 pd.Timestamp(self.time[-1], tz='UTC')-pd.Timedelta(days=1))
        t = pd.date_range(lo, hi, freq='30min')
        tn = t.astype('int64').to_numpy()
        offsets = np.arange(289)*300*SECONDS
        ix = np.searchsorted(self.time, tn[:,None]+offsets, side='left')-1
        valid = (ix[:,0] >= 1440) & np.isfinite(self.features[ix[:,0]]).all(axis=1)
        valid &= ((tn[:,None]+offsets-self.time[ix]) <= 90*SECONDS).all(axis=1)
        ix, tn = ix[valid], tn[valid]
        assert (self.time[ix[:,-1]] < pd.Timestamp(cutoff).value).all()
        return {'time':tn, 'features':self.features[ix[:,0]], 'vol':self.vol[ix[:,0]],
                'paths':(self.logp[ix[:,1:]]-self.logp[ix[:,[0]]]).astype('float32'),
                'last_path_observation':int(self.time[ix[:,-1]].max())}
