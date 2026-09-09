# NIC Industries Weekly Sales Tracker

Weekly Amazon performance dashboard for NIC Industries: Cerakote Ceramics (US, CA, UK, FR, DE, IT, ES, NL, AU, SA; MX archived 2026-09-09), Cerakote Legacy (US), Prismatic Powders (US).
Live page: https://high-shot.github.io/NIC/

Same shape as the INTL health tracker: API pulls land in `data/raw/`, `normalize.py` turns them into one JSON per week, `build.py` injects the weeks into `template.html`, output is a static `index.html` on GitHub Pages. No Google Sheet, no Apps Script, no downloads except the NTB report until the Amazon Ads API is connected.

```
config/accounts.json      tab -> brand, market, currency, source (Scale Insights or Helium10), seller id
config/data_map.json      ASIN -> product, campaign-name tokens, KPI thresholds, top-N rule for Legacy and Prismatic
config/fx.json            USD rates for the GLOBAL view (refreshed by scripts/fx_update.py)
data/raw/WE_<Sunday>/     source pulls for the week (CSV, see RUNBOOK.md for exact shapes)
data/weeks/WE_<Sunday>.json   normalized week: acct + products + flags per tab
scripts/normalize.py      raw -> week JSON (mapping, ad allocation, BSR, NTB, flags)
scripts/ingest_ntb.py     Reports Beta daily master report -> data/raw/<week>/ntb.csv (cuts Mon-Sun)
scripts/build.py          weeks -> index.html
scripts/fx_update.py      refresh FX rates
template.html             the dashboard (v3.9: FX-normalised GLOBAL, Thursday-rule MTD, MONTH view, pp deltas)
inbox/                    drop the Reports Beta master report here for the Wednesday run
RUNBOOK.md                what the Wednesday scheduled task does, step by step
```

## Source rules
- Revenue, units, sessions: Scale Insights `get_sales_data` for Cerakote Auto markets (matches Seller Central within 0.3%); Helium10 P&L weekly series for Legacy, Prismatic, SA. Helium10 `sales` for US sellers, `gross_revenue` (VAT/GST inclusive) elsewhere.
- Ad spend and ad sales: account totals from Scale Insights campaign totals (SP+SB+SD); product level is the ASIN-attributed figure plus a pro-rata share of spend Scale Insights could not attribute (multi-ASIN SB/SD campaigns). Legacy and Prismatic: Helium10 spend, ad sales derived from Helium10 ACoS.
- NTB orders and sales: Reports Beta master report (daily rows, last 30 days, all advertiser accounts) until the Ads API is live. `ingest_ntb.py` cuts the Mon-Sun week, routes by advertiser account, marketplace and advertised ASIN, and writes the report's in-week spend per tab; `normalize.py` flags any tab where that spend covers under 95% of Scale Insights/Helium10 spend (campaigns missing from the export). Zero NTB with no report loaded is flagged, not silent.
- Archiving a market: set `"archived": "YYYY-MM-DD"` on its row in `config/accounts.json`. History stays in `data/weeks`, the tab leaves the nav and GLOBAL, no more pulls.
- BSR: Scale Insights `get_bsr_data`, main category rank plus the first subcategory rank.
- Page Views: dropped (not exposed by either API; CVR uses sessions).
- Reporting week is Monday to Sunday, WE = Sunday. Run on Wednesday: sessions are incomplete before then.

## Local rebuild
```
python3 scripts/normalize.py WE_2026-09-06
python3 scripts/build.py
```
