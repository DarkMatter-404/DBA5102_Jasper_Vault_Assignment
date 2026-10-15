# Jasper PP pricing

Thu, 10 Sept 26

## Jasper Vault and Perpetual Protect Overview

- Jasper Vault: derivatives trading platform; core product is Perpetual Protect (PP)
- PP designed for traders who want short-term downside protection without closing their leveraged perp position
- Works like insurance: user pays a premium upfront, Jasper Vault covers losses during the protection window
- Protection periods: 0.5, 1, 2, 4, 8, 12, or 24 hours
- All assignment data uses ATM (0% deductible, 100% coverage) only; OTM/moneyness not in scope

## How PP Pricing Works

- Premium driven by three main factors:
  - Moneyness (ATM vs. OTM): all assignment data is ATM
  - Duration: longer protection = higher premium (like insurance)
  - Market volatility: implied vol and realized vol both matter
- Current model: Black-Scholes base premium + CTA strategy overlay (RSI, Bollinger Bands, etc.) = final premium
- Base premium will be added to the dataset after this session
- Base premium is not the “correct answer”: it reflects existing methodology, which the project aims to improve

## Dataset Walkthrough

- PP transaction training data covers 2nd February to 31st July 2026
- August data held back as validation set (not released)
- Key columns per row:
  - Open/close timestamps and expiration timestamp
  - Option type: 0 = call (long), 1 = put (short)
  - Product tag: protection duration in seconds (e.g. 1,800 = 30 min)
  - BTC quantity and strike price (notional = quantity × strike)
  - Premium amount paid and realized P&L (payout from Jasper Vault to user)
- Close time can differ from expiration if user exits early
- BTC market history CSV provided at 1-minute intervals (OHLCV + trade count)
- Additional data can be sourced externally (e.g. Binance, TradingView) if needed

## Modeling Approaches

- Two directions, both acceptable:
  - Direction 1: keep base premium as foundation, build a dynamic multiplier on top
    - Question to answer: when to mark up or down, and by how much
    - Formula: finalPremium = basePremium × dynamicMultiplier
  - Direction 2: ignore base premium entirely, build fair-value pricing from scratch
    - Can use statistical, ML, or alternative option pricing models (e.g. Black-76)
- Hybrid approach suggested: financially interpretable fair value model + data-driven adjustment layer
- Zero-DTE context matters: very short duration means sudden volatility spikes and macro events have outsized impact
  - Suggested to incorporate macro/event data and sentiment signals (e.g. Twitter, economic calendars)
  - RSI/Bollinger Band features alone likely insufficient
- Pricing objective: not maximum premium, but accurate risk pricing that remains commercially attractive to users

## Next Steps and Support

- Base premium column to be added to the training dataset and re-uploaded after this session
- A group chat will be set up for ongoing Q&A with Jeremy and Wang Zhi (quant team)
- Session recording to be shared for students who could not attend
