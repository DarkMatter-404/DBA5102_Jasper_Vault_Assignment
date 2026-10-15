#!/usr/bin/env python3
"""Meaningful leakage/round-trip checks and a fixed-spec timestamp sensitivity.
Run after pp_pricing.py analyze. Does not select or tune another model.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile
import numpy as np
import pandas as pd
import pp_pricing as pp

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--orders',type=Path,default=ROOT.parent/'data/en/pp_transactions_training.csv')
    parser.add_argument('--market',type=Path,default=ROOT.parent/'data/en/btc_market_history.csv')
    parser.add_argument('--outdir',type=Path,default=ROOT/'output/data')
    parser.add_argument('--reference-dir',type=Path,default=ROOT/'reference_results')
    args=parser.parse_args()
    ORDERS,MARKET,OUT=args.orders,args.market,args.outdir
    manifest=json.loads((args.reference_dir/'input_manifest.json').read_text())
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ORDERS,MARKET]}
    for name,value in hashes.items():
        assert value==manifest['input_sha256'][name],f'Input mismatch: {name}; verification requires the original EN release.'
    checks={'input_files_match_original_en_release':True}
    market=pp.read_market(MARKET)
    data=pp.features(ORDERS,market)
    frozen=json.loads((OUT/'frozen_july_model.json').read_text())
    deployment=json.loads((OUT/'deployment_model.json').read_text())
    reference=pp.quote_predictions(data,frozen)
    with tempfile.TemporaryDirectory(prefix='jasper_verify_') as work:
        work=Path(work)
        blank=pd.read_csv(ORDERS)
        blank['closedAt']=np.nan;blank['realizedProfit_USDC']=np.nan
        blank.to_csv(work/'blind.csv',index=False)
        blind=pp.features(work/'blind.csv',market)
        blind_quotes=pp.quote_predictions(blind,frozen)
        cols=['expected_payout_USDC','pricing_multiplier','challenger_multiplier','challenger_premium_USDC','recommended_premium_USDC']
        np.testing.assert_allclose(reference[cols],blind_quotes[cols],rtol=1e-12,equal_nan=True)
        assert reference.status.equals(blind_quotes.status)
        checks['blank_outcomes_and_close_leave_all_7831_quotes_unchanged']=True
        adversarial=pd.concat([pd.read_csv(ORDERS).iloc[[0]]]*9,ignore_index=True)
        adversarial.loc[0,'premiumAmount_USDC']=np.nan
        adversarial.loc[1,'premiumAmount_USDC']=-1.
        adversarial.loc[2,'premiumAmount_USDC']=0.
        adversarial.loc[3,'premiumAmount_USDC']=np.inf
        adversarial.loc[4,'quantity_BTC']=-1.
        adversarial.loc[4,'strikePrice']=-1.  # Positive product must not mask two invalid inputs.
        adversarial.loc[5,'optionType']=2
        adversarial.loc[6,'expirationDate']=adversarial.loc[6,'createdAt']
        adversarial.loc[7,'createdAt']='2026-08-25 00:00:00'
        adversarial.loc[7,'expirationDate']='2026-08-25 00:29:53'
        adversarial.loc[8,'expirationDate']='2026-02-02 02:20:00'  # Invalid nominal quote timing.
        adversarial.to_csv(work/'adversarial.csv',index=False)
        adv_data=pp.features(work/'adversarial.csv',market)
        adv=pp.quote_predictions(adv_data,frozen)
        assert adv.loc[:3,'status'].eq('no_quote_invalid_reference').all()
        assert adv.loc[4:6,'status'].eq('no_quote_invalid_contract').all()
        assert adv.loc[:6,cols].isna().all().all()
        assert adv.loc[7,'status']=='fallback_recorded_price_market_data_invalid'
        assert adv.loc[8,'status']=='fallback_recorded_price_ambiguous_quote_time'
        assert (adv.loc[7:8,'recommended_premium_USDC']==adversarial.loc[7:8,'premiumAmount_USDC']).all()
        checks['invalid_reference_and_contracts_emit_no_quote_and_market_fallback_is_distinct']=True
        raw=pd.read_csv(MARKET)
        raw_time=pd.to_datetime(raw.close_time_utc,utc=True)
        examples=data[data.quote_valid].iloc[[100,3000,7000]]
        for i,row in examples.iterrows():
            raw.loc[raw_time.le(row.feature_time)].to_csv(work/'truncated_market.csv',index=False)
            one=pd.read_csv(ORDERS).iloc[[int(row.source_row)]]
            one.to_csv(work/'one_order.csv',index=False)
            recalc=pp.features(work/'one_order.csv',pp.read_market(work/'truncated_market.csv'))
            names=pp.FEATURES['state']+['anchor_bps','recorded_bps','market_age_seconds']
            np.testing.assert_allclose(recalc[names].to_numpy(float),row[names].to_numpy(float)[None,:],rtol=1e-12,atol=1e-12)
        checks['future_market_truncation_leaves_features_unchanged_for_three_dates']=True
    default_quotes=pp.quote_predictions(data,deployment)
    quoted=data.reference_valid & data.contract_valid
    assert np.all(default_quotes.loc[quoted,'pricing_multiplier'].eq(1))
    np.testing.assert_allclose(default_quotes.loc[quoted,'recommended_premium_USDC'],data.loc[quoted,'premiumAmount_USDC'])
    assert default_quotes.loc[~quoted,'recommended_premium_USDC'].isna().all()
    checks['deployment_gate_disabled_returns_reference_only_for_valid_contracts']=True
    default_quotes.to_csv(OUT/'submission_template_training_rows.csv',index=False)
    # Confirm exact held-out row-level score reproduction from the serialized frozen model.
    test=data[data.analysis_valid & data.createdAt.ge(pd.Timestamp('2026-07-01',tz='UTC'))].copy()
    pred=pp.predict_rate(frozen,test)*test.notional_USDC.to_numpy()/1e4
    existing=pd.read_csv(OUT/'july_holdout_predictions.csv')
    np.testing.assert_allclose(pred,existing[frozen['selected_name']],rtol=1e-10)
    checks['frozen_model_roundtrip_reproduces_saved_holdout_cost_predictions']=True
    expected=pd.read_csv(args.reference_dir/'july_holdout_metrics.csv')
    actual=pd.read_csv(OUT/'july_holdout_metrics.csv')
    pd.testing.assert_frame_equal(actual,expected,check_exact=False,rtol=1e-7,atol=1e-8)
    expected_summary=json.loads((args.reference_dir/'analysis_summary.json').read_text())
    actual_summary=json.loads((OUT/'analysis_summary.json').read_text())
    for key in ['selected_model','refit_rows_for_July','split']:
        assert actual_summary[key]==expected_summary[key],f'Reproduction mismatch: {key}'
    checks['original_model_selection_splits_and_july_metrics_reproduced']=True
    # Sensitivity keeps the June-selected spec/hyperparameters; no re-selection.
    strict=pp.features(ORDERS,market,feature_clock='nominal_start')
    strict_train=pp.train_before(strict,'2026-07-01')
    strict_test=strict[strict.analysis_valid & strict.createdAt.ge(pd.Timestamp('2026-07-01',tz='UTC'))].copy()
    sensitivity=[]
    for label,anchor,feature_set,alpha in [
        ('June_selected_spec_nominal_start',frozen['anchor'],frozen['feature_set'],frozen['alpha']),
        ('Calibrated_paid_price_nominal_start','recorded_bps','scalar',0.)]:
        model=pp.fit(strict_train,anchor,feature_set,alpha)
        pred=pp.predict_rate(model,strict_test)*strict_test.notional_USDC.to_numpy()/1e4
        sensitivity.append({'model':label,'quote_clock':'min(createdAt, expirationDate-productType)',**pp.metrics(strict_test,pred)})
    pd.DataFrame(sensitivity).to_csv(OUT/'nominal_start_timing_sensitivity.csv',index=False)
    # Diagnostic explanation of regime fragility, not a replacement selection rule.
    rows=[]
    for field in ['optionType','productType']:
        for period in ['2026-06','2026-07']:
            d=data[data.analysis_valid & data.month.eq(period)]
            for group,g in d.groupby(field):
                rows.append({'period':period,'dimension':field,'value':group,'orders':len(g),
                    'recorded_premium_USDC':g.premiumAmount_USDC.sum(),'payout_USDC':g.realizedProfit_USDC.sum(),
                    'claims_to_premium':g.realizedProfit_USDC.sum()/g.premiumAmount_USDC.sum()})
    pd.DataFrame(rows).to_csv(OUT/'side_and_tenor_diagnostics.csv',index=False)
    versions={name:importlib.metadata.version(name) for name in ['pandas','numpy','scipy','matplotlib']}
    report={'checks':checks,'timestamp_sensitivity':'Fixed June-selected specification, retrained on pre-July settled labels using a conservative inferred opening-time clock; not tuned on July.',
        'python':platform.python_version(),'package_versions':versions,
        'input_sha256':hashes,
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'pp_pricing.py',ROOT/'build_figures.py']}}
    pp.dump_json(OUT/'verification_report.json',report)
    print(json.dumps(report,indent=2))
    print(pd.DataFrame(sensitivity).to_string(index=False))

if __name__=='__main__':main()
