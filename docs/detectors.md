The detector engine turns a consent-filtered ledger into deduplicated observations. This document is for judges and developers reviewing the rules.

# Detector catalogue

| Module | Detector | Input and rule | Minimum data / limitation |
|---|---|---|---|
| Cashflow | `safe_to_spend` | Spendable current/wallet balance less upcoming debits and buffer, divided by days to income | Recurring income or payday hint |
| Cashflow | `income_expense_crossover` | Three 30-day net-income windows; project a declining linear margin | 90 days; trends are not forecasts |
| Cashflow | `bill_spike` | Latest recurring amount or utility month above 130% of baseline (`BILL_SPIKE_RATIO_BPS`) | Four cycles or three prior months |
| Leaks | `zombie_subscription` | Subscription-like series with at least three cycles; rank annual cost | Cannot observe usage; asks “Still using this?” |
| Leaks | `renewal_countdown` | Active debits due within seven days (`RENEWAL_DAYS`) | Known active series |
| Leaks | `double_charge_price_change` | Equal merchant/amount within 48 hours, or recurring change of at least 5% | Excludes known repeating merchants |
| Behaviour | `temporal_spending_spikes` | Weekday discretionary bucket above 140% average | Four samples in a bucket and 12 overall |
| Behaviour | `merchant_monopoly` | One merchant above 35% of 30-day discretionary spend | Three transactions |
| Behaviour | `velocity_warning` | Month projection exceeds income, or pace exceeds 125% of typical | Day 5, income and history |
| Wealth | `found_money_redirection` | Lapsed/cancelled series, bill drop, or unusually large credit | Requires a comparable baseline |
| Wealth | `opportunity_cost_swap` | Redirect 20% of largest discretionary category at configured basis-point rate | Three transactions; illustration only |
| Wealth | `idle_cash_optimisation` | Surplus beyond buffer and average month, low rate, idle for 30 days | Account movement and rate data |

Exact constants live in `backend/app/insights/config.py`. All calculations use integer arithmetic. Wealth output includes: “Educational information, not financial advice.”

## Related docs

- [Architecture](architecture.md)
- [Testing](testing.md)
- [Known gaps](KNOWN_GAPS.md)
