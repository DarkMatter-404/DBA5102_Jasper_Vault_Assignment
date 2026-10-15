#!/usr/bin/env python3
"""Meaningful checks for the frozen model, temporal boundary and fallbacks."""
import gzip,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import framework as fw

class FrameworkChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=fw.HERE;cls.m=fw.model()
        raw=pd.read_csv(cls.root/'data/assignment_inputs/pp_transactions_validation.csv')
        cls.raw=raw
        bars=fw.v1.read_market(cls.root/'data/assignment_inputs/btc_market_history.csv.gz')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'orders.csv';fw.normalize(raw).to_csv(p,index=False)
            cls.d=fw.v3.augment(fw.v1.features(p,bars))
        cls.b,cls.origin=fw.references(raw)

    def test_input_and_model_identity(self):
        import hashlib
        manifest=json.loads((self.root/'data/input_manifest.json').read_text())
        self.assertEqual(fw.digest(self.root/'models/frozen_components.json'),manifest['frozen_components']['sha256'])
        for key in ['validation','market','training']:
            r=manifest[key];p=self.root/r['bundled_path'];b=p.read_bytes()
            self.assertEqual(hashlib.sha256(b).hexdigest(),r['bundled_sha256'])
            if p.suffix=='.gz':b=gzip.decompress(b)
            self.assertEqual(hashlib.sha256(b).hexdigest(),r['uncompressed_sha256'])
        self.assertLess(pd.Timestamp(self.m['news']['latest_training_settlement']),pd.Timestamp(self.m['cutoff_utc']))
        self.assertLess(pd.Timestamp(self.m['news']['text_model']['latest_training_document']),pd.Timestamp(self.m['cutoff_utc']))

    def test_future_records_do_not_change_quote(self):
        # Real quote at which news and social are both available.
        q=self.d[self.d.source_row.eq(300)].copy()
        news=fw.nlp.prepare_news(fw.nlp.read_news(self.root/'data/news_combined_2026.jsonl'),'publication_proxy',5)
        original=fw.nlp.quote_features(q,news,self.m['news']['text_model'])
        injected=news.iloc[[0]].copy();injected['available_at']=q.createdAt.iloc[0]+pd.Timedelta(seconds=1)
        injected['news_id']='future_record';injected['input_text']='hack crisis liquidation bitcoin'
        result=fw.nlp.quote_features(q,pd.concat([news,injected],ignore_index=True),self.m['news']['text_model'])
        pd.testing.assert_frame_equal(original,result)
        soc=fw.social.prepare(fw.social.read_records(self.root/'data/btc_social_snapshots.csv'))
        before=fw.social.quote_features(q,soc)
        extra=soc.iloc[[0]].copy();extra['available_at']=q.createdAt.iloc[0]+pd.Timedelta(seconds=1);extra['record_id']='future_social';extra['sentiment_mean_score']=-1.
        after=fw.social.quote_features(q,pd.concat([soc,extra],ignore_index=True))
        pd.testing.assert_frame_equal(before,after)

    def test_observed_clock_never_backdates_archive(self):
        f=fw.assemble(self.d,self.root/'data/news_combined_2026.jsonl',self.root/'data/btc_social_snapshots.csv',self.m,'observed')
        q=fw.predict_frame(f,self.m,self.b,self.origin)
        self.assertEqual(int(f.social_available.sum()),0)
        self.assertEqual(int(q.full_component_eligible.sum()),0)
        self.assertTrue(np.allclose(q.pricing_multiplier,q.duration_multiplier,equal_nan=True))

    def test_inference_no_fit_and_missing_data_fallback(self):
        fail=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Fitting called during inference'))
        with patch.object(fw.v2,'fit',fail),patch.object(fw.v3,'fit_model',fail),patch.object(fw.v31,'fit_overlay',fail):
            f=fw.assemble(self.d,self.root/'data/news_combined_2026.jsonl',self.root/'data/btc_social_snapshots.csv',self.m)
            q=fw.predict_frame(f,self.m,self.b,self.origin)
        self.assertEqual(len(q),4155);self.assertEqual(int(q.pricing_multiplier.isna().sum()),7)
        stale=~q.full_component_eligible&q.pricing_multiplier.notna()
        self.assertTrue(np.allclose(q.loc[stale,'pricing_multiplier'],q.loc[stale,'duration_multiplier']))
        no_social=q.full_component_eligible&~q.social_layer_applied
        self.assertTrue(np.allclose(q.loc[no_social,'pricing_multiplier'],q.loc[no_social,'market_news_multiplier']))
        changed=self.raw.copy();changed['closedAt']='2099-01-01';changed['realizedProfit_USDC']=999999999.
        pd.testing.assert_frame_equal(fw.normalize(self.raw),fw.normalize(changed))

if __name__=='__main__':unittest.main(verbosity=2)
