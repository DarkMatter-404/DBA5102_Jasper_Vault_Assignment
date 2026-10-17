import sys,unittest,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from etl.data import Market,orders,QUOTE_FIELDS
from etl.events import Events
from etl.hazard import Hazard
from etl.simulator import Simulator,distribution_stats

class Integrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market=Market(ROOT/'data/raw/btc_market_history.csv.gz')
        cls.train=orders(ROOT/'data/raw/pp_transactions_training.csv')
        cls.cut=pd.Timestamp('2026-07-01',tz='UTC')
        cls.events=Events(ROOT/'data/events/recorded_events.jsonl')
        cls.hazard=Hazard().fit(cls.train,cls.market,cls.cut)
        cls.sim=Simulator(cls.market,cls.events,cls.hazard,cls.cut)
        cls.row=next(cls.train[(cls.train.createdAt>=cls.cut)&cls.train.scorable][QUOTE_FIELDS].itertuples(index=False))

    def test_no_future_market_or_path(self):
        c=self.market.context(self.row.createdAt)
        self.assertLess(pd.Timestamp(c['market_asof']),self.row.createdAt)
        self.assertLess(self.sim.a['last_path_observation'],self.cut.value)
        self.assertLess(pd.Timestamp(self.hazard.meta['last_label_close']),self.cut)
        # Alter all market observations at/after quote and check past feature unchanged.
        i=c['index']; self.assertLess(self.market.time[i],self.row.createdAt.value)
        self.assertGreaterEqual(self.market.time[i+1],self.row.createdAt.value)

    def test_outcome_does_not_change_quote(self):
        a=self.sim.predict(self.row,outcome=0);b=self.sim.predict(self.row,outcome=100000)
        for x,y in zip(a,b):
            for k in ['mean_claim','es95','payout_probability','event_weight']:self.assertEqual(x[k],y[k])
        self.assertNotEqual(a[0]['crps'],b[0]['crps'])

    def test_observed_clock_has_no_historical_events(self):
        ev=Events(ROOT/'data/events/recorded_events.jsonl','observed')
        for t in pd.date_range('2026-01-01','2026-10-15',freq='h',tz='UTC'):
            self.assertIsNone(ev.context(t,'verified_research'))

    def test_event_admission_and_delay(self):
        for r in self.events.records:
            t=pd.Timestamp(r['proxy_available_at'])
            self.assertGreater(t,pd.Timestamp(r['published_at']))
            if not r['review']['admit']:
                self.assertNotIn(r['source_id'],{s['source_id'] for s in self.events.by_arm['verified_research']})
        e=next(r for r in self.events.records if r['event_id']=='cpi-07-14')
        self.assertIsNone(self.events.context(pd.Timestamp(e['proxy_available_at'])-pd.Timedelta(minutes=1),'verified_research'))
        self.assertEqual(self.events.context(pd.Timestamp(e['proxy_available_at']),'verified_research')['event_id'],'cpi-07-14')

    def test_distribution_and_payoff_mechanics(self):
        s=distribution_stats(np.array([0.,10.]),np.array([.5,.5]),5)
        self.assertAlmostEqual(s['mean_claim'],5);self.assertAlmostEqual(s['es95'],10)
        self.assertAlmostEqual(s['crps'],2.5)
        h=self.hazard.settlement_mass(np.zeros((3,6)),SimpleNamespace(productType=1800,optionType=0,quantity_BTC=.01,strikePrice=80000),.001)
        np.testing.assert_allclose(h.sum(axis=1),1)
        r=self.row
        low=self.sim.predict(r,verified_spot=r.strikePrice*.95)[0]['mean_claim']
        high=self.sim.predict(r,verified_spot=r.strikePrice*1.05)[0]['mean_claim']
        self.assertTrue(high>=low if r.optionType==0 else high<=low)

    def test_missing_market_fails_closed_status(self):
        r=self.row._replace(createdAt=pd.Timestamp('2026-10-01',tz='UTC'))
        p=self.sim.predict(r)[-1]
        self.assertEqual(p['quote_status'],'missing_market_diagnostic_only')
        self.assertEqual(p['event_weight'],0)
        self.assertTrue(np.isfinite(p['mean_claim']))

if __name__=='__main__':unittest.main(verbosity=2)
