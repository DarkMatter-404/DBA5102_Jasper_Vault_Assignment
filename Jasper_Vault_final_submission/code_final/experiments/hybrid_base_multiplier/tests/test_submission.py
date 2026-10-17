import json

import numpy as np
import pandas as pd
import pytest

from pricing.data import ROOT, VALID_FILE

SUB = ROOT / "outputs" / "validation_premiums.csv"


@pytest.mark.skipif(not (SUB.exists() and VALID_FILE.exists()),
                    reason="needs the validation files and the output of notebooks/05_validation_submission.ipynb")
def test_submission_file():
    raw, sub = pd.read_csv(VALID_FILE), pd.read_csv(SUB)
    assert len(sub) == len(raw) == 4155
    assert (sub["createdAt"] == raw["createdAt"]).all()
    p = sub["premiumAmount_USDC"]
    assert p.notna().all() and (p > 0).all()
    assert np.allclose(p, sub["premium_per_BTC_USDC"] * sub["quantity_BTC"])
    cfg = json.loads((ROOT / "outputs" / "selected_config.json").read_text())["config"]
    ratio = sub["premium_per_BTC_USDC"] / sub["reference_price_per_BTC_USDC"]
    at_floor = sub["premium_per_BTC_USDC"] <= sub["expected_payout_per_BTC_USDC"] + 1e-9
    assert (ratio >= cfg["cap_lo"] - 1e-9).all()
    assert ((ratio <= cfg["cap_hi"] + 1e-9) | at_floor).all()
    # Both outputs for every order: premium and multiplier (premium per BTC / anchor).
    m = sub["pricingMultiplier"]
    assert m.notna().all() and (m > 0).all()
    assert np.allclose(m * sub["anchor_per_BTC_USDC"], sub["premium_per_BTC_USDC"])
    has_base = raw["apiBasePrice_per_BTC_USDC"].notna()
    assert np.allclose(sub.loc[has_base, "anchor_per_BTC_USDC"], raw.loc[has_base, "apiBasePrice_per_BTC_USDC"])
    assert (sub.loc[has_base, "anchor_source"] == "jasper").all()
    assert (sub.loc[~has_base, "anchor_source"] == "rebuilt").all()
