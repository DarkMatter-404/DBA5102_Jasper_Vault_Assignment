#!/usr/bin/env python3
"""Forward-only headline collector using real receipt and readiness clocks."""
import argparse,hashlib,json,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'revision_v3'))
import collect_news as collector
import news

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--user-agent',required=True,help='Identify your project and contact address')
    p.add_argument('--config',default=str(HERE/'data/feeds.json'))
    p.add_argument('--outdir',default=str(HERE/'runtime'));a=p.parse_args()
    root=Path(a.outdir);root.mkdir(parents=True,exist_ok=True)
    config=json.loads(Path(a.config).read_text());model_bytes=(HERE/'models/frozen_components.json').read_bytes()
    text_model=json.loads(model_bytes)['news']['text_model'];model_hash=hashlib.sha256(model_bytes).hexdigest()
    db=collector.open_db(root/'news.sqlite');fail=False
    # The frozen model was fitted on headlines. Do not introduce RSS body text.
    original_parser=collector.parse_feed
    def headline_parser(payload):
        rows=original_parser(payload)
        for row in rows:row['text']=''
        return rows
    collector.parse_feed=headline_parser
    try:
        for feed in config['feeds']:
            try:
                payload=collector.fetch(feed['url'],a.user_agent)
                count,added=collector.ingest(db,feed,payload,text_model,model_hash)
                status='ok';detail='RSS parsed; headline-only features; actual local receipt.'
            except Exception as e:
                count=added=0;status='error';detail=f'{type(e).__name__}: {e}';fail=True
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?)',(feed['name'],collector.utcnow(),status,count,added,detail));db.commit()
            print(json.dumps({'source':feed['name'],'status':status,'articles':count,'new_versions':added,'detail':detail}))
        collector.export_first_versions(db,root/'observed_news.jsonl')
        h=collector.health(db,config)
        h['pricing_action']='Combined experimental framework in observed mode; missing or unhealthy feeds use its duration fallback.'
        h['text_scope']='headline_only'
        (root/'feed_health.json').write_text(json.dumps(h,indent=2)+'\n')
    finally:collector.parse_feed=original_parser;db.close()
    return 2 if fail else 0

if __name__=='__main__':sys.exit(main())
