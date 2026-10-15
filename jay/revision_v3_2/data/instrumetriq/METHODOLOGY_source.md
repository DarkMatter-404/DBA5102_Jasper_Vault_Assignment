# Methodology

High-level overview of Instrumetriq's data collection and processing approach.

---

## Data Sources

### Market Data

**Source**: Binance REST and WebSocket APIs

- **Spot market**: Order book snapshots, recent trades, 24-hour ticker
- **Futures market** (Tier 3): USDT-margined perpetual contracts, funding rates, open interest, trader positioning

Market data is sampled at regular intervals during each observation session.

### Social Data

**Source**: X (Twitter) public posts

Posts are captured for cryptocurrency-related terms and cashtags. Sentiment scraping operates on its own cycle (~60 minutes per complete pass through all tracked symbols). While independent of watchlist timing, the most recent sentiment cycle is assigned to a coin at admission time.

---

## Sentiment Analysis

### Pipeline (V2 — current, since February 2026)

Posts pass through the following stages before aggregation:

1. **Collection** — Public posts are retrieved from X (Twitter) via asset-specific queries.
2. **Deduplication** — Previously observed posts are identified and removed. Each post is scored at most once.
3. **Crypto relevance filtering** — A dedicated BERTweet-based classification model evaluates whether each post pertains to cryptocurrency. Off-topic posts are excluded before sentiment scoring. Filtered posts are retained separately for auditing.
4. **Primary sentiment scoring** — Each relevant post is scored by a domain-specific BERTweet-based sentiment model trained on crypto-related language. Classification scheme: 3-class (positive, neutral, negative).
5. **Secondary confidence scoring** — A second model, based on the DistilBERT architecture, independently evaluates each post. Its confidence determines whether the primary classification is accepted, overridden, or forced to neutral.
6. **Cycle-level aggregation** — Individual post scores are aggregated into cycle-level metrics (pos/neu/neg ratios, mean score, decision source statistics).
7. **Silence handling** — Periods of low or absent posting activity are tracked explicitly via `recent_posts_count`, `is_silent`, and `hours_since_latest_tweet`.

### Referee Adjudication

The secondary model's confidence drives the final decision for each post:

- **primary_default** — Primary model classification accepted (secondary model confidence supports the primary label)
- **referee_override** — Secondary model overrides the primary classification (sufficient confidence in a different label)
- **referee_neutral_band** — Forced neutral (secondary model confidence falls within an uncertainty band where neither label is reliable)

These decision sources are tracked per cycle in `hybrid_decision_stats.decision_sources`.

### Version Identification

Each record includes a `methodology_regime` field (`"v1"` or `"v2"`) and a `sentiment_model_version` field (`"v1.0"` or `"v2.0"`) enabling programmatic separation of data produced under different pipeline configurations.

**Cutover timestamps:**
- **Phase 1** (2026-02-16T05:14:00Z) — Updated sentiment models deployed. Records carry `methodology_regime: "v2"`.
- **Phase 2** (2026-02-17T06:03:00Z) — Crypto relevance filter activated. Records additionally include `crypto_filter_enabled: true`.

Data produced before February 16, 2026 carries `methodology_regime: "v1"`.

### V1 Methodology (prior to February 2026)

The original pipeline used a two-model DistilBERT ensemble without relevance filtering:
- Posts were collected, deduplicated, and scored directly (no relevance filter step)
- Both primary and referee models were DistilBERT-based
- The same referee adjudication logic applied (primary_default, referee_override, referee_neutral_band)

---

## Observation Windows

### Session Duration

Each watchlist session runs for **~120–130 minutes**:
- Symbols are admitted based on activity scoring
- Market data is sampled every ~10 seconds throughout the session
- Sessions typically accumulate **700+ price samples** before archival

### Session Lifecycle

1. **Admission** — Symbol enters watchlist based on activity scoring
2. **Sampling** — Market data captured every ~10 seconds for the 2-hour session duration
3. **Archival** — Session data finalized and written to daily partition

---

## What Gets Captured

### Activity Signals
- Trading volume and trade count
- Order book depth and imbalance
- Spread dynamics and microstructure metrics
- Taker buy/sell ratios

### Silence Detection
- Symbols with no recent social mentions are flagged (`is_silent`)
- Enables filtering for "quiet" periods vs. active discussion

### Sentiment Polarity
- Post-level 3-class classification
- Aggregated counts and mean scores per observation window
- Confidence metrics from model predictions

**Note on positive skew**: Sentiment language in cryptocurrency-related social media discourse is characteristically skewed positive. The V2 pipeline partially addresses this through improved negative sentiment recall and relevance filtering that removes non-crypto noise. The dataset continues to reflect observed narrative tone rather than normalized sentiment.

### Volume Context
- Spot volume relative to historical norms
- Open interest changes (futures)
- Funding rate regime indicators

---

## Data Quality

### Validation Checks

Each observation undergoes validation:
- Timestamp consistency
- Numeric range checks
- Cross-field logic validation
- Source data completeness

### Quality Flags

Tier 3 includes boolean flags indicating:
- Data source availability (`spot_data_ok`, `futures_data_ok`, `twitter_data_ok`)
- Fallback calculation usage (`mom_fallback`, `vol_fallback`)
- Contract existence for futures data

---

## Coverage

### Temporal
- Daily exports since December 2025
- Continuous 24/7 collection

### Asset Universe
- All USDC-quoted pairs on Binance spot
- Corresponding USDT perpetual contracts (where available)

### Filtering
- Data completeness is required for admission — both market data from Binance and a sentiment cycle from the scraper must be present
- Symbols with missing fields from either source are excluded from the watchlist for that monitoring period

---

## Limitations

- **Single exchange**: Market data from Binance only
- **Single platform**: Social data from X (Twitter) only
- **English-centric**: Sentiment model trained primarily on English text
- **Latency**: Data is processed in batch, not real-time

---

## Updates

Schema and methodology may evolve. Version numbers in metadata track changes:
- `schema_version` — Document structure version
- `archive_schema_version` — Version at time of archival
- `methodology_regime` — Pipeline configuration version (`"v1"` or `"v2"`)
- `sentiment_model_version` — Model generation (`"v1.0"` or `"v2.0"`)
