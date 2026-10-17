#!/usr/bin/env python3
"""V3 research: V2 duration credibility + time-safe news text residual model."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize, brentq

HERE=Path(__file__).resolve().parent
JAY=HERE.parent
sys.path.insert(0,str(JAY));sys.path.insert(0,str(HERE))
import pp_pricing as v1
import news as nlp
spec=importlib.util.spec_from_file_location('jasper_v2',JAY/'revision_v2/pricing.py')
v2=importlib.util.module_from_spec(spec);spec.loader.exec_module(v2)
MARKET=['log_vol_ratio','abs_momentum_60','weekend','hour_sin','hour_cos']
SPECS={'v2':([],0.),'market_control_ridge1':(MARKET,1.),
       'news_count_control_ridge1':(MARKET+nlp.COUNT_FEATURES,1.),
       **{f'news_text_ridge{a:g}':(MARKET+nlp.COUNT_FEATURES+nlp.TEXT_FEATURES,a) for a in [.1,1.,10.]}}

def save(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False,default=lambda z:z.item() if isinstance(z,np.generic) else str(z))+'\n')

def augment(d):
    d=d.copy();d['abs_momentum_60']=d.signed_momentum_60.abs()
    d['weekend']=d.createdAt.dt.dayofweek.ge(5).astype(float)
    h=d.createdAt.dt.hour+d.createdAt.dt.minute/60
    d['hour_sin']=np.sin(2*np.pi*h/24);d['hour_cos']=np.cos(2*np.pi*h/24)
    return d

def load_orders(orders,market):
    bars=v1.read_market(market)
    if bars.bar_close.isna().any():
        raise ValueError('Market file contains missing timestamps; restore the complete original CSV. Do not silently remove a truncated final record.')
    return augment(v1.features(orders,bars))

def fit_residual(train,base,features,alpha):
    if not features:return {'features':[],'center':[],'scale':[],'beta':[],'alpha':alpha}
    x=train[features].to_numpy(float)
    center=np.array([float(x[:,j].mean()) if f in MARKET else 0. for j,f in enumerate(features)])
    scale=x.std(axis=0);scale[scale<1e-8]=1.
    x=np.clip((x-center)/scale,-8,8)
    y=train.realizedProfit_USDC.to_numpy(float);c=v2.cost(base,train);den=c.sum()
    def obj(b):
        eta=x@b; clipped=np.clip(eta,-20,20); mu=c*np.exp(clipped)
        loss=np.sum(mu-y*clipped)/den+.5*alpha*(b@b)
        grad=x.T@((mu-y)*((eta>-20)&(eta<20)))/den+alpha*b
        return loss,grad
    result=minimize(obj,np.zeros(len(features)),jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-12,'gtol':1e-8})
    if not result.success and np.max(abs(result.jac))>1e-5:raise RuntimeError(result.message)
    return {'features':features,'center':center.tolist(),'scale':scale.tolist(),'beta':result.x.tolist(),'alpha':alpha,'optimizer_success':bool(result.success),'max_gradient':float(np.max(abs(result.jac)))}

def predicted_cost(model,d):
    base=v2.cost(model['v2'],d);r=model['residual']
    if not r['features']:return base
    x=np.clip((d[r['features']].to_numpy(float)-r['center'])/r['scale'],-8,8)
    return base*np.exp(np.clip(x@r['beta'],-np.log(2),np.log(2)))

def candidate_multiplier(model,d):
    if model['candidate']=='v2':return v2.multiplier(model['v2'],d)
    base=model['v2'];b=d.premiumAmount_USDC.to_numpy(float)
    score=np.sqrt(predicted_cost(model,d)/(base['pooled_payout_to_premium']*b))
    raw=np.clip(model['train_normalizer']*score,.85,1.15)
    return 1+base['pricing']['weight']*(raw-1)

def fit_model(d,prepared_news,cutoff,candidate,model_spec=None):
    cutoff=pd.Timestamp(cutoff);base=v2.fit(d,cutoff)
    text_model=nlp.fit_text(prepared_news,cutoff)
    f=pd.concat([d,nlp.quote_features(d,prepared_news,text_model)],axis=1)
    tr=f[f.analysis_valid & f.createdAt.lt(cutoff) & f.closedAt.lt(cutoff)]
    features,alpha=model_spec if model_spec is not None else SPECS[candidate]
    model={'schema':'jasper-pp-news-v3','candidate':candidate,'cutoff_utc':str(cutoff),'v2':base,
           'text_model':text_model,'residual':fit_residual(tr,base,features,alpha),
           'news_live_enabled':False,'status':'retrospective_research_publication_clock_not_live_validated',
           'news_clock':'publication_proxy','latency_minutes':5,
           'training_rows':len(tr),'latest_training_settlement':str(tr.closedAt.max())}
    if candidate=='v2':model['train_normalizer']=base['pricing']['train_normalizer']
    else:
        b=tr.premiumAmount_USDC.to_numpy(float);score=np.sqrt(predicted_cost(model,tr)/(base['pooled_payout_to_premium']*b))
        model['train_normalizer']=float(brentq(lambda c:np.sum(b*np.clip(c*score,.85,1.15))-b.sum(),.00001,10000))
    return model,f

def scenario(d,m,period,policy,e):
    b=d.premiumAmount_USDC.to_numpy(float);y=d.realizedProfit_USDC.to_numpy(float)
    q=np.minimum(1,np.asarray(m)**(-e));profit=q*(b*m-y)
    day=pd.DataFrame({'day':d.day,'margin':profit}).groupby('day').margin.sum()
    return {'period':period,'policy':policy,'elasticity':e,'orders':len(d),'gross_margin_USDC':float(profit.sum()),
            'mean_order_retention':float(q.mean()),'minimum_order_retention':float(q.min()),
            'quoted_premium_change':float(np.sum(b*m)/b.sum()-1),'discounted_order_share':float(np.mean(m<1-1e-10)),
            'worst_creation_day_USDC':float(day.min())}

def choose(metrics,scenarios):
    dev=metrics[metrics.period.ne('2026-07')]
    wide={k:dev.pivot(index='period',columns='model',values=k) for k in ['RMSE_USDC','notional_weighted_poisson_deviance']}
    sm=scenarios[(scenarios.period.ne('2026-07')) & scenarios.elasticity.eq(4)].pivot(index='period',columns='policy',values='gross_margin_USDC')
    rows=[]
    for name in [k for k in SPECS if k.startswith('news_text')]:
        rm=wide['RMSE_USDC'];dv=wide['notional_weighted_poisson_deviance']
        row={'candidate':name,'mean_rmse_ratio_v2':float((rm[name]/rm.v2).mean()),
             'mean_rmse_ratio_market':float((rm[name]/rm.market_control_ridge1).mean()),
             'mean_deviance_ratio_market':float((dv[name]/dv.market_control_ridge1).mean()),
             'mean_deviance_ratio_count_control':float((dv[name]/dv.news_count_control_ridge1).mean()),
             'minimum_development_margin_difference_v2':float((sm[name]-sm.v2).min())}
        row['eligible']=bool(all(row[x]<1 for x in ['mean_rmse_ratio_v2','mean_rmse_ratio_market','mean_deviance_ratio_market','mean_deviance_ratio_count_control']) and row['minimum_development_margin_difference_v2']>=0)
        rows.append(row)
    ranks=pd.DataFrame(rows).sort_values(['mean_deviance_ratio_market','candidate'])
    eligible=ranks[ranks.eligible]
    return ranks,{'shadow_candidate':str(ranks.iloc[0].candidate),'development_selected':str(eligible.iloc[0].candidate) if len(eligible) else 'v2',
                 'live_news_enabled':False,'reason':'No live news enablement from reconstructed publication timestamps and a limited official-source corpus. July is retrospective.'}

def analyze(args):
    out=Path(args.outdir);out.mkdir(parents=True,exist_ok=True)
    d=load_orders(args.orders,args.market);raw=nlp.read_news(args.news);prepared=nlp.prepare_news(raw,'publication_proxy',5)
    metrics=[];scenarios=[];models={};frames={}
    for month in ['2026-04','2026-05','2026-06','2026-07']:
        start=pd.Timestamp(month+'-01',tz='UTC');end=start+pd.offsets.MonthBegin(1)
        for name in SPECS:
            model,f=fit_model(d,prepared,start,name);models[(month,name)]=model;frames[(month,name)]=f
            te=f[f.analysis_valid & f.createdAt.ge(start)&f.createdAt.lt(end)]
            if month!='2026-07':te=te[te.closedAt.lt(end)]
            metrics.append({'period':month,'model':name,'training_rows':model['training_rows'],**v1.metrics(te,predicted_cost(model,te))})
            mult=candidate_multiplier(model,te)
            for e in [0,1,2,4]:scenarios.append(scenario(te,mult,month,name,e))
        for e in [0,1,2,4]:scenarios.append(scenario(te,np.ones(len(te)),month,'recorded_reference',e))
        calibrated_reference=te.premiumAmount_USDC.to_numpy(float)*model['v2']['pooled_payout_to_premium']
        metrics.append({'period':month,'model':'calibrated_recorded_reference','training_rows':model['training_rows'],**v1.metrics(te,calibrated_reference)})
        print('Completed',month,flush=True)
    met=pd.DataFrame(metrics);sc=pd.DataFrame(scenarios);ranks,selection=choose(met,sc)
    shadow=selection['shadow_candidate'];july=models[('2026-07',shadow)];f=frames[('2026-07',shadow)]
    te=f[f.analysis_valid & f.month.eq('2026-07')].copy()
    # Added diagnostic after the initial comparison: match regularization exactly.
    # These controls do not change the declared selection or choose a new model.
    ablations=[];alpha=july['residual']['alpha']
    for name,features in [('market_matched_regularization',MARKET),('count_matched_regularization',MARKET+nlp.COUNT_FEATURES)]:
        am,af=fit_model(d,prepared,pd.Timestamp('2026-07-01T00:00:00Z'),name,(features,alpha))
        at=af[af.analysis_valid & af.month.eq('2026-07')]
        for e in [0,1,2,4]:
            ablations.append({'model':name,'alpha':alpha,**v1.metrics(at,predicted_cost(am,at)),**scenario(at,candidate_multiplier(am,at),'2026-07',name,e)})
    for e in [0,1,2,4]:ablations.append({'model':shadow,'alpha':alpha,**v1.metrics(te,predicted_cost(july,te)),**scenario(te,candidate_multiplier(july,te),'2026-07',shadow,e)})
    pd.DataFrame(ablations).to_csv(out/'matched_regularization_ablation.csv',index=False)
    mult=candidate_multiplier(july,te);b=te.premiumAmount_USDC.to_numpy(float)
    for e in [0,1,2,4]:
        uniform=float(np.sum(mult*b)/b.sum());scenarios.append(scenario(te,np.full(len(te),uniform),'2026-07','uniform_same_shadow_premium',e))
        if e:ret=np.minimum(1,mult**(-e)).mean();scenarios.append(scenario(te,np.full(len(te),ret**(-1/e)),'2026-07','uniform_same_shadow_retention',e))
    sc=pd.DataFrame(scenarios)
    qr=te[['source_row','createdAt','productType','premiumAmount_USDC','realizedProfit_USDC','news_count_1h','news_count_4h','news_count_24h','latest_news_available_at']].copy()
    qr['v2_multiplier']=v2.multiplier(july['v2'],te);qr['shadow_multiplier']=mult
    qr['v2_expected_payout_USDC']=v2.cost(july['v2'],te);qr['shadow_expected_payout_USDC']=predicted_cost(july,te)
    qr['recommended_multiplier']=qr.v2_multiplier;qr['recommended_premium_USDC']=b*qr.recommended_multiplier
    qr['status']='v2_fallback_news_overlay_research_only';qr.to_csv(out/'july_predictions.csv',index=False)
    met.to_csv(out/'cost_metrics.csv',index=False);sc.to_csv(out/'commercial_scenarios.csv',index=False);ranks.to_csv(out/'development_selection.csv',index=False)
    save(out/'selection.json',selection);save(out/'frozen_july_shadow_model.json',july)
    final,_=fit_model(d,prepared,pd.Timestamp('2026-07-31T17:11:48Z'),shadow)
    final['development_selected']=selection['development_selected'];save(out/'preblind_research_model.json',final)
    # Hold model coefficients fixed; only delay availability. This is a latency stress, not retuning.
    sensitivity=[]
    for lag in [5,30,60]:
        ns=nlp.prepare_news(raw,'publication_proxy',lag)
        tf=pd.concat([d,nlp.quote_features(d,ns,july['text_model'])],axis=1)
        tf=tf[tf.analysis_valid & tf.month.eq('2026-07')]
        m=candidate_multiplier(july,tf)
        sensitivity.append({'latency_minutes':lag,**v1.metrics(tf,predicted_cost(july,tf)),**{k:v for k,v in scenario(tf,m,'2026-07',shadow,4).items() if k in ['gross_margin_USDC','mean_order_retention']}})
    pd.DataFrame(sensitivity).to_csv(out/'latency_sensitivity.csv',index=False)
    # News-event exposure counts disclose the effective sample, not merely 7,603 contracts.
    coverage=f[f.analysis_valid].groupby('month').agg(orders=('source_row','size'),orders_with_news_4h=('news_count_4h',lambda x:int((x>0).sum())),orders_with_news_24h=('news_count_24h',lambda x:int((x>0).sum())))
    coverage['share_with_news_4h']=coverage.orders_with_news_4h/coverage.orders;coverage.to_csv(out/'news_order_coverage.csv')
    prepared.assign(month=prepared.available_at.dt.strftime('%Y-%m')).groupby(['month','source']).size().rename('documents').to_csv(out/'news_monthly_counts.csv')
    # Conditional paired-day uncertainty, without claiming independence across adjacent days.
    e=4;y=te.realizedProfit_USDC.to_numpy(float);v2m=v2.multiplier(july['v2'],te)
    diff=np.minimum(1,mult**-e)*(b*mult-y)-np.minimum(1,v2m**-e)*(b*v2m-y)
    delta=pd.DataFrame({'day':te.day,'delta':diff}).groupby('day').delta.sum().to_numpy()
    rng=np.random.default_rng(271828);draws=delta[rng.integers(0,len(delta),(2000,len(delta)))].sum(axis=1)
    save(out/'conditional_bootstrap.json',{'comparator':'V2','shadow':shadow,'july_e4_margin_difference':float(delta.sum()),'conditional_95pct_interval':np.quantile(draws,[.025,.975]).tolist(),'boundary':'Conditional on model, recorded buyers and assumed elasticity; excludes model selection, timestamp error, dependence across adjacent days and unknown demand.'})
    save(out/'input_manifest.json',{str(Path(p).name):{'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest(),'bytes':Path(p).stat().st_size} for p in [args.orders,args.market,args.news]})
    save(out/'audit.json',{'raw_orders':len(d),'valid_orders':int(d.analysis_valid.sum()),'raw_news_documents':len(raw),'prepared_proxy_documents':len(prepared),'observed_clock_documents':len(nlp.prepare_news(raw,'observed')),'text_training_documents_prejuly':july['text_model']['training_documents'],'all_atm':True,'news_live_enabled':False,'news_inference_api_calls':0,'selection':selection})
    print(json.dumps(selection,indent=2));print(met[met.period.eq('2026-07')][['model','RMSE_USDC','notional_weighted_poisson_deviance']].to_string(index=False))

def predict(args):
    model=json.loads(Path(args.model).read_text())
    if model.get('schema')!='jasper-pp-news-v3':raise ValueError('Unknown model schema')
    if model.get('news_live_enabled'):raise ValueError('This research package has no validated live-news calibration')
    d=load_orders(args.orders,args.market);raw=nlp.read_news(args.news)
    # Recommendation always uses inherited audited V2 fallbacks; shadow score is opt-in.
    result=v2.quotes(model['v2'],d)
    result['news_status']='disabled_reconstructed_training_corpus';result['shadow_expected_payout_USDC']=np.nan
    result['shadow_multiplier']=np.nan
    if args.shadow_publication_proxy:
        ns=nlp.prepare_news(raw,'publication_proxy',model['latency_minutes'])
        f=pd.concat([d,nlp.quote_features(d,ns,model['text_model'])],axis=1);valid=f.quote_valid
        result.loc[valid,'shadow_expected_payout_USDC']=predicted_cost(model,f.loc[valid]);result.loc[valid,'shadow_multiplier']=candidate_multiplier(model,f.loc[valid])
        result['news_status']='publication_proxy_shadow_only'
    elif args.shadow_observed:
        import sqlite3
        from collect_news import health
        if not args.collector_db or not Path(args.collector_db).is_file():raise ValueError('Observed shadow requires the existing collector database for per-quote health checks')
        config=json.loads(Path(args.feeds).read_text());db=sqlite3.connect(args.collector_db)
        digest=hashlib.sha256(Path(args.model).read_bytes()).hexdigest()
        if 'text_model_sha256' not in raw:raw['text_model_sha256']=''
        matched=raw[raw.text_model_sha256.eq(digest)]
        ns=nlp.prepare_news(matched,'observed');f=pd.concat([d,nlp.quote_features(d,ns,model['text_model'])],axis=1)
        # A failed/stale feed is never translated into a reassuring zero-news feature.
        healthy=pd.Series([health(db,config,t.isoformat())['healthy'] if pd.notna(t) else False for t in d.createdAt],index=d.index)
        db.close()
        # Do not turn a model-version mismatch into an apparent absence of news.
        mismatch=raw[~raw.text_model_sha256.eq(digest)].first_seen_at.dropna()
        model_ready=pd.Series([not ((mismatch<t)&(mismatch>=t-pd.Timedelta(hours=24))).any() if pd.notna(t) else False for t in d.createdAt],index=d.index)
        valid=f.quote_valid & healthy & model_ready & ~result.is_before_model_cutoff
        result.loc[valid,'shadow_expected_payout_USDC']=predicted_cost(model,f.loc[valid]);result.loc[valid,'shadow_multiplier']=candidate_multiplier(model,f.loc[valid])
        result['news_status']='observed_shadow_unavailable_feed_health_model_version_or_quote_clock'
        result.loc[valid,'news_status']='observed_shadow_only_rss_training_domain_shift'
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);result.to_csv(args.output,index=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    for cmd in ['analyze','predict']:
        a=s.add_parser(cmd);a.add_argument('--orders',required=True);a.add_argument('--market',required=True);a.add_argument('--news',default=str(HERE/'data/official_news_2026.jsonl'))
        if cmd=='analyze':a.add_argument('--outdir',default=str(HERE/'reference_results'))
        else:
            a.add_argument('--model',required=True);a.add_argument('--output',required=True)
            group=a.add_mutually_exclusive_group();group.add_argument('--shadow-publication-proxy',action='store_true');group.add_argument('--shadow-observed',action='store_true')
            a.add_argument('--collector-db');a.add_argument('--feeds',default=str(HERE/'data/feeds.json'))
    args=p.parse_args();analyze(args) if args.command=='analyze' else predict(args)

if __name__=='__main__':main()
