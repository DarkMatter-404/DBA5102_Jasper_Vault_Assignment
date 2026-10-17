"""BTC X sentiment adapter. Historical availability is explicitly a proxy."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
CUTOVER=pd.Timestamp('2026-02-17T06:03:00Z')
ACTIVITY=['social_score_available','social_log_posts','social_put','social_silent']
SENTIMENT=['social_directional_sentiment','social_abs_sentiment']
TIME_COLUMNS=['snapshot_ts','meta_added_ts','meta_expires_ts','session_end_proxy','available_at','first_seen_at','nlp_ready_at']

def read_records(path):
    p=Path(path)
    d=pd.read_json(p,lines=True) if p.suffix=='.jsonl' else pd.read_csv(p)
    for c in TIME_COLUMNS:
        if c not in d:d[c]=pd.NaT
        d[c]=pd.to_datetime(d[c],utc=True,errors='coerce',format='mixed')
    return d

def validate(d):
    needed=['symbol','snapshot_ts','meta_added_ts','meta_expires_ts','meta_duration_sec','sentiment_posts_total','sentiment_posts_pos','sentiment_posts_neu','sentiment_posts_neg','sentiment_mean_score']
    if set(needed)-set(d):raise ValueError('Missing source columns: '+str(set(needed)-set(d)))
    if d[needed[:5]].isna().any().any():raise ValueError('Missing session timestamps or symbol')
    nums=['meta_duration_sec','sentiment_posts_total','sentiment_posts_pos','sentiment_posts_neu','sentiment_posts_neg']
    if not np.isfinite(d[nums].to_numpy(float)).all() or (d[nums]<0).any().any():raise ValueError('Invalid duration or post counts')
    counts=d[nums[1:]].to_numpy(float)
    if not np.equal(counts,np.floor(counts)).all():raise ValueError('Post counts must be integers')
    if not np.array_equal(d.sentiment_posts_total,d[['sentiment_posts_pos','sentiment_posts_neu','sentiment_posts_neg']].sum(axis=1)):raise ValueError('Post counts do not reconcile')
    s=d.sentiment_mean_score.dropna()
    if not np.isfinite(s).all() or not s.between(-1,1).all():raise ValueError('Sentiment must be in [-1,1] or missing')
    if (d.meta_expires_ts<d.meta_added_ts).any() or (d.snapshot_ts-d.meta_added_ts).abs().gt(pd.Timedelta(minutes=1)).any():raise ValueError('Inconsistent admission timestamps')

def prepare(d,clock='session_end_proxy',latency_minutes=5):
    if clock not in ['session_end_proxy','observed']:raise ValueError('Unknown social clock')
    if not np.isfinite(latency_minutes) or latency_minutes<0:raise ValueError('Invalid latency')
    d=d.copy();validate(d)
    # No provider market fields are read by any model feature function.
    end=d.meta_added_ts+pd.to_timedelta(d.meta_duration_sec,unit='s')
    d['session_end_proxy']=pd.concat([end,d.meta_expires_ts],axis=1).max(axis=1)
    d['available_at']=d.session_end_proxy+pd.Timedelta(minutes=latency_minutes)
    if clock=='observed':
        ok=d.first_seen_at.notna() & d.nlp_ready_at.notna()
        ok &= d.get('clock_quality',pd.Series('',index=d.index)).eq('observed_local')
        d=d[ok].copy()
        d['available_at']=d[['available_at','first_seen_at','nlp_ready_at']].max(axis=1)
    d=d[d.symbol.eq('BTC') & d.meta_added_ts.ge(CUTOVER)].copy()
    # Same historical session is immutable; keep the first observed representation.
    d=d.sort_values(['available_at','record_id']).drop_duplicates(['symbol','meta_added_ts'],keep='first')
    return d.reset_index(drop=True)

def quote_features(quotes,prepared,max_age_hours=4):
    if not np.isfinite(max_age_hours) or max_age_hours<=0:raise ValueError('Invalid maximum age')
    s=prepared.sort_values(['available_at','record_id']).reset_index(drop=True)
    times=s.available_at.astype('int64').to_numpy();rows=[]
    for q in quotes.itertuples():
        row={f:0. for f in ACTIVITY+SENTIMENT}
        row.update(social_available=0.,social_record_id='',social_available_at='',social_session_start='',social_age_hours=np.nan,social_mean_score=np.nan,social_posts_total=np.nan,social_status='missing_or_stale')
        if pd.isna(q.createdAt):rows.append(row);continue
        j=np.searchsorted(times,q.createdAt.value,side='left')-1
        if j<0:rows.append(row);continue
        r=s.iloc[j];age=(q.createdAt-r.meta_added_ts).total_seconds()/3600
        if not 0<=age<=max_age_hours:rows.append(row);continue
        has=bool(pd.notna(r.sentiment_mean_score) and r.sentiment_posts_total>0)
        mean=float(r.sentiment_mean_score) if has else 0.
        silent=str(r.get('sentiment_is_silent','')).lower()=='true'
        row.update(social_available=1.,social_score_available=float(has),social_log_posts=float(np.log1p(r.sentiment_posts_total)),social_put=float(q.put),social_silent=float(silent),social_directional_sentiment=(1-2*q.put)*mean,social_abs_sentiment=abs(mean),social_record_id=r.record_id,social_available_at=r.available_at.isoformat(),social_session_start=r.meta_added_ts.isoformat(),social_age_hours=age,social_mean_score=float(r.sentiment_mean_score) if has else np.nan,social_posts_total=int(r.sentiment_posts_total),social_status='fresh_proxy' if has else 'fresh_snapshot_missing_score')
        rows.append(row)
    return pd.DataFrame(rows,index=quotes.index)

def build(root=HERE/'data/instrumetriq',output=HERE/'data/btc_social_snapshots.csv'):
    root=Path(root);manifest=json.loads((root/'source_manifest.json').read_text());frames=[];audit=[]
    for f in manifest['files']:
        p=root/'raw'/Path(f['path']).name;b=p.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if len(b)!=f['size'] or blob!=f['sha']:raise ValueError('Source hash mismatch: '+str(p))
        d=pd.read_csv(p);d['sample_file']=p.name;d['source_sha256']=hashlib.sha256(b).hexdigest();frames.append(d)
        audit.append({'file':p.name,'rows':len(d),'btc_rows':int(d.symbol.eq('BTC').sum()),'sha256':hashlib.sha256(b).hexdigest(),'git_blob_sha':blob})
    all_rows=pd.concat(frames,ignore_index=True);d=all_rows[all_rows.symbol.eq('BTC')].copy()
    keep=['symbol','snapshot_ts','meta_added_ts','meta_expires_ts','meta_duration_sec','meta_archive_schema_version','sentiment_posts_total','sentiment_posts_pos','sentiment_posts_neu','sentiment_posts_neg','sentiment_mean_score','sentiment_is_silent','sample_file','source_sha256']
    d=d[keep].copy();d['record_id']=['instrumetriq_'+hashlib.sha256((r.symbol+'|'+r.meta_added_ts).encode()).hexdigest()[:16] for r in d.itertuples()]
    d['clock_quality']='reconstructed_session_end_not_historical_receipt';d['first_seen_at']='';d['nlp_ready_at']=''
    d['methodology_inference']=np.where(pd.to_datetime(d.meta_added_ts,utc=True)>=CUTOVER,'after_v2_filter_cutover_time_only','excluded_pre_cutover')
    Path(output).parent.mkdir(parents=True,exist_ok=True);d.to_csv(output,index=False)
    prepared=prepare(read_records(output));prepared.to_csv(Path(output).with_name('btc_social_prepared_proxy.csv'),index=False)
    summary={'raw_rows':len(all_rows),'unique_symbols':int(all_rows.symbol.nunique()),'weekly_sample_files':len(frames),'btc_rows':len(d),'btc_post_cutover_rows':len(prepared),'btc_nonmissing_hybrid_scores':int(d.sentiment_mean_score.notna().sum()),'files':audit,'source_ref':manifest['ref'],'license':'CC BY 4.0 sample data; attribution to Instrumetriq; extracted BTC fields and added clocks/IDs; not endorsed by provider'}
    (root/'acquisition_audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='files'},indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default=str(HERE/'data/instrumetriq'));p.add_argument('--output',default=str(HERE/'data/btc_social_snapshots.csv'));a=p.parse_args();build(a.root,a.output)
