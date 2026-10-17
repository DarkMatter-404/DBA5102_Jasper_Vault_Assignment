#!/usr/bin/env python3
"""Reproduce every v2 research family; no network calls and no fresh tuning."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=next((p for p in HERE.parents if (p/'data'/'with_base_premium').is_dir()),HERE.parents[2])  # code_final path fix
sys.path.insert(0,str(HERE.parents[1]))  # code_final: Jay's folder
import pp_pricing
OUT=HERE.parents[1]/'output/v2/research'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    original=REPO/'data/en/pp_transactions_training.csv'
    enriched=REPO/'data/with_base_premium/pp_transactions_training.csv'
    market_path=REPO/'data/en/btc_market_history.csv'
    for p in [original,enriched,market_path]:
        if not p.is_file(): raise FileNotFoundError(f'Required shared repository input: {p}')
    market=pp_pricing.read_market(market_path)
    orig=pp_pricing.features(original,market)
    orig.to_pickle(OUT/'original_features.pkl')
    base=pp_pricing.features(enriched,market)
    base['api_base_USDC']=base.quantity_BTC*pd.to_numeric(base.apiBasePrice_per_BTC_USDC,errors='coerce')
    base['api_base_bps']=1e4*base.api_base_USDC/base.notional_USDC
    base['base_valid']=base.api_base_USDC.gt(0)&np.isfinite(base.api_base_USDC)
    base['paid_to_base']=base.premiumAmount_USDC/base.api_base_USDC
    base.to_pickle(OUT/'enriched_features.pkl')
    matched=base[base.analysis_valid&base.base_valid]
    audit=matched.groupby('month').agg(n=('source_row','size'),paid=('premiumAmount_USDC','sum'),base=('api_base_USDC','sum'),payout=('realizedProfit_USDC','sum'))
    audit['paid_margin']=audit.paid-audit.payout
    audit['base_margin']=audit.base-audit.payout
    audit.to_csv(OUT/'base_audit_monthly.csv')
    summary={'original_orders':len(orig),'original_valid_labels':int(orig.analysis_valid.sum()),
             'enriched_orders':len(base),'enriched_valid_labels':int(base.analysis_valid.sum()),
             'enriched_unmatched_base_raw':int((~base.base_valid).sum()),
             'matched_valid_labels':len(matched),
             'enriched_valid_but_unmatched':int((base.analysis_valid&~base.base_valid).sum()),
             'base_warning':'Matched 0DTE per-BTC quote times quantity; PP conversion and past-only match timestamps are unverified. Negative-residual filtering changes the population.',
             'sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [original,enriched,market_path]}}
    (OUT/'population_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
    stages=['cost_family/study.py','cost_family/diagnostics.py','cost_family/commercial.py',
            'cost_family/budget_neutral_study.py','cost_family/blend_tradeoff.py',
            'base_study.py','tree_study.py','decision_study.py']
    env=os.environ.copy()
    # Keep this small research run reproducible without excessive thread fan-out.
    env['OMP_NUM_THREADS']='1'
    env['OPENBLAS_NUM_THREADS']='1'
    for stage in stages:
        print(f'Running {stage}',flush=True)
        logfile=OUT/(Path(stage).stem+'.log')
        with logfile.open('w') as log:
            subprocess.run([sys.executable,str(HERE/stage)],cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(f'All eight stages completed. Tables and logs: {OUT}')


if __name__=='__main__':main()
