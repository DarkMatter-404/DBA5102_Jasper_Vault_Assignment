#!/usr/bin/env python3
"""Forward RSS collection with immutable first observations and feed-health logs.

This is an input-data collector, not permission to enable the research news price.
Run once every five minutes on a machine that can access the configured feeds.
"""
from __future__ import annotations
import argparse, hashlib, html, json, re, sqlite3, sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
import pandas as pd
import news

HERE=Path(__file__).resolve().parent

def utcnow():return datetime.now(timezone.utc).isoformat()

def clean(text):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(text or '')))).strip()

def parse_timestamp(raw):
    """Never invent a timezone or intraday time for an ambiguous date."""
    raw=str(raw or '').strip()
    if not raw:return ''
    try:
        d=parsedate_to_datetime(raw)
    except (ValueError,TypeError):
        try:d=datetime.fromisoformat(raw.replace('Z','+00:00'))
        except ValueError:return ''
    if d.tzinfo is None:return ''
    return d.astimezone(timezone.utc).isoformat()

def parse_feed(payload):
    root=ET.fromstring(payload)
    if root.tag.split('}')[-1].lower() not in {'rss','feed','rdf'}:
        raise ValueError('Response is not an RSS/Atom feed')
    records=[]
    for item in root.iter():
        if item.tag.split('}')[-1] not in {'item','entry'}:continue
        tags={child.tag.split('}')[-1]:child for child in item}
        def value(key):
            el=tags.get(key)
            return ''.join(el.itertext()).strip() if el is not None else ''
        links=[el for el in item if el.tag.split('}')[-1]=='link']
        url=next((el.attrib['href'] for el in links if el.attrib.get('href') and el.attrib.get('rel','alternate')=='alternate'),'')
        if not url:url=value('link')
        if not url.startswith(('http://','https://')):continue
        title=clean(value('title'))
        if not title:continue
        raw_date=value('pubDate') or value('published') or value('date')
        # Atom updated is an edit clock, not evidence of original publication.
        records.append({'source_url':url,'title':title,
                        'text':' '.join(clean(value('description') or value('summary') or value('content')).split()[:200]),
                        'published_at':parse_timestamp(raw_date),'publisher_timestamp_raw':raw_date})
    return records

