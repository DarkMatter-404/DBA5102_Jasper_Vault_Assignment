"""Discrete early-close probability; no actual future hold time at inference."""
import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

FEATURE_NAMES=['elapsed_fraction','elapsed_fraction_squared','log_hours','put_indicator','standardized_signed_gain','log_notional']

def features(paths, row, vol):
    k=paths.shape[1]
    elapsed=np.arange(1,k+1)*300/float(row.productType)
    side=1 if int(row.optionType)==0 else -1
    gain=np.clip(side*paths/(max(vol,1e-7)*np.sqrt(np.arange(1,k+1)*5)), -10,10)
    return np.stack([np.broadcast_to(elapsed,paths.shape),np.broadcast_to(elapsed**2,paths.shape),
        np.full(paths.shape,np.log(row.productType/3600)),np.full(paths.shape,row.optionType),gain,
        np.full(paths.shape,np.log(max(row.quantity_BTC*row.strikePrice,1e-6)))],axis=-1)

class Hazard:
    def fit(self, orders, market, cutoff):
        use=orders[orders.scorable & (orders.createdAt < cutoff) & (orders.closedAt < cutoff)]
        xx=[]; yy=[]; early=0; usable=0
        for r in use.itertuples():
            ctx=market.context(r.createdAt)
            if not ctx['fresh']: continue
            n=int(r.productType//300)
            # Settlement grace <5min is not an early exercise.
            hold=(r.closedAt-r.createdAt).total_seconds()
            isearly=hold < r.productType-300
            exitstep=max(1,min(n-1,int(np.ceil(hold/300)))) if isearly else n
            if n<2: continue
            nr=exitstep if isearly else n-1
            path=market.path_at(r.createdAt,nr)
            if path is None: continue
            # Decisions condition on the PREVIOUS interval endpoint, never
            # on a price observed after the customer's actual close.
            assert r.createdAt + pd.Timedelta(seconds=300*(nr-1)) < cutoff
            x=features(path[None,:-1],r,ctx['vol'])[0]
            y=np.zeros(nr,dtype=int)
            if isearly: y[-1]=1; early+=1
            xx.append(x); yy.append(y); usable+=1
        self.meta={'training_orders':len(use),'usable_hazard_orders':usable,'early_exits':early,
            'fit_cutoff':str(cutoff),'last_label_close':str(use.closedAt.max()),
            'features':FEATURE_NAMES}
        y=np.concatenate(yy) if yy else np.zeros(1)
        self.pooled=float((y.sum()+1)/(len(y)+100))
        self.model=None
        if early >= 20 and len(np.unique(y))==2:
            x=np.concatenate(xx)
            self.scaler=StandardScaler().fit(x)
            self.model=LogisticRegression(C=.1,max_iter=300,solver='lbfgs').fit(self.scaler.transform(x),y)
            self.coef=self.model.coef_[0]/self.scaler.scale_
            self.intercept=float(self.model.intercept_[0]-self.coef@self.scaler.mean_)
            self.meta.update({'method':'regularized_logistic_hazard','standardized_coefficients':dict(zip(FEATURE_NAMES,self.model.coef_[0].tolist()))})
        else:self.meta['method']='pooled_hazard'
        return self

    def settlement_mass(self, paths, row, vol):
        if self.model is None: h=np.full(paths.shape,self.pooled)
        else:
            before=np.column_stack([np.zeros(len(paths)),paths[:,:-1]])
            h=expit(features(before,row,vol)@self.coef+self.intercept)
        h=np.clip(h,1e-8,1-1e-8)
        h[:,-1]=1
        survive=np.cumprod(np.column_stack([np.ones(len(paths)),1-h[:,:-1]]),axis=1)
        mass=survive*h
        assert np.allclose(mass.sum(axis=1),1,atol=1e-10)
        return mass
