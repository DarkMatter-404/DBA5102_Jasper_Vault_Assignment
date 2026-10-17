import sys,unittest,tempfile,json,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from etl.agents import process_records,validate_label

class FakeClient:
    model='fixture-not-an-llm';verifier='fixture-not-an-llm'
    def call(self,prompt,payload,model):
        if 'analyst' in payload:
            return {'category':'inflation','admit':True,'reason':'fixture'}, {'model':model,'usage':None}
        assert 'research' not in payload and 'review' not in payload
        assert 'realizedProfit_USDC' not in payload
        return {'category':'inflation','reason':'fixture'}, {'model':model,'usage':None}

class AgentTests(unittest.TestCase):
    def test_schema_rejects_probability_and_nonboolean(self):
        with self.assertRaises(ValueError):validate_label({'category':'inflation','reason':'x','probability':.99})
        with self.assertRaises(ValueError):validate_label({'category':'inflation','reason':'x','admit':'true'},True)

    def test_two_pass_preserves_evidence_and_clocks(self):
        r=json.loads((ROOT/'data/events/recorded_events.jsonl').read_text().splitlines()[0])
        with tempfile.TemporaryDirectory() as d:
            out=process_records([r],FakeClient(),ROOT/'prompts',Path(d)/'log.jsonl')[0]
            for k in ['proxy_available_at','published_at','collected_at','source_id','event_id','source_fact']:
                self.assertEqual(out[k],r[k])
            self.assertEqual(out['review']['category'],'inflation')
            log=json.loads((Path(d)/'log.jsonl').read_text())
            self.assertEqual(len(log['calls']),2)

    def test_collector_records_receipt_and_deduplicates(self):
        spec=importlib.util.spec_from_file_location('collector',ROOT/'scripts/collect_news.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        xml='<rss><channel><item><title>Fixture release</title><link>https://example.org/release</link><pubDate>Tue, 14 Jul 2026 12:30:00 GMT</pubDate><description>Fixture only.</description></item></channel></rss>'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'feed.xml').write_text(xml)
            config=[{'url':'https://example.org/rss','source_kind':'primary'}]
            a=mod.collect(config,p/'out.jsonl','fixture',p/'feed.xml')
            b=mod.collect(config,p/'out.jsonl','fixture',p/'feed.xml')
            self.assertEqual(a['added'],1);self.assertEqual(b['added'],0)
            r=json.loads((p/'out.jsonl').read_text())
            self.assertGreater(r['proxy_available_at'],r['collected_at'])
            self.assertFalse(r['review']['admit'])

if __name__=='__main__':unittest.main()