def open_db(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS observations (source TEXT, url TEXT, content_hash TEXT, first_seen_at TEXT, payload TEXT, PRIMARY KEY(source,url,content_hash))')
    db.execute('CREATE TABLE IF NOT EXISTS runs (source TEXT, finished_at TEXT, status TEXT, article_count INTEGER, new_versions INTEGER, detail TEXT)')
    return db

def ingest(db,feed,payload,model,model_hash,seen_at=None,ready_clock=utcnow):
    rows=parse_feed(payload);added=0
    for row in rows:
        seen=seen_at or utcnow();url=news.canonical_url(row['source_url'])
        digest=hashlib.sha256((row['title']+'\n'+row['text']).encode()).hexdigest()
        if db.execute('SELECT 1 FROM observations WHERE source=? AND url=? AND content_hash=?',(feed['name'],url,digest)).fetchone():continue
        text=(row['title']+' '+row['text']).split()[:240];text=' '.join(text)
        vec=news.text_vectors(model,pd.DataFrame({'input_text':[text]}))[0].tolist()
        tags={k:len(re.findall(p,text,re.I)) for k,p in news.PATTERNS.items()}
        ready=ready_clock()
        if pd.Timestamp(ready)<pd.Timestamp(seen):raise ValueError('NLP-ready clock precedes receipt')
        record={**row,'news_id':hashlib.sha256((url+digest).encode()).hexdigest()[:20],
                'source':feed['name'],'source_url':url,'first_seen_at':seen,'nlp_ready_at':ready,
                'retrieved_at':seen,'clock_quality':'observed_local','timestamp_precision':'minute' if row['published_at'] else 'unknown',
                'publication_bound_at':row['published_at'],'text_scope':'rss_title_and_up_to_200_summary_words',
                'text_sha256':digest,'rights':feed.get('rights','Publisher terms apply'),
                'text_vector':vec,'event_tags':tags,'text_model_sha256':model_hash,
                'nlp_version':news.NLP_VERSION,'text_version_verified_at_release':False}
        db.execute('INSERT INTO observations VALUES (?,?,?,?,?)',(feed['name'],url,digest,seen,json.dumps(record)))
        added+=1
    db.commit();return len(rows),added

def export_first_versions(db,path):
    # Preserve every edit in SQLite, but expose only the earliest observed text per URL.
    rows=db.execute('SELECT url,payload FROM observations ORDER BY first_seen_at,rowid').fetchall()
    seen=set();out=[]
    for url,payload in rows:
        if url not in seen:out.append(payload);seen.add(url)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text('\n'.join(out)+('\n' if out else ''));tmp.replace(path)
    return len(out)

def health(db,config,asof=None):
    now=pd.Timestamp(asof or utcnow());limit=config.get('max_health_age_seconds',600);rows=[]
    for feed in config['feeds']:
        r=db.execute('SELECT finished_at,status,detail FROM runs WHERE source=? AND finished_at<=? ORDER BY finished_at DESC,rowid DESC LIMIT 1',(feed['name'],now.isoformat())).fetchone()
        age=(now-pd.Timestamp(r[0])).total_seconds() if r else None
        ok=bool(r and r[1]=='ok' and 0<=age<=limit)
        rows.append({'source':feed['name'],'required':feed.get('required',True),'healthy':ok,'age_seconds':age,'latest_status':r[1] if r else 'never_collected'})
    return {'asof_utc':now.isoformat(),'healthy':all(r['healthy'] for r in rows if r['required']),
            'sources':rows,'pricing_action':'Use V2. This package never activates the news price automatically.'}

def fetch(url,user_agent):
    request=Request(url,headers={'User-Agent':user_agent,'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    with urlopen(request,timeout=25) as response:
        payload=response.read(5_000_001)
    if len(payload)>5_000_000:raise ValueError('Feed exceeds 5 MB response limit')
    return payload

def collect(args):
    config=json.loads(Path(args.config).read_text());model_bytes=Path(args.model).read_bytes()
    model=json.loads(model_bytes)['text_model'];model_hash=hashlib.sha256(model_bytes).hexdigest()
    db=open_db(args.db);failed=False
    for feed in config['feeds']:
        try:
            payload=fetch(feed['url'],args.user_agent);count,added=ingest(db,feed,payload,model,model_hash)
            status='ok';detail='Parsed feed successfully; empty feed is distinct from failed request.'
        except Exception as error:
            count=added=0;status='error';detail=f'{type(error).__name__}: {error}';failed=True
        db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?)',(feed['name'],utcnow(),status,count,added,detail));db.commit()
        print(json.dumps({'source':feed['name'],'status':status,'articles':count,'new_versions':added,'detail':detail}),flush=True)
    count=export_first_versions(db,args.export);report=health(db,config)
    report['exported_first_versions']=count
    Path(args.health_output).parent.mkdir(parents=True,exist_ok=True);Path(args.health_output).write_text(json.dumps(report,indent=2)+'\n')
    db.close()
    return 2 if failed else 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default=str(HERE/'data/feeds.json'));p.add_argument('--model',default=str(HERE/'reference_results/preblind_research_model.json'))
    p.add_argument('--db',default=str(HERE/'runtime/news.sqlite'));p.add_argument('--export',default=str(HERE/'runtime/observed_news.jsonl'))
    p.add_argument('--health-output',default=str(HERE/'runtime/feed_health.json'))
    p.add_argument('--user-agent',required=True,help='Identify your project and contact address as required by publisher policies')
    sys.exit(collect(p.parse_args()))

if __name__=='__main__':main()
