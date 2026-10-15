# Tier 1 Schema Reference

This document provides exhaustive field-by-field documentation for the Tier 1 daily parquet exports.

For an introduction to the dataset, quick start examples, and file layout, see [README_TIER1.md](README_TIER1.md).

---

## Column Reference

Tier 1 provides a **flat schema** with 19 columns. All nested structures from the source data have been flattened into simple column names | Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Trading pair symbol (e.g., "BTCUSDC") |
| `snapshot_ts` | string | Observation timestamp (ISO 8601) |
| `meta_added_ts` | string | When session was admitted to watchlist |
| `meta_expires_ts` | string | Session expiration time |
| `meta_duration_sec` | double | Total session duration in seconds |
| `meta_archive_schema_version` | int64 | Schema version at archival time |
| `spot_mid` | double | Mid price from order book |
| `spot_spread_bps` | double | Bid-ask spread in basis points |
| `spot_range_pct_24h` | double | 24-hour price range as percentage |
| `spot_ticker24_chg` | double | 24-hour price change percentage |
| `derived_liq_global_pct` | double | Global liquidity percentile rank |
| `derived_spread_bps` | double | Derived spread in basis points |
| `score_final` | double | Final composite admission score |
| `sentiment_posts_total` | int64 | Total X (Twitter) posts in cycle |
| `sentiment_posts_pos` | int64 | Positive sentiment posts count |
| `sentiment_posts_neu` | int64 | Neutral sentiment posts count |
| `sentiment_posts_neg` | int64 | Negative sentiment posts count |
| `sentiment_mean_score` | double | Mean hybrid sentiment score |
| `sentiment_is_silent` | bool | No recent posts for this symbol |

---

## Detailed Field Reference

### Identity Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | The cryptocurrency trading pair symbol in BASEQUOTE format (e.g., 'ALTUSDC' where ALT is the base asset and USDC is the quote currency). This is the exchange symbol used on Binance spot market. The symbol identifies which coin is being tracked in this watchlist session. Pattern: 3-15 uppercase alphanumeric characters |
| `snapshot_ts` | string | UTC timestamp of when this watchlist entry was first created/admitted. Format: 'YYYY-MM-DDTHH:MM:SS.sssZ' (ISO 8601 with Z suffix). This marks the start of the 2-hour tracking session |

### Meta Fields

| Field | Type | Description |
|-------|------|-------------|
| `meta_added_ts` | string | UTC timestamp (ISO 8601) of when this session was admitted to the active watchlist. This is the official session start time. Format: 'YYYY-MM-DDTHH:MM:SS.ssssssZ' |
| `meta_expires_ts` | string | UTC timestamp (ISO 8601) when this session will expire. Calculated as added_ts + TTL (default 2 hours / 7200 seconds). After this time, the entry is archived and removed from active watchlist |
| `meta_duration_sec` | double | Total session duration in seconds from admission to archival. Calculated as (expired_ts - added_ts).total_seconds(). Typically ~7200 seconds (2 hours) but may vary slightly based on archiver timing |
| `meta_archive_schema_version` | int64 | The schema version of the entry at the time of archival. Copied from schema_version to preserve the original schema even if migrations occur. Used for archive compatibility. Current production version is 7 |

### Spot Market Fields

| Field | Type | Description |
|-------|------|-------------|
| `spot_mid` | double | Mid-price calculated as (bid + ask) / 2, in quote currency (USD for USDC pairs). This is the theoretical fair price at the moment of snapshot |
| `spot_spread_bps` | double | Bid-ask spread expressed in basis points (1 bps = 0.01%). Formula: 10000 * (ask - bid) / mid. Lower values indicate tighter, more liquid markets. Example: 7.5 bps means the spread is 0.075% of the mid price |
| `spot_range_pct_24h` | double | 24-hour price range as a percentage of mid price. Formula: 100 * (high24 - low24) / mid. Measures intraday volatility - higher values indicate more price movement. Example: 5.46 means the 24h high-low range was 5.46% of current price |
| `spot_ticker24_chg` | double | 24-hour price change as a signed percentage. Positive = price increased, negative = price decreased over last 24 hours. Example: -0.149 means price dropped 0.149% in 24h |

### Derived Fields

| Field | Type | Description |
|-------|------|-------------|
| `derived_liq_global_pct` | double | Global liquidity percentile rank across ALL trading pairs in the universe. Range: 0-100 percentile. Measures this coin's 24h quote volume relative to all other coins. Formula: percentile_rank(this_coin_qv, all_coins_qv) * 100. Higher = more liquid than peers. Example: 31.7 means this coin has more volume than ~32% of all coins |
| `derived_spread_bps` | double | Current bid-ask spread in basis points. Formula: ((ask - bid) / mid) * 10000. Example: 7.56 bps = 0.0756% spread. NOTE: This field is updated by the sampler every ~10 seconds during the 2-hour session, so the archived value reflects the LAST sample before expiry |

