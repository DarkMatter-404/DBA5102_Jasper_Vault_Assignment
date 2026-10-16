"""Append first-seen RSS/Atom cards for PROSPECTIVE research. Never backfill receipt time.

No full publisher articles are redistributed. Some feeds require user-agent
contact details or may change; failures are recorded, not replaced with guesses.
"""
import argparse,json,hashlib,re
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

def text(node,name):
    for e in node.iter():
        if e.tag.split('}')[-1]==name:return ''.join(e.itertext()).strip()
    return ''

def collect(config,output,user_agent,fixture=None):
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    seen=set()
    if dest.exists():seen={json.loads(l)['source_id'] for l in dest.read_text().splitlines() if l.strip()}
    receipt=datetime.now(timezone.utc);added=0;errors=[]
    with dest.open('a') as f:
        for source in config:
            try:
                if urlsplit(source['url']).scheme!='https':raise ValueError('HTTPS feed required')
                raw=Path(fixture).read_bytes() if fixture else urlopen(Request(source['url'],headers={'User-Agent':user_agent}),timeout=30).read(2_000_001)
                if len(raw)>2_000_000:raise ValueError('Feed too large')
                root=ET.fromstring(raw)
                for item in root.iter():
                    if item.tag.split('}')[-1] not in ['item','entry']:continue
                    title=text(item,'title');url=text(item,'link')
                    if not url:
                        url=next((e.attrib.get('href','') for e in item if e.tag.split('}')[-1]=='link'),'')
                    if urlsplit(url).scheme!='https':continue
                    sid='rss-'+hashlib.sha256(url.encode()).hexdigest()[:16]
                    if sid in seen:continue
                    date=text(item,'pubDate') or text(item,'published') or text(item,'updated')
                    try:
                        pub=parsedate_to_datetime(date)
                    except (ValueError,TypeError):
                        try:pub=datetime.fromisoformat(date.replace('Z','+00:00'))
                        except ValueError:pub=receipt
                    if pub.tzinfo is None:pub=pub.replace(tzinfo=timezone.utc)
                    # Short excerpt for classification; full fetch can be implemented
                    # with publisher permission and an immutable archive.
                    content=text(item,'description') or text(item,'summary')
                    fact=re.sub(r'<[^>]+>',' ',content)
                    fact=' '.join(fact.split())[:120]
                    row={'source_id':sid,'event_id':sid,'title':title,'url':url,'source_fact':fact,
                        'published_at':pub.isoformat(),'event_date':pub.date().isoformat(),
                        'proxy_available_at':(max(pub,receipt)+timedelta(minutes=5)).isoformat(),
                        'collected_at':receipt.isoformat(),'processed_at':receipt.isoformat(),
                        'clock_basis':'observed_feed_receipt_plus_five_minutes','source_kind':source['source_kind'],
                        'label_provenance':'unclassified_live_feed','research':{'category':'none','reason':'Awaiting research'},
                        'review':{'category':'none','admit':False,'reason':'Awaiting verification'},
                        'input_sha256':hashlib.sha256((title+'\n'+fact).encode()).hexdigest(),
                        'feed_sha256':hashlib.sha256(raw).hexdigest()}
                    f.write(json.dumps(row)+'\n');seen.add(sid);added+=1
            except Exception as exc:errors.append({'feed':source['url'],'error_type':type(exc).__name__})
    summary={'at':receipt.isoformat(),'added':added,'errors':errors,'note':'Exact URL deduplication only; cross-source episode matching needs review before pricing.'}
    with dest.with_suffix('.collection_log.jsonl').open('a') as log:log.write(json.dumps(summary)+'\n')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--user-agent',default='EventToLossAcademicPrototype/1.0');p.add_argument('--fixture')
    a=p.parse_args();print(json.dumps(collect(json.loads(Path(a.config).read_text()),a.output,a.user_agent,a.fixture)))
