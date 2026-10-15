#!/usr/bin/env python3
"""V3.1 reproducible research: frozen news model plus a small X sentiment overlay."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import social

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('jasper_v3',HERE.parent/'revision_v3/pricing.py')
v3=importlib.util.module_from_spec(spec);spec.loader.exec_module(v3)
nlp=v3.nlp;v2=v3.v2;v1=v3.v1
BASE_SPECS={'v2':([],0.),'market':(v3.MARKET+['put'],1.),'news_counts':(v3.MARKET+['put']+nlp.COUNT_FEATURES,1.),'news_text':(v3.MARKET+['put']+nlp.COUNT_FEATURES+nlp.TEXT_FEATURES,1.)}
OVERLAYS={'news_social_activity':social.ACTIVITY,'news_social_sentiment':social.ACTIVITY+social.SENTIMENT}

def fit_overlay(news_model,frame,cutoff,features):
    tr=frame[frame.analysis_valid & frame.createdAt.lt(cutoff) & frame.closedAt.lt(cutoff) & frame.social_available.eq(1)].copy()
    x=tr[features].to_numpy(float)
    center=np.array([float(tr[f].mean()) if f=='social_log_posts' and len(tr) else 0. for f in features])
    scale=x.std(axis=0) if len(tr) else np.ones(len(features));scale[scale<1e-8]=1.
    enabled=len(tr)>=30
    beta=np.zeros(len(features));success=True
    if enabled:
        x=np.clip((x-center)/scale,-8,8);c=v3.predicted_cost(news_model,tr);y=tr.realizedProfit_USDC.to_numpy(float)
        def objective(b):
            eta=x@b;z=np.clip(eta,-20,20);mu=c*np.exp(z)
            return np.sum(mu-y*z)/c.sum()+5*(b@b),x.T@((mu-y)*((eta>-20)&(eta<20)))/c.sum()+10*b
        opt=minimize(objective,beta,jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-12,'gtol':1e-8})
        if not opt.success and abs(opt.jac).max()>1e-5:raise RuntimeError(opt.message)
        beta=opt.x;success=bool(opt.success)
    return {'features':features,'center':center.tolist(),'scale':scale.tolist(),'beta':beta.tolist(),'alpha':10.,'enabled':enabled,'training_rows':len(tr),'training_social_records':int(tr.social_record_id.nunique()),'training_creation_days':int(tr.day.nunique()),'maximum_cost_factor':1.10,'optimizer_success':success,'latest_training_settlement':str(tr.closedAt.max()),'offset':'frozen matched news-text model'}

def overlay_factor(model,frame):
    ans=np.ones(len(frame));ok=frame.social_available.eq(1).to_numpy()
    if model['enabled'] and ok.any():
        x=np.clip((frame.loc[ok,model['features']].to_numpy(float)-model['center'])/model['scale'],-8,8)
        ans[ok]=np.exp(np.clip(x@model['beta'],-np.log(model['maximum_cost_factor']),np.log(model['maximum_cost_factor'])))
    return ans

def overlay_cost(news_model,overlay,frame):
    return v3.predicted_cost(news_model,frame)*overlay_factor(overlay,frame)

def overlay_multiplier(news_model,overlay,frame):
    base=news_model['v2'];b=frame.premiumAmount_USDC.to_numpy(float)
    score=np.sqrt(overlay_cost(news_model,overlay,frame)/(base['pooled_payout_to_premium']*b))
    # Keep the news normalizer: absent/stale social data gives exactly its quote.
    raw=np.clip(news_model['train_normalizer']*score,.85,1.15)
    return 1+base['pricing']['weight']*(raw-1)

def paired_interval(frame,ma,mb):
    b=frame.premiumAmount_USDC.to_numpy(float);y=frame.realizedProfit_USDC.to_numpy(float)
    a=np.minimum(1,ma**-4)*(b*ma-y);c=np.minimum(1,mb**-4)*(b*mb-y)
    byday=pd.DataFrame({'day':frame.day,'delta':a-c}).groupby('day').delta.sum().to_numpy()
    rng=np.random.default_rng(271828);draw=byday[rng.integers(0,len(byday),(2000,len(byday)))].sum(axis=1)
    return {'difference_USDC':float(byday.sum()),'conditional_95pct_interval_USDC':np.quantile(draw,[.025,.975]).tolist(),'days':len(byday),'days_with_nonzero_difference':int((abs(byday)>1e-9).sum()),'interpretation':'Paired UTC creation-day resampling, fixed models and assumed elasticity 4. Excludes selection, feed timing uncertainty and dependence between days; not causal profit evidence.'}

def score_demo(model,quote):
    d=pd.DataFrame([quote]);d['createdAt']=pd.to_datetime(d.createdAt,utc=True)
    if d.createdAt.iloc[0]<pd.Timestamp(model['cutoff_utc']):raise ValueError('Quote precedes model cutoff')
    if d.premiumAmount_USDC.iloc[0]<=0 or d.productType.iloc[0] not in v2.TENORS or d.put.iloc[0] not in [0,1]:raise ValueError('Invalid reference or contract')
    # Demo input contains only assembled quote-time features, no payoff labels.
    news=model['news'];b=float(d.premiumAmount_USDC.iloc[0]);out={}
    out['reference_premium_USDC']=b
    for name,c,m in [('v2',v2.cost(news['v2'],d),v2.multiplier(news['v2'],d)),('news_text',v3.predicted_cost(news,d),v3.candidate_multiplier(news,d))]+[(n,overlay_cost(news,o,d),overlay_multiplier(news,o,d)) for n,o in model['overlays'].items()]:
        out[name]={'expected_payout_USDC':float(c[0]),'multiplier':float(m[0]),'premium_USDC':float(b*m[0])}
    out['recommended_model']='v2';out['status']='retrospective_demo_only_social_and_news_not_enabled'
    return out

def analyze(a):
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    d=v3.load_orders(a.orders,a.market);news=nlp.prepare_news(nlp.read_news(a.news),'publication_proxy',5)
    raw_social=social.read_records(a.social);prepared=social.prepare(raw_social)
    sf=social.quote_features(d,prepared);metrics=[];scenarios=[];models={};fold_audit=[];prediction_frames={}
    for month in ['2026-04','2026-05','2026-06','2026-07']:
        start=pd.Timestamp(month+'-01',tz='UTC');end=start+pd.offsets.MonthBegin(1)
        base_models={}
        for name,mspec in BASE_SPECS.items():
            m,f=v3.fit_model(d,news,start,name,mspec);base_models[name]=m
        f=pd.concat([f,sf],axis=1)
        overlays={name:fit_overlay(base_models['news_text'],f,start,features) for name,features in OVERLAYS.items()}
        te=f[f.analysis_valid & f.createdAt.ge(start) & f.createdAt.lt(end)].copy()
        if month!='2026-07':te=te[te.closedAt.lt(end)].copy()
        predictions={name:(v3.predicted_cost(m,te),v3.candidate_multiplier(m,te)) for name,m in base_models.items()}
        predictions.update({name:(overlay_cost(base_models['news_text'],o,te),overlay_multiplier(base_models['news_text'],o,te)) for name,o in overlays.items()})
        for name,(cost,mult) in predictions.items():
            for population,mask in [('all',np.ones(len(te),dtype=bool)),('fresh_social',te.social_available.eq(1).to_numpy())]:
                if mask.any():
                    metrics.append({'period':month,'model':name,'population':population,'orders':int(mask.sum()),**v1.metrics(te.loc[mask],cost[mask])})
                    for e in [0,1,2,4]:scenarios.append({'population':population,**v3.scenario(te.loc[mask],mult[mask],month,name,e)})
            te[name+'_cost']=cost;te[name+'_multiplier']=mult
        for e in [0,1,2,4]:scenarios.append({'population':'all',**v3.scenario(te,np.ones(len(te)),month,'recorded_reference',e)})
        models[month]={'schema':'jasper-news-social-v3.1','cutoff_utc':start.isoformat(),'news':base_models['news_text'],'overlays':overlays,'recommended':'v2','live_news_enabled':False,'live_social_enabled':False,'social_clock':'session_end_proxy','max_social_age_hours':4}
        fold_audit.append({'period':month,'base_training_rows':base_models['news_text']['training_rows'],'text_training_documents':base_models['news_text']['text_model']['training_documents'],**overlays['news_social_sentiment']})
        prediction_frames[month]=te
        print('Completed',month,'orders',len(te),'fresh social',int(te.social_available.sum()),flush=True)
    pd.DataFrame(metrics).to_csv(out/'cost_metrics.csv',index=False);pd.DataFrame(scenarios).to_csv(out/'commercial_scenarios.csv',index=False)
    v3.save(out/'fold_training_audit.json',fold_audit);v3.save(out/'frozen_july_model.json',models['2026-07'])
    full=pd.concat(prediction_frames.values()).sort_values('createdAt');full.to_csv(out/'evaluation_predictions.csv',index=False)
    coverage=pd.concat([d,sf],axis=1);coverage=coverage[coverage.analysis_valid]
    coverage.groupby('month').agg(orders=('source_row','size'),fresh_social_orders=('social_available','sum'),scored_social_orders=('social_score_available','sum'),distinct_social_records=('social_record_id',lambda x:int(x[x.ne('')].nunique()))).to_csv(out/'social_order_coverage.csv')
    permonth=[]
    for month,g in coverage.groupby('month'):
        q=g[g.social_available.eq(1)];permonth.append({'month':month,'fresh_social_creation_days':int(q.day.nunique()),'fresh_share':float(g.social_available.mean())})
    pd.DataFrame(permonth).to_csv(out/'social_day_coverage.csv',index=False)
    news.assign(month=news.available_at.dt.strftime('%Y-%m')).groupby(['month','source']).size().rename('headlines').to_csv(out/'news_monthly_counts.csv')
    # News exposure is rebuilt using the frozen July text transform; counts are transform-independent.
    nf=nlp.quote_features(d,news,models['2026-07']['news']['text_model'])
    nc=pd.concat([d[['month','analysis_valid']],nf],axis=1);nc=nc[nc.analysis_valid]
    nc.groupby('month').agg(orders=('analysis_valid','size'),news_4h=('news_count_4h',lambda x:int(x.gt(0).sum())),news_24h=('news_count_24h',lambda x:int(x.gt(0).sum()))).to_csv(out/'news_order_coverage.csv')
    july=prediction_frames['2026-07'];jm=models['2026-07'];sent=july.news_social_sentiment_multiplier.to_numpy()
    v3.save(out/'conditional_comparisons.json',{name:paired_interval(july,sent,july[name+'_multiplier'].to_numpy()) for name in ['v2','news_text','news_social_activity']})
    stress=[]
    for lag in [5,60,1440]:
        lagged=social.quote_features(d,social.prepare(raw_social,latency_minutes=lag))
        f=pd.concat([d,nf,lagged],axis=1);te=f[f.analysis_valid & f.month.eq('2026-07')]
        o=jm['overlays']['news_social_sentiment'];cost=overlay_cost(jm['news'],o,te);mult=overlay_multiplier(jm['news'],o,te)
        stress.append({'social_latency_minutes':lag,'fresh_social_orders':int(te.social_available.sum()),**v1.metrics(te,cost),**v3.scenario(te,mult,'2026-07','news_social_sentiment',4)})
    pd.DataFrame(stress).to_csv(out/'social_latency_sensitivity.csv',index=False)
    # Earliest eligible quote: deterministic, never selected on return or uplift.
    demo=july[july.social_score_available.eq(1)].sort_values(['createdAt','source_row']).iloc[0]
    cols=['source_row','createdAt','productType','premiumAmount_USDC','put']+v3.MARKET+nlp.COUNT_FEATURES+nlp.TEXT_FEATURES+['social_available']+social.ACTIVITY+social.SENTIMENT
    quote={k:demo[k] for k in cols};v3.save(out/'demo_quote_features.json',quote)
    detail=score_demo(jm,quote)
    record=prepared[prepared.record_id.eq(demo.social_record_id)].iloc[0]
    detail.update(quote_created_at=demo.createdAt.isoformat(),source_row=int(demo.source_row),contract='put' if demo.put else 'call',duration_seconds=int(demo.productType),social_record_id=demo.social_record_id,social_available_at=demo.social_available_at,social_session_start=demo.social_session_start,social_mean_score=float(demo.social_mean_score),social_posts_total=int(demo.social_posts_total),lexicon_counts={k:int(record['sentiment_posts_'+k]) for k in ['pos','neu','neg']},source_sample=record.sample_file,social_age_hours=float(demo.social_age_hours),news_4h=int(demo.news_count_4h),news_24h=int(demo.news_count_24h),social_cost_factor=float(overlay_factor(jm['overlays']['news_social_sentiment'],pd.DataFrame([demo]))[0]))
    v3.save(out/'demo_result.json',detail)
    v3.save(out/'input_manifest.json',{str(Path(p).name):{'bytes':Path(p).stat().st_size,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in [a.orders,a.market,a.news,a.social,HERE/'PROTOCOL.md']})
    v3.save(out/'decision.json',{'recommended_model':'v2','news_enabled':False,'social_enabled':False,'reason':'Weekly convenience samples and reconstructed clocks do not establish live availability; July was already explored. See matched incremental comparisons before claiming improvement.','raw_news':len(news),'btc_raw_snapshots':len(raw_social),'post_cutover_snapshots':len(prepared),'observed_historical_social_records':len(social.prepare(raw_social,'observed')),'july_fresh_social_orders':int(july.social_available.sum())})
    print(pd.DataFrame(metrics).query("period=='2026-07' and population=='all'")[['model','RMSE_USDC','notional_weighted_poisson_deviance']].to_string(index=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('analyze');a.add_argument('--orders',required=True);a.add_argument('--market',required=True);a.add_argument('--news',default=str(HERE/'data/news_expanded_2026.jsonl'));a.add_argument('--social',default=str(HERE/'data/btc_social_snapshots.csv'));a.add_argument('--outdir',default=str(HERE/'reference_results'))
    a=s.add_parser('demo');a.add_argument('--model',default=str(HERE/'reference_results/frozen_july_model.json'));a.add_argument('--quote',default=str(HERE/'reference_results/demo_quote_features.json'))
    a=p.parse_args()
    if a.command=='analyze':analyze(a)
    else:print(json.dumps(score_demo(json.loads(Path(a.model).read_text()),json.loads(Path(a.quote).read_text())),indent=2))

if __name__=='__main__':main()
