"""Conditional historical paths -> early-close claims -> distribution statistics."""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from .events import ARMS

def distribution_stats(values, weights, outcome=None):
    x=np.asarray(values).ravel(); w=np.asarray(weights).ravel()
    ix=np.argsort(x,kind='stable'); x=x[ix]; w=w[ix]; w=w/w.sum()
    c=np.cumsum(w); mean=float(w@x)
    upper=np.minimum(w,np.maximum(c-.95,0))
    out={'mean_claim':mean,'es95':float(upper@x/.05),
         'payout_probability':float(w[x>1e-10].sum()),
         'q05':float(x[min(len(x)-1,np.searchsorted(c,.05))]),
         'q95':float(x[min(len(x)-1,np.searchsorted(c,.95))]),
         'mass_error':abs(float(w.sum())-1)}
    if outcome is not None and np.isfinite(outcome):
        out['crps']=float(w@np.abs(x-outcome)-np.sum(w*x*(2*c-w-1)))
    return out

class Simulator:
    def __init__(self, market, events, hazard, cutoff):
        self.market,self.events,self.hazard,self.cutoff=market,events,hazard,pd.Timestamp(cutoff)
        self.a=market.archive(cutoff)
        self.scaler=StandardScaler().fit(self.a['features'])
        self.z=self.scaler.transform(self.a['features'])
        self.nn=NearestNeighbors(n_neighbors=min(128,len(self.z))).fit(self.z)
        self.labels={a:events.archive_labels(self.a['time'],a) for a in ARMS[1:]}
        self.meta={'archive_paths':len(self.z),'fit_cutoff':str(cutoff),
            'last_archive_outcome':str(pd.Timestamp(self.a['last_path_observation'],tz='UTC')),
            'hazard':hazard.meta}

    def _weights(self, ix, distances):
        age=(self.cutoff.value-self.a['time'][ix])/8.64e13
        # Kernel bandwidth from selected state distances, not test outcomes.
        bw=max(float(np.median(distances)),.25)
        w=np.exp(-.5*(distances/bw)**2)*2**(-age/90)
        return w/w.sum()

    def predict(self, row, outcome=None, verified_spot=None):
        ctx=self.market.context(row.createdAt)
        fresh=ctx['fresh']
        if fresh:
            z=self.scaler.transform(ctx['features'][None,:])[0]
            dist,ix=self.nn.kneighbors(z[None,:]); ix,dist=ix[0],dist[0]
            vol=ctx['vol']; base_w=self._weights(ix,dist)
        else:
            # Deterministic stratified subsample of the unconditional past archive.
            ix=np.linspace(0,len(self.z)-1,min(128,len(self.z)),dtype=int)
            dist=np.zeros(len(ix)); base_w=self._weights(ix,dist)
            vol=float(np.median(self.a['vol'])); z=None
        nsteps=int(row.productType//300)
        cache={}
        def claim_paths(indices):
            key=tuple(indices.tolist())
            if key in cache:return cache[key]
            ratio=vol/self.a['vol'][indices]
            scaled=self.a['paths'][indices,:nsteps]*np.clip(ratio,.25,4)[:,None]
            spot=float(verified_spot) if verified_spot is not None else float(row.strikePrice)
            price=spot*np.exp(scaled)
            side=1 if int(row.optionType)==0 else -1
            claims=np.maximum(side*(price-row.strikePrice),0)*row.quantity_BTC
            mass=self.hazard.settlement_mass(scaled,row,vol)
            cache[key]=(claims,mass,float(((ratio<.25)|(ratio>4)).mean()))
            return cache[key]
        x0,h0,clip0=claim_paths(ix)
        common={'row_id':int(row.row_id),'createdAt':str(row.createdAt),'market_asof':ctx['market_asof'],
            'fresh_market':fresh,'quote_status':'research_quote' if fresh else 'missing_market_diagnostic_only',
            'vol_per_sqrt_minute':vol,'fit_cutoff':str(self.cutoff),'moneyness_assumption':'ATM' if verified_spot is None else 'verified_spot',
            'archive_last_observation':self.meta['last_archive_outcome'],
            'market_vol_scale_clip_fraction':clip0}
        output=[]
        for arm in ARMS:
            ev=self.events.context(row.createdAt,arm)
            alpha=0.; episodes=0; indices=None
            if ev is not None and fresh:
                cats,ids=self.labels[arm]
                candidates=np.where(cats==ev['category'])[0]
                episodes=len(set(ids[candidates])) if len(candidates) else 0
                if episodes:
                    d=np.sqrt(np.sum((self.z[candidates]-z)**2,axis=1))
                    order=np.argsort(d,kind='stable')[:128]
                    indices=candidates[order]
                    w1=self._weights(indices,d[order])
                    alpha=.35*ev['strength']
                    if arm=='verified_research':alpha*=episodes/(episodes+10)
            if alpha>0:
                x1,h1,_=claim_paths(indices)
                x=np.concatenate([x0.ravel(),x1.ravel()])
                w=np.concatenate([((1-alpha)*base_w[:,None]*h0).ravel(),(alpha*w1[:,None]*h1).ravel()])
            else:x=x0; w=base_w[:,None]*h0
            stats=distribution_stats(x,w,outcome)
            output.append({**common,'arm':arm,**stats,'event_id':ev['event_id'] if ev else '',
                'event_category':ev['category'] if ev else 'none','event_weight':alpha,
                'distinct_past_event_episodes':episodes})
        return output