### Score Fields

| Field | Type | Description |
|-------|------|-------------|
| `score_final` | double | A composite quality score (0-100) derived from weighted individual factor scores. Key factors include **Price Action** (Momentum, Volatility), **Liquidity Health** (Spread Efficiency, Depth), and **Order Flow** (Taker Buy/Sell Pressure). This metric acts as a quality filter: higher scores (≥60) indicate tradeable, liquid assets with strong market interest, while lower scores filter out predominantly illiquid or noise-heavy pairs |

### Sentiment Fields

These fields are derived from X (Twitter) sentiment analysis using a hybrid two-model AI system (DistilBERT transformers fine-tuned on crypto Twitter data) | Field | Type | Description |
|-------|------|-------------|
| `sentiment_posts_total` | int64 | Total number of tweets collected and analyzed for this cryptocurrency during the most recent scraping cycle. A 'cycle' is one complete pass through all tracked coins in the data collection schedule. The duration of a cycle varies based on API rate limits and queue size (typically ~49 minutes) |
| `sentiment_posts_pos` | int64 | Count of tweets classified as POSITIVE sentiment using lexicon-based analysis. A tweet is positive if its sentiment score > 0.1 on a scale of -1.0 to +1.0. The lexicon matches terms from categories: positive_general (bullish, moon, hodl, gains, etc.) and pump_hype (pump, breakout, rally, etc.) |
| `sentiment_posts_neu` | int64 | Count of tweets classified as NEUTRAL sentiment using lexicon-based analysis. A tweet is neutral if its sentiment score is between -0.1 and +0.1 on a scale of -1.0 to +1.0. These tweets contain no strong positive or negative sentiment signals |
| `sentiment_posts_neg` | int64 | Count of tweets classified as NEGATIVE sentiment using lexicon-based analysis. A tweet is negative if its sentiment score < -0.1 on a scale of -1.0 to +1.0. The lexicon matches terms from categories: negative_general (bearish, crash, dump, etc.), fud_fear (fud, scam, rugpull, etc.), and scam_rug |
| `sentiment_mean_score` | double | Mean of hybrid_score_3class values across all tweets. Each tweet gets -1.0 (negative), 0.0 (neutral), or +1.0 (positive) from the hybrid two-model AI system. Range: -1.0 to +1.0. Positive values indicate overall positive sentiment, negative values indicate overall negative. Example: 0.67 means sentiment skews positive. The hybrid system uses a primary DistilBERT model for classification and a referee model for confidence calibration and overrides. *Note: Sentiment means are typically positive due to structural properties of crypto social discourse; interpret alongside post counts, balance, and silence indicators.* |
| `sentiment_is_silent` | bool | True if zero tweets were collected for this coin during this scraping cycle. A silent coin may indicate low market interest or search query issues |

---

## Type Reference

| Type | Description |
|------|-------------|
| `string` | UTF-8 text |
| `int64` | 64-bit signed integer |
| `double` | 64-bit floating point |
| `bool` | Boolean (true/false) |

---

## Field Mapping

Tier 1 flattens nested fields from the source data. Here's the mapping:

| Tier 1 Column | Source Path |
|---------------|-------------|
| `symbol` | `symbol` |
| `snapshot_ts` | `snapshot_ts` |
| `meta_added_ts` | `meta.added_ts` |
| `meta_expires_ts` | `meta.expires_ts` |
| `meta_duration_sec` | `meta.duration_sec` |
| `meta_archive_schema_version` | `meta.archive_schema_version` |
| `spot_mid` | `spot_raw.mid` |
| `spot_spread_bps` | `spot_raw.spread_bps` |
| `spot_range_pct_24h` | `spot_raw.range_pct_24h` |
| `spot_ticker24_chg` | `spot_raw.ticker24_chg` |
| `derived_liq_global_pct` | `derived.liq_global_pct` |
| `derived_spread_bps` | `derived.spread_bps` |
| `score_final` | `scores.final` |
| `sentiment_posts_total` | `twitter_sentiment_windows.last_cycle.posts_total` |
| `sentiment_posts_pos` | `twitter_sentiment_windows.last_cycle.posts_pos` |
| `sentiment_posts_neu` | `twitter_sentiment_windows.last_cycle.posts_neu` |
| `sentiment_posts_neg` | `twitter_sentiment_windows.last_cycle.posts_neg` |
| `sentiment_mean_score` | `twitter_sentiment_windows.last_cycle.hybrid_decision_stats.mean_score` |
| `sentiment_is_silent` | `twitter_sentiment_windows.last_cycle.sentiment_activity.is_silent` |
