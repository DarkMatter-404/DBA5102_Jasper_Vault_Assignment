# Data sources and provenance

## Assignment inputs

Original training orders, complete supplied BTC minute history and the new validation CSV are bundled in `data/assignment_inputs/`. Compression changes storage, not CSV contents; `data/input_manifest.json` records compressed and uncompressed hashes. The original validation upload is unchanged. These files remain assignment data, not newly collected market information.

The frozen component model is copied exactly from V3.1's July-1 artifact. No new labels, vocabulary fitting or coefficients are introduced. Existing headline and BTC extracts remain dependencies under `jay/revision_v3_1/data/`.

## News extension

`data/news_extension.csv` contains 65 short CoinDesk headlines: 37 August, 21 September and 7 October 2026. `data/news_combined_2026.jsonl` combines them with the original 88 records. Each added row retains its publisher URL, title, displayed date line, UTC publication and later publication/update bound, retrieval date and retrieval-response hash. The latest included publisher bound is October 12 at 10:20 UTC. No article bodies are redistributed.

Discovery used date/topic searches for BTC/crypto markets across August–October, then publisher-page verification. Live blogs were excluded because their evolving headlines and multiple post clocks are ambiguous. Searches for October 13 primarily returned live blogs, which remained excluded. A second pass queried the social-sample Sundays August 2, 9, 16 and 23 and included crypto policy, security and infrastructure coverage. All eligible non-live results from that pass were retained, independent of model direction or outcomes. The discovery/exclusion ledger is included.

This is a convenience sample with uneven dates and a single publisher for the added headlines. Search discoverability is not a complete historical archive. The later displayed update clock is used conservatively, but it does not prove that today's headline text was present at that historical time. `first_seen_at` and `nlp_ready_at` stay blank for historical reconstruction. We do not label retrospective downloads as observed historical feeds.

Copyright remains with each publisher. Short headlines, factual metadata and links are retained for this academic experiment. The collection is not a freely licensed full-text dataset or a verified production-news license.

## Social extension

**Attribution:** Instrumetriq (2026), *Instrumetriq Crypto Market Activity & Sentiment Context Dataset*, [DOI 10.5281/zenodo.18508636](https://doi.org/10.5281/zenodo.18508636), [public repository](https://github.com/SiCkGFX/instrumetriq-public). Free samples and documentation are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Source reference: `c97da362f0d2e48a3dc3d87ee7d45889ee806b0d`. The complete added-file paths, byte sizes and Git blob hashes appear in `data/instrumetriq/source_manifest.json`.

We downloaded all 11 available Tier-1 weekly CSVs dated August 2 through October 11: 24,180 asset observations, including 103 BTC snapshots. Combining with the original 248 yields 351 BTC snapshots. A conservative February 17 methodology cutoff leaves 322 usable research records. Changes made: BTC selection, IDs, source hashes, availability proxies and model features. No endorsement by the provider is implied.

The provider describes X-post deduplication, crypto relevance filtering, primary BERTweet sentiment and a DistilBERT confidence/referee step. We consume its precomputed aggregate score, not individual posts. Tier-1 positive/neutral/negative counts and its hybrid mean score should not be treated as interchangeable; raw counts are checked for internal consistency, not used to reconstruct the hybrid score.

The flattened sample does not carry all provider model-version/quality fields, so the cutoff is a timestamp-based methodology inference. Snapshot admissions are not verified sentiment receipt times. We wait until the reconstructed session end plus processing delay and impose a four-hour admission-age limit. Weekly coverage, selection by provider activity, positive-language skew and dependence across snapshots limit generalisation. Provider market fields are not used as a substitute for missing assignment candles.

See the bundled original `LICENSE_source.md`, `METHODOLOGY_source.md` and `README_source.md`. Full paid/subscription data has separate terms; the free-sample license should not be assumed to cover it.

## Reproducibility boundary

Pinned social samples and curated headline metadata reproduce the delivered experiment offline. Rerunning web search or RSS later can produce different documents or revisions; archive immutable observations if building a prospective dataset. Actual future receipt logging is supplied separately by the forward adapters.
