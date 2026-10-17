#!/usr/bin/env python3
"""Verify immutable social downloads and combine headline/social datasets offline."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'revision_v3_1'))
import social

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    root=HERE/'data';provider=root/'instrumetriq'
    manifest=json.loads((provider/'source_manifest.json').read_text());frames=[];audit=[]
    for f in manifest['files']:
        p=provider/'raw'/Path(f['path']).name;b=p.read_bytes()
        assert len(b)==f['size'] and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==f['sha'],p
        d=pd.read_csv(p);d['sample_file']=p.name;d['source_sha256']=sha(p);frames.append(d)
        audit.append({'filename':p.name,'rows':len(d),'btc_rows':int(d.symbol.eq('BTC').sum()),'sha256':sha(p),'git_blob_sha':f['sha']})
    allrows=pd.concat(frames,ignore_index=True);d=allrows[allrows.symbol.eq('BTC')].copy()
    old=pd.read_csv(HERE.parent/'revision_v3_1/data/btc_social_snapshots.csv')
    d['record_id']=['instrumetriq_'+hashlib.sha256((r.symbol+'|'+r.meta_added_ts).encode()).hexdigest()[:16] for r in d.itertuples()]
    d['clock_quality']='reconstructed_session_end_not_historical_receipt';d['first_seen_at']='';d['nlp_ready_at']=''
    d['methodology_inference']='after_v2_filter_cutover_time_only'
    d=d.reindex(columns=old.columns)
    joined=pd.concat([old,d],ignore_index=True).drop_duplicates('record_id').sort_values('meta_added_ts')
    joined.to_csv(root/'btc_social_snapshots.csv',index=False)
    prepared=social.prepare(social.read_records(root/'btc_social_snapshots.csv'))
    prepared.to_csv(root/'btc_social_prepared_proxy.csv',index=False)
    old_news=[json.loads(x) for x in (HERE.parent/'revision_v3_1/data/news_expanded_2026.jsonl').read_text().splitlines() if x.strip()]
    new=pd.read_csv(root/'news_extension.csv',keep_default_na=False)
    assert new.source_url.is_unique and new.title.str.split().str.len().le(25).all()
    assert pd.to_datetime(new.publication_bound_at,utc=True).ge(pd.Timestamp('2026-08-01T00:00:00Z')).all()
    for r in old_news:r['dataset_batch']='original_v31'
    news=old_news+[{**r,'dataset_batch':'aug_oct_extension'} for r in new.to_dict('records')]
    assert len({r['source_url'] for r in news})==len(news)
    (root/'news_combined_2026.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in news))
    report={'new_weekly_files':len(frames),'new_all_asset_rows':len(allrows),'new_btc_snapshots':len(d),'combined_btc_snapshots':len(joined),'post_cutover_btc_snapshots':len(prepared),'original_news':len(old_news),'new_headlines':len(new),'combined_news':len(news),'new_social_last_snapshot':str(pd.to_datetime(d.snapshot_ts,utc=True).max()),'new_news_last_publisher_bound':str(pd.to_datetime(new.publication_bound_at,utc=True).max()),'new_social_sources':audit,'provider_ref':manifest['ref'],'historical_receipt_verified':False}
    (root/'acquisition_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='new_social_sources'},indent=2))

if __name__=='__main__':main()
