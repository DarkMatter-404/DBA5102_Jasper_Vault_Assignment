#!/usr/bin/env python3
"""Combined PP pricing experiment: frozen duration, market, news and X sentiment.

Research replay uses reconstructed clocks. Observed mode requires receipt logs
and a feed-health record. No fitting occurs in this module.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;JAY=HERE.parent
sys.path.insert(0,str(JAY/'revision_v3_1'))
import pricing as v31
v3=v31.v3;v2=v3.v2;v1=v3.v1;nlp=v3.nlp;social=v31.social
VARIANTS=['duration','market_news','news_social_activity','combined_sentiment']

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,obj):v3.save(path,obj)
def model():return json.loads((HERE/'models/frozen_components.json').read_text())

def normalize(raw,keep_outcomes=False):
    d=raw.copy()
    for c in ['createdAt','expirationDate']:
        d[c]=pd.to_datetime(d[c],utc=True,format='mixed',errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    if not keep_outcomes:d['closedAt']=np.nan;d['realizedProfit_USDC']=np.nan
    return d

def references(raw):
    b=pd.to_numeric(raw.premiumAmount_USDC,errors='coerce').copy()
    origin=pd.Series(np.where(b.gt(0),'recorded_premium','missing'),index=raw.index)
    if {'apiBasePrice_per_BTC_USDC','markup_per_BTC_USDC'}<=set(raw):
        api=pd.to_numeric(raw.apiBasePrice_per_BTC_USDC,errors='coerce');mark=pd.to_numeric(raw.markup_per_BTC_USDC,errors='coerce')
        qty=pd.to_numeric(raw.quantity_BTC,errors='coerce');proxy=qty*(api+mark)
        ok=b.isna()&api.gt(0)&mark.ge(0)&qty.gt(0)&proxy.gt(0)&np.isfinite(proxy)
        b.loc[ok]=proxy[ok];origin.loc[ok]='conditional_api_plus_markup_not_verified_live'
    return b.where(b.gt(0)&np.isfinite(b)),origin

def assemble(d,news_path,social_path,m,clock='research_proxy',latency=5,health=None):
    news=nlp.prepare_news(nlp.read_news(news_path),'publication_proxy' if clock=='research_proxy' else 'observed',latency)
    soc=social.prepare(social.read_records(social_path),'session_end_proxy' if clock=='research_proxy' else 'observed',latency)
    f=pd.concat([d,nlp.quote_features(d,news,m['news']['text_model']),social.quote_features(d,soc)],axis=1)
    f['clock_mode']=clock
    # A sparse research sample's zero count means no sampled article, not no news.
    f['news_clock_admitted']=(f.createdAt.ge(pd.Timestamp('2026-02-01T00:00:00Z'))&f.createdAt.lt(pd.Timestamp('2026-10-15T00:00:00Z'))) if clock=='research_proxy' else False
    if clock=='observed':
        ok=pd.Series(False,index=f.index)
        if health and health.get('healthy') is True:
            stamp=pd.Timestamp(health['asof_utc']);age=(f.createdAt-stamp).dt.total_seconds()
            ok=age.between(0,600)
        f['news_clock_admitted']=ok
    return f

def relative_components(m,f):
    """Exact cancellation of the reference premium; no fake price imputation."""
    news=m['news'];base=news['v2'];r=news['residual']
    ratio=f.productType.map(lambda t:base['tenor_ratios'].get(str(int(t)),base['pooled_payout_to_premium'])).to_numpy(float)
    x=np.clip((f[r['features']].to_numpy(float)-r['center'])/r['scale'],-8,8)
    news_ratio=ratio*np.exp(np.clip(x@r['beta'],-np.log(2),np.log(2)))
    def multiplier(cost_ratio):
        raw=np.clip(news['train_normalizer']*np.sqrt(cost_ratio/base['pooled_payout_to_premium']),.85,1.15)
        return 1+base['pricing']['weight']*(raw-1)
    activity=news_ratio*v31.overlay_factor(m['overlays']['news_social_activity'],f)
    combined=news_ratio*v31.overlay_factor(m['overlays']['news_social_sentiment'],f)
    costs={'duration':ratio,'market_news':news_ratio,'news_social_activity':activity,'combined_sentiment':combined}
    mults={k:(v2.multiplier(base,f) if k=='duration' else multiplier(v)) for k,v in costs.items()}
    return costs,mults

def predict_frame(f,m,b,origin):
    eligible=f.contract_valid&f.quote_time_valid&f.createdAt.ge(pd.Timestamp(m['cutoff_utc']))
    full=eligible&f.market_valid&f.news_clock_admitted
    cols=['source_row','createdAt','productType','optionType','quantity_BTC','strikePrice','market_valid','market_age_seconds','bar_close','contract_valid','quote_time_valid','news_count_4h','news_count_24h','latest_news_available_at','social_available','social_record_id','social_available_at','social_session_start','social_age_hours','social_mean_score','social_posts_total']
    q=f[cols].copy();q['csv_line']=q.source_row+2;q['reference_premium_USDC']=b;q['reference_origin']=origin
    base=m['news']['v2'];r=np.full(len(f),np.nan);mult=np.full(len(f),np.nan)
    r[eligible]=f.loc[eligible,'productType'].map(lambda t:base['tenor_ratios'].get(str(int(t)),base['pooled_payout_to_premium']))
    mult[eligible]=v2.multiplier(base,f.loc[eligible])
    for name in VARIANTS:q[name+'_cost_per_reference']=r;q[name+'_multiplier']=mult
    if full.any():
        costs,mults=relative_components(m,f.loc[full])
        for name in VARIANTS:q.loc[full,name+'_cost_per_reference']=costs[name];q.loc[full,name+'_multiplier']=mults[name]
    q['pricing_multiplier']=q.combined_sentiment_multiplier
    q['experimental_premium_USDC']=b*q.pricing_multiplier
    q['expected_payout_USDC']=b*q.combined_sentiment_cost_per_reference
    q['full_component_eligible']=full
    q['social_layer_applied']=full&f.social_available.eq(1)
    q['status']='withheld_contract_time_or_cutoff'
    q.loc[eligible,'status']='duration_component_fallback_missing_market_or_observed_news_health'
    q.loc[full,'status']='market_news_component_social_missing_or_stale'
    q.loc[q.social_layer_applied,'status']='combined_news_social_experiment'
    q['reference_compatible_required']=True;q['official_base_mapping_confirmed']=False
    q['result_kind']=np.where(f.clock_mode.eq('research_proxy'),'research_replay_not_a_profit_score','observed_clock_shadow_quote')
    return q

def summarize(q):
    rows=[]
    populations={'all_valid_factors':q.pricing_multiplier.notna(),'fresh_market_factors':q.full_component_eligible,'matched_absolute_fresh_market':q.full_component_eligible&q.reference_premium_USDC.notna(),'all_conditional_absolute_including_fallback':q.pricing_multiplier.notna()&q.reference_premium_USDC.notna(),'social_applied':q.social_layer_applied}
    for pop,mask in populations.items():
        if not mask.any():continue
        for name in VARIANTS:
            v=q.loc[mask,name+'_multiplier'];b=q.loc[mask,'reference_premium_USDC'];ab=b.notna()
            rows.append({'population':pop,'component':name,'rows':int(mask.sum()),'mean_multiplier':float(v.mean()),'minimum_multiplier':float(v.min()),'maximum_multiplier':float(v.max()),'discounted_share':float(v.lt(1-1e-10).mean()),'assumed_retention_e4':float(np.minimum(1,v**-4).mean()),'absolute_quote_rows':int(ab.sum()),'reference_total_USDC':float(b[ab].sum()) if ab.any() else None,'quoted_total_USDC':float((b[ab]*v[ab]).sum()) if ab.any() else None,'aggregate_quote_change':float((b[ab]*v[ab]).sum()/b[ab].sum()-1) if ab.any() else None,'actual_profit':None,'validation_RMSE':None})
    return pd.DataFrame(rows)

def historical_evidence(a,bars,m,out):
    # Only score the frozen pre-July model; never train on July or validation.
    tr=v3.augment(v1.features(a.training,bars))
    f=assemble(tr,a.news,a.social,m)
    te=f[f.analysis_valid&f.month.eq('2026-07')].copy()
    costs,mults=relative_components(m,te);rows=[];scenarios=[]
    for name in VARIANTS:
        pred=te.premiumAmount_USDC.to_numpy(float)*costs[name]
        rows.append({'component':name,'period':'2026-07_retrospective',**v1.metrics(te,pred)})
        for e in [0,1,2,4]:scenarios.append(v3.scenario(te,mults[name],'2026-07_retrospective',name,e))
    for e in [0,1,2,4]:scenarios.append(v3.scenario(te,np.ones(len(te)),'2026-07_retrospective','recorded_reference_proxy',e))
    pd.DataFrame(rows).to_csv(out/'historical_july_cost_metrics.csv',index=False)
    pd.DataFrame(scenarios).to_csv(out/'historical_july_commercial_scenarios.csv',index=False)
    return len(te)

def run(a):
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    frozen_path=HERE/'models/frozen_components.json';frozen_hash=digest(frozen_path);m=model()
    raw=pd.read_csv(a.validation);source_hash=digest(a.validation)
    if raw.realizedProfit_USDC.notna().any():raise ValueError('Outcomes are now available: use a separate scoring-only evaluation. Do not refit this experiment.')
    cleaned=normalize(raw);path=out/'inference_input.csv';cleaned.to_csv(path,index=False)
    bars=v1.read_market(a.market)
    if bars.bar_close.isna().any():raise ValueError('Incomplete or invalid market input')
    d=v3.augment(v1.features(path,bars));b,origin=references(raw)
    health=json.loads(Path(a.news_health).read_text()) if a.news_health else None
    f=assemble(d,a.news,a.social,m,a.clock,health=health)
    q=predict_frame(f,m,b,origin);q.to_csv(out/'validation_predictions.csv',index=False)
    summary=summarize(q);summary.to_csv(out/'component_comparison.csv',index=False)
    # Row-aligned relative recommendation, with explicit abstentions and reference semantics.
    q[['source_row','csv_line','createdAt','pricing_multiplier','experimental_premium_USDC','reference_origin','status','reference_compatible_required','official_base_mapping_confirmed']].to_csv(out/'assignment_recommendations.csv',index=False)
    f[['source_row','createdAt']+v3.MARKET+['put']+nlp.COUNT_FEATURES+nlp.TEXT_FEATURES+social.ACTIVITY+social.SENTIMENT+['social_available']].to_csv(out/'quote_time_features.csv',index=False)
    monthly=q.assign(month=q.createdAt.dt.strftime('%Y-%m'),news4=q.news_count_4h.gt(0),news24=q.news_count_24h.gt(0),priced=q.experimental_premium_USDC.notna(),factors=q.pricing_multiplier.notna()).groupby('month').agg(orders=('source_row','size'),fresh_market=('market_valid','sum'),news_within_4h=('news4','sum'),news_within_24h=('news24','sum'),fresh_social=('social_available','sum'),full_component_eligible=('full_component_eligible','sum'),social_layer_applied=('social_layer_applied','sum'),relative_factors=('factors','sum'),conditional_absolute_quotes=('priced','sum'))
    monthly.to_csv(out/'monthly_coverage.csv')
    # Same frozen model, same quotes, old vs extended input samples. No ranking/tuning.
    oldf=assemble(d,JAY/'revision_v3_1/data/news_expanded_2026.jsonl',JAY/'revision_v3_1/data/btc_social_snapshots.csv',m,a.clock,health=health)
    oldq=predict_frame(oldf,m,b,origin)
    delta=q[['source_row','createdAt','full_component_eligible','social_layer_applied']].copy()
    delta['original_corpus_multiplier']=oldq.pricing_multiplier;delta['extended_corpus_multiplier']=q.pricing_multiplier
    delta['multiplier_difference']=q.pricing_multiplier-oldq.pricing_multiplier
    delta['conditional_premium_difference_USDC']=b*delta.multiplier_difference
    delta['comparison_kind']='same_model_input_extension_diagnostic_not_performance'
    delta.to_csv(out/'collection_extension_effect.csv',index=False)
    latency=[]
    for lag in [5,60,1440]:
        lf=assemble(d,a.news,a.social,m,a.clock,latency=lag,health=health);lq=predict_frame(lf,m,b,origin)
        mask=lq.full_component_eligible&b.notna()
        latency.append({'latency_minutes':lag,'fresh_social_orders':int(lf.social_available.sum()),'social_layer_applied':int(lq.social_layer_applied.sum()),'quotes_changed_vs_5min':int((lq.pricing_multiplier-q.pricing_multiplier).abs().gt(1e-10).sum()),'matched_reference_rows':int(mask.sum()),'matched_quoted_total_USDC':float((b[mask]*lq.loc[mask,'pricing_multiplier']).sum())})
    pd.DataFrame(latency).to_csv(out/'latency_sensitivity.csv',index=False)
    # Deterministic real example: first social-applied row with an absolute reference if possible.
    sample=q[q.social_layer_applied&q.reference_premium_USDC.notna()]
    if sample.empty:sample=q[q.social_layer_applied]
    for name,pop in [('demo_result',sample),('demo_joint_signals',q[q.social_layer_applied&q.news_count_4h.gt(0)])]:
        if len(pop):
            row=pop.sort_values(['createdAt','source_row']).iloc[0]
            save(out/(name+'.json'),{k:(None if pd.isna(v) else v) for k,v in row.items()})
        else:save(out/(name+'.json'),{'status':'no_eligible_example'})
    historical_rows=historical_evidence(a,bars,m,out) if not a.skip_historical else 0
    factors=[]
    for layer,r in [('market_news',m['news']['residual']),('social_sentiment',m['overlays']['news_social_sentiment'])]:
        for j,name in enumerate(r['features']):factors.append({'layer':layer,'feature':name,'coefficient':r['beta'][j],'training_center':r['center'][j],'training_scale':r['scale'][j],'interpretation':'Regularized log expected-payout effect per standardized unit, before clipping; association, not causality.'})
    pd.DataFrame(factors).to_csv(out/'learned_factors.csv',index=False)
    # Observed clocks are a separate diagnostic, never backdated from this download.
    observed=assemble(d,a.news,a.social,m,'observed',health=health)
    oq=predict_frame(observed,m,b,origin)
    observed_report={'fresh_social':int(observed.social_available.sum()),'full_component_eligible':int(oq.full_component_eligible.sum()),'duration_fallback_rows':int(oq.status.str.startswith('duration_component').sum()),'reason':'Current download is not historical receipt. Observed mode also requires a timely healthy collector record.'}
    save(out/'observed_clock_diagnostic.json',observed_report)
    # Critical integrity and temporal checks.
    changed=raw.copy();changed['closedAt']='2099-01-01';changed['realizedProfit_USDC']=1e15
    pd.testing.assert_frame_equal(normalize(raw),normalize(changed))
    assert q.source_row.tolist()==list(range(len(raw)))
    assert d.createdAt.notna().all() and cleaned.closedAt.isna().all() and cleaned.realizedProfit_USDC.isna().all()
    assert (d.loc[d.market_valid,'bar_close']<=d.loc[d.market_valid,'createdAt']).all()
    fresh=f.social_available.eq(1)
    assert (pd.to_datetime(f.loc[fresh,'social_available_at'],utc=True)<f.loc[fresh,'createdAt']).all()
    assert f.loc[fresh,'social_age_hours'].between(0,4).all()
    timed=f.latest_news_available_at.ne('')
    assert (pd.to_datetime(f.loc[timed,'latest_news_available_at'],utc=True)<f.loc[timed,'createdAt']).all()
    for name in VARIANTS:
        v=q[name+'_multiplier'].dropna();p=m['news']['v2']['pricing']
        assert v.between(p['minimum_multiplier']-1e-12,p['maximum_multiplier']+1e-12).all()
    no_social=q.full_component_eligible&~q.social_layer_applied
    assert np.allclose(q.loc[no_social,'market_news_multiplier'],q.loc[no_social,'combined_sentiment_multiplier'])
    fallback=q.pricing_multiplier.notna()&~q.full_component_eligible
    assert np.allclose(q.loc[fallback,'pricing_multiplier'],q.loc[fallback,'duration_multiplier'])
    test=f.loc[q.full_component_eligible].copy();test['premiumAmount_USDC']=3.14159
    if len(test):
        cs,ms=relative_components(m,test)
        assert np.allclose(cs['combined_sentiment'],v31.overlay_cost(m['news'],m['overlays']['news_social_sentiment'],test)/3.14159)
        assert np.allclose(ms['combined_sentiment'],v31.overlay_multiplier(m['news'],m['overlays']['news_social_sentiment'],test))
    assert digest(a.validation)==source_hash and digest(frozen_path)==frozen_hash
    info={'framework':'V3.2 combined duration + market + news NLP + X sentiment experiment','selected_experiment':'combined_sentiment','clock':a.clock,'model_cutoff_utc':m['cutoff_utc'],'models_refitted':False,'validation_rows':len(raw),'actual_payouts_available':int(raw.realizedProfit_USDC.notna().sum()),'recorded_premiums_available':int(raw.premiumAmount_USDC.notna().sum()),'conditional_reference_rows':int(b.notna().sum()),'relative_factor_rows':int(q.pricing_multiplier.notna().sum()),'full_component_eligible':int(q.full_component_eligible.sum()),'fresh_social_quotes':int(f.social_available.sum()),'social_layer_applied_quotes':int(q.social_layer_applied.sum()),'news_4h_quotes':int(f.news_count_4h.gt(0).sum()),'news_24h_quotes':int(f.news_count_24h.gt(0).sum()),'conditional_absolute_fresh_market':int((q.full_component_eligible&b.notna()).sum()),'conditional_absolute_including_fallback':int(q.experimental_premium_USDC.notna().sum()),'changed_by_collection_extension':int(delta.multiplier_difference.abs().gt(1e-10).sum()),'latest_market_candle':str(bars.bar_close.max()),'historical_july_rows':historical_rows,'validation_profit_or_accuracy_measurable':False,'original_validation_sha256':source_hash,'frozen_component_sha256':frozen_hash,'official_base_mapping_confirmed':False,'price_cap':m['news']['v2']['pricing'],'status_counts':q.status.value_counts().to_dict()}
    save(out/'summary.json',info)
    save(out/'checks.json',{'passed':True,'no_refitting':True,'rows_preserved':True,'future_outcomes_ignored':True,'past_only_features':True,'stale_social_neutral_increment':True,'missing_market_explicit_fallback':True,'price_limits_hold':True,'relative_algebra_matches_original':True,'inputs_and_models_unchanged':True})
    def portable(p):
        p=Path(p).resolve()
        return str(p.relative_to(HERE)) if p.is_relative_to(HERE) else str(p)
    save(out/'run_manifest.json',{'inputs':{role:{'path':portable(p),'sha256':digest(p)} for role,p in {'validation':a.validation,'market':a.market,'training':a.training,'news':a.news,'social':a.social,'model':frozen_path,'protocol':HERE/'PROTOCOL.md'}.items()},'clock':a.clock})
    print(json.dumps(info,indent=2));print(summary[summary.population.eq('matched_absolute_fresh_market')].to_string(index=False))
    return q,info

def arguments():
    p=argparse.ArgumentParser(description=__doc__)
    for name,default in [('validation','data/assignment_inputs/pp_transactions_validation.csv'),('market','data/assignment_inputs/btc_market_history.csv.gz'),('training','data/assignment_inputs/pp_transactions_training.csv.gz'),('news','data/news_combined_2026.jsonl'),('social','data/btc_social_snapshots.csv'),('outdir','results')]:p.add_argument('--'+name,default=str(HERE/default))
    p.add_argument('--clock',choices=['research_proxy','observed'],default='research_proxy');p.add_argument('--news-health')
    p.add_argument('--skip-historical',action='store_true',help='For new quote batches: skip the separate July outcome study.')
    return p.parse_args()

if __name__=='__main__':run(arguments())
