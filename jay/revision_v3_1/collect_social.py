#!/usr/bin/env python3
"""Record actual local receipt of a provider Tier-1 CSV; no backdated receipt."""
import argparse, datetime, hashlib, json
from pathlib import Path
import pandas as pd
import social

FIELDS=['symbol','snapshot_ts','meta_added_ts','meta_expires_ts','meta_duration_sec','sentiment_posts_total','sentiment_posts_pos','sentiment_posts_neu','sentiment_posts_neg','sentiment_mean_score','sentiment_is_silent']

def ingest(source,journal):
    source=Path(source);journal=Path(journal)
    raw=source.read_bytes();received=datetime.datetime.now(datetime.timezone.utc).isoformat()
    d=pd.read_csv(source)
    for c in ['snapshot_ts','meta_added_ts','meta_expires_ts']:d[c]=pd.to_datetime(d[c],utc=True,errors='raise',format='mixed')
    social.validate(d);d=d[d.symbol.eq('BTC')]
    seen=set()
    if journal.exists():seen={json.loads(s)['record_id'] for s in journal.read_text().splitlines() if s.strip()}
    rows=[];digest=hashlib.sha256(raw).hexdigest()
    for r in d.to_dict('records'):
        key='observed_'+hashlib.sha256((r['symbol']+'|'+r['meta_added_ts'].isoformat()).encode()).hexdigest()[:16]
        if key in seen:continue
        row={k:r.get(k) for k in FIELDS}
        for k,v in row.items():
            if pd.isna(v):row[k]=None
            elif isinstance(v,pd.Timestamp):row[k]=v.isoformat()
        row.update(record_id=key,clock_quality='observed_local',first_seen_at=received,nlp_ready_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_file=source.name,source_sha256=digest,score_origin='precomputed provider hybrid NLP; adapter did not train or run transformer')
        rows.append(row);seen.add(key)
    journal.parent.mkdir(parents=True,exist_ok=True)
    with journal.open('a') as f:
        for r in rows:f.write(json.dumps(r,allow_nan=False)+'\n')
    result={'new_records':len(rows),'journal':str(journal),'received_at':received,'note':'Receipt now does not make historical samples fresh. Use social.prepare(..., clock="observed") and the four-hour admission-age limit.'}
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--journal',required=True);a=p.parse_args();ingest(a.input,a.journal)
