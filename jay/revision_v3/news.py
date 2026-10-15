"""Point-in-time news features. Publication reconstruction is explicitly opt-in."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

NLP_VERSION = 'tfidf-svd3-events-v1'
COUNT_FEATURES = ['news_log_count_4h', 'news_log_count_24h']
TEXT_FEATURES = ['news_text_0', 'news_text_1', 'news_text_2', 'news_uncertainty_4h', 'news_crypto_regulation_4h']
PATTERNS = {
 'uncertainty': r'\b(?:uncertain\w*|volatil\w*|shock\w*|stress|conflict|crisis|disrupt\w*|liquidation\w*|default\w*|hack\w*|exploit\w*|depeg\w*)\b',
 'crypto': r'\b(?:bitcoin|btc|crypto\w*|stablecoin\w*|tokeniz\w*|blockchain|digital assets?|ethereum|ether|defi)\b',
 'regulation': r'\b(?:regulat\w*|securities|commission|sec|cftc|laws?|legislat\w*|compliance)\b',
 'security': r'\b(?:hack\w*|exploit\w*|breach\w*|stolen|depeg\w*|attack\w*)\b',
 'macro': r'\b(?:inflation|employment|payroll\w*|federal reserve|fomc|interest rates?|consumer price|producer price|monetary|tariff\w*)\b'
}

def canonical_url(url):
    p=urlsplit(str(url)); query=[(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in {'ref','fbclid','gclid'}]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),urlencode(query),''))

def read_news(path):
    path=Path(path)
    if path.suffix=='.jsonl': rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]; d=pd.DataFrame(rows)
    else:d=pd.read_csv(path,keep_default_na=False)
    for c in ['news_id','source','source_url','title','text','clock_quality','timestamp_precision']:
        if c not in d:d[c]=''
        d[c]=d[c].fillna('').astype(str)
    for c in ['published_at','publication_bound_at','first_seen_at','nlp_ready_at']:
        if c not in d:d[c]=pd.NaT
        d[c]=pd.to_datetime(d[c],utc=True,errors='coerce',format='mixed')
    d['input_text']=(d.title+' '+d.text).str.split().str[:240].str.join(' ')
    d['canonical_url']=d.source_url.map(canonical_url)
    return d

def prepare_news(d,clock='observed',latency_minutes=5):
    if clock not in {'observed','publication_proxy'}:raise ValueError('Unknown news clock')
    if not np.isfinite(latency_minutes) or latency_minutes<0:raise ValueError('Latency must be nonnegative')
    d=d.copy()
    if clock=='observed':
        # No invented historical observations. Both receipt and NLP-ready stamps required.
        ok=d.first_seen_at.notna() & d.nlp_ready_at.notna() & d.clock_quality.isin(['observed_local','archived_observed'])
        d=d.loc[ok].copy()
        d['available_at']=d[['first_seen_at','nlp_ready_at','published_at']].max(axis=1)
    else:
        d['available_at']=d.publication_bound_at.fillna(d.published_at)+pd.Timedelta(minutes=latency_minutes)
        # Observed items are never moved backwards by selecting research mode.
        observed=d.clock_quality.isin(['observed_local','archived_observed'])
        d.loc[observed,'available_at']=d.loc[observed,['available_at','first_seen_at','nlp_ready_at']].max(axis=1)
    d=d[d.available_at.notna() & d.input_text.str.strip().ne('')].sort_values(['available_at','news_id'])
    # Causal duplicate suppression. Same FOMC headline on a later date is a new event.
    last_title={}; seen_urls=set(); keep=[]
    for i,r in d.iterrows():
        title=re.sub(r'\W+',' ',r.title.lower()).strip(); key=r.canonical_url or r.news_id
        duplicate=key in seen_urls or (title and title in last_title and (r.available_at-last_title[title]).total_seconds()<86400)
        if not duplicate:
            keep.append(i);seen_urls.add(key);last_title[title]=r.available_at
    d=d.loc[keep].reset_index(drop=True)
    for name,pattern in PATTERNS.items():d['tag_'+name]=d.input_text.str.count(pattern,flags=re.I).astype(float)
    d['uncertainty_rate']=d.tag_uncertainty/np.maximum(d.input_text.str.split().str.len(),1)*100
    d['crypto_regulation']=((d.tag_crypto>0)&(d.tag_regulation>0)).astype(float)
    return d

def fit_text(d,cutoff):
    train=d[d.available_at.lt(pd.Timestamp(cutoff))]
    base={'version':NLP_VERSION,'training_documents':len(train),'cutoff_utc':str(cutoff),'vocabulary':{},'idf':[],'components':[],'terms_by_component':[]}
    if len(train)<2:return base
    v=TfidfVectorizer(max_features=512,ngram_range=(1,2),stop_words='english',strip_accents='unicode',token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z]+\b')
    try:x=v.fit_transform(train.input_text)
    except ValueError:return base
    rank=min(3,x.shape[0]-1,x.shape[1]-1)
    if rank<1:return base
    svd=TruncatedSVD(n_components=rank,random_state=271828).fit(x)
    terms=v.get_feature_names_out()
    base.update(vocabulary={k:int(z) for k,z in v.vocabulary_.items()},idf=v.idf_.tolist(),components=svd.components_.tolist(),
                terms_by_component=[[str(terms[j]) for j in np.argsort(abs(c))[-8:][::-1]] for c in svd.components_],
                latest_training_document=str(train.available_at.max()))
    return base

def text_vectors(model,d):
    out=np.zeros((len(d),3))
    if not model['vocabulary'] or not len(d):return out
    v=TfidfVectorizer(vocabulary=model['vocabulary'],ngram_range=(1,2),stop_words='english',strip_accents='unicode',token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z]+\b')
    v.idf_=np.array(model['idf']); x=v.transform(d.input_text)
    components=np.asarray(model['components']);out[:,:len(components)]=x@components.T
    return out

def quote_features(quotes,news,text_model):
    """Only documents strictly earlier than each quote; no end-of-day aggregates."""
    d=news.sort_values('available_at').reset_index(drop=True); vec=text_vectors(text_model,d)
    stamps=d.available_at.astype('int64').to_numpy(); rows=[]
    for q in quotes.createdAt:
        row={k:0. for k in COUNT_FEATURES+TEXT_FEATURES}
        row.update(news_count_1h=0,news_count_4h=0,news_count_24h=0,latest_news_available_at='')
        if pd.isna(q):rows.append(row);continue
        end=np.searchsorted(stamps,q.value,side='left')
        for hours in [1,4,24]:
            start=np.searchsorted(stamps,(q-pd.Timedelta(hours=hours)).value,side='left');row[f'news_count_{hours}h']=int(end-start)
            if hours in [4,24]:row[f'news_log_count_{hours}h']=float(np.log1p(end-start))
        start=np.searchsorted(stamps,(q-pd.Timedelta(hours=4)).value,side='left')
        if end>start:
            age=(q.value-stamps[start:end])/3.6e12;weight=np.exp(-age/2.)
            # Sum / (1+mass) retains both content and intensity without unbounded counts.
            emb=(vec[start:end]*weight[:,None]).sum(axis=0)/(1+weight.sum())
            row.update({f'news_text_{j}':float(emb[j]) for j in range(3)})
            row['news_uncertainty_4h']=float(np.sum(d.uncertainty_rate.iloc[start:end]*weight)/(1+weight.sum()))
            row['news_crypto_regulation_4h']=float(np.sum(d.crypto_regulation.iloc[start:end]*weight)/(1+weight.sum()))
        if end:row['latest_news_available_at']=d.available_at.iloc[end-1].isoformat()
        rows.append(row)
    return pd.DataFrame(rows,index=quotes.index)
