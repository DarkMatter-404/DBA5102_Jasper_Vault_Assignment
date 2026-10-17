#!/usr/bin/env python3
"""Check chronology, quote independence, price bounds and reference reproduction."""
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile

import numpy as np
import pandas as pd
import pricing

ROOT=Path(__file__).resolve().parent
REPO=next((p for p in ROOT.parents if (p/'data'/'with_base_premium').is_dir()),ROOT.parents[1])  # code_final path fix
OUT=ROOT.parent/'output/v2'  # code_final: Jay's folder


def main():
    orders=REPO/'data/en/pp_transactions_training.csv'
    candles=REPO/'data/en/btc_market_history.csv'
    expected_manifest=json.loads((ROOT/'reference_results/input_manifest.json').read_text())
    for p in [orders,candles]:
        assert hashlib.sha256(p.read_bytes()).hexdigest()==expected_manifest[p.name]['sha256'], f'Input mismatch: {p.name}'
    checks={'original_EN_input_hashes':True}
    market=pricing.v1.read_market(candles)
    data=pricing.v1.features(orders,market)
    model=pricing.fit(data,'2026-07-01')
    assert model['training_rows']==4975
    preblind=pricing.fit(data,'2026-07-31T17:11:48Z')
    assert preblind['training_rows']==7585
    assert pd.Timestamp(model['latest_training_settlement'])<pd.Timestamp(model['cutoff_utc'])
    assert model==pricing.fit(data,'2026-07-01T08:00:00+08:00')
    altered=data.copy()
    unavailable=(altered.createdAt>=pd.Timestamp('2026-07-01',tz='UTC')) | (altered.closedAt>=pd.Timestamp('2026-07-01',tz='UTC'))
    altered.loc[unavailable,'realizedProfit_USDC']=1e9
    assert pricing.fit(altered,'2026-07-01')==model
    checks['settled_label_cutoff_and_timezone_equivalence']=True
    before=pricing.quotes(model,data)
    columns=['expected_payout_USDC','recommended_multiplier','recommended_premium_USDC','assumed_retention_at_emax']
    with tempfile.TemporaryDirectory(prefix='jasper_v2_verify_') as work:
        work=Path(work)
        raw=pd.read_csv(orders)
        raw.drop(columns=['realizedProfit_USDC','closedAt']).to_csv(work/'blind.csv',index=False)
        blind=pricing.v1.features(work/'blind.csv',market)
        after=pricing.quotes(model,blind)
        pd.testing.assert_frame_equal(before,after)
        assert before.source_row.tolist()==list(range(len(raw)))
        checks['all_7831_quotes_invariant_to_missing_outcomes_and_row_order_preserved']=True
        adversarial=pd.concat([raw.iloc[[0]]]*8,ignore_index=True)
        adversarial.loc[0,'premiumAmount_USDC']=0
        adversarial.loc[1,'premiumAmount_USDC']=np.inf
        adversarial.loc[2,'quantity_BTC']=-1
        adversarial.loc[2,'strikePrice']=-1
        adversarial.loc[3,'optionType']=2
        adversarial.loc[4,'expirationDate']=adversarial.loc[4,'createdAt']
        adversarial.loc[5,'productType']=12345
        adversarial.loc[6,'createdAt']='2026-08-25 00:00:00'
        adversarial.loc[6,'expirationDate']='2026-08-25 00:29:53'
        adversarial.loc[7,'expirationDate']='2026-02-02 02:20:00'
        adversarial.to_csv(work/'adversarial.csv',index=False)
        bad=pricing.quotes(model,pricing.v1.features(work/'adversarial.csv',market))
        assert bad.loc[:5,columns].isna().all().all()
        assert bad.loc[6:7,'status'].eq('reference_fallback_requote_before_live_use').all()
        assert bad.loc[6:7,'recommended_multiplier'].eq(1).all()
        checks['invalid_contracts_block_and_unsupported_quotes_explicitly_fallback']=True
        # The new model does not use volatility in its price, but it retains the
        # common audit's past-only market coverage check for comparable samples.
        row=data[data.quote_valid & data.month.eq('2026-07')].iloc[0]
        bars=pd.read_csv(candles)
        bars[pd.to_datetime(bars.close_time_utc,utc=True)<=row.createdAt].to_csv(work/'past.csv',index=False)
        raw.iloc[[int(row.source_row)]].to_csv(work/'one.csv',index=False)
        one=pricing.v1.features(work/'one.csv',pricing.v1.read_market(work/'past.csv'))
        actual=pricing.quotes(model,one)
        expected=before[before.source_row.eq(row.source_row)]
        np.testing.assert_allclose(actual[columns],expected[columns],rtol=1e-12)
        checks['future_market_removal_does_not_change_quote']=True
    tr=pricing.v1.train_before(data,'2026-07-01')
    b=tr.premiumAmount_USDC.to_numpy()
    assert np.isclose(np.sum(b*pricing.multiplier(model,tr)),b.sum(),rtol=1e-12)
    checks['training_premium_neutrality']=True
    historical=before.is_before_model_cutoff & data.quote_valid
    assert before.loc[historical,'status'].eq('historical_diagnostic_model_used_later_labels').all()
    assert not before.loc[data.month.eq('2026-07'),'is_before_model_cutoff'].any()
    checks['earlier_than_model_cutoff_quotes_labeled_historical']=True
    extreme=copy.deepcopy(model)
    extreme['tenor_ratios']['1800']=1e-10
    extreme['tenor_ratios']['3600']=1e10
    sample=pd.DataFrame({'productType':[1800,3600],'premiumAmount_USDC':[1.,1.]})
    m=pricing.multiplier(extreme,sample)
    np.testing.assert_allclose(m,[.98709410502004,1.01290589497996],atol=1e-12)
    for elasticity in np.linspace(0,4,41):
        assert np.minimum(1,m**-elasticity).min()>=.95-1e-12
    assert pricing.analytic_weight(1,4,1.15)==0
    for rho,emax,upper in [(0,4,1.15),(1.1,4,1.15),(.95,0,1.15),(.95,4,1),(.95,np.nan,1.15)]:
        try: pricing.analytic_weight(rho,emax,upper)
        except ValueError: pass
        else: raise AssertionError('Invalid retention assumptions accepted')
    bad_model=copy.deepcopy(model);bad_model['pricing']['weight']=.5
    try: pricing.quotes(bad_model,data)
    except ValueError: pass
    else: raise AssertionError('Inconsistent stored retention cap accepted')
    checks['extreme_risk_still_respects_analytic_assumed_retention_bound']=True
    pd.testing.assert_frame_equal(before,pricing.quotes(json.loads(json.dumps(model)),data))
    assert np.isclose(pricing.lower_tail_mean([-10,0,10,20,30,40]),-10/1.2)
    checks['model_serialization_and_fractional_twenty_percent_tail']=True
    for filename in ['cost_metrics.csv','commercial_scenarios.csv','frozen_tenor_rates.csv']:
        pd.testing.assert_frame_equal(pd.read_csv(OUT/filename),pd.read_csv(ROOT/'reference_results'/filename),check_exact=False,rtol=1e-8,atol=1e-8)
    saved=json.loads((OUT/'frozen_july_model.json').read_text())
    assert saved==model
    checks['frozen_model_and_headline_results_reproduced']=True
    report={'checks':checks,'python':platform.python_version(),
            'package_versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy']},
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'pricing.py',Path(__file__),pricing.JAY/'pp_pricing.py']},
            'scope':'Implementation and retrospective reproduction checks, not proof of demand or out-of-sample superiority.'}
    pricing.write_json(OUT/'verification_report.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
