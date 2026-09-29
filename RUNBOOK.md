# NIC weekly sales tracker: Monday + Thursday run

Runs Monday and Thursday 07:00 CT as a scheduled task (Monday builds the week, Thursday re-runs it after sessions and attribution settle). The NTB report email lands Mon/Wed/Thu around 05:00 CT, before either run. Fresh session, no memory. Everything needed is below.
Repo: https://github.com/High-Shot/NIC (Pages serves `index.html` from main). Local clone on Barcus's Mac: `~/Documents/Claude/Projects/Cerakote Management/nic-tracker` (connected folder "Cerakote Management"; gh is logged in there, no token stored anywhere).

Reporting week = Monday to Sunday. WEEK = the Sunday just passed, formatted `WE_YYYY-MM-DD`; START = that Monday. On either run: WEEK = `date -d 'last sunday' +WE_%F`, START = `date -d 'last sunday -6 days' +%F`, END = the Sunday.
Also re-run the PRIOR week (WEEK minus 7 days) for Scale Insights sales and campaign totals only: attribution settles late and the numbers move.

Goal: `data/raw/$WEEK/*`, `data/weeks/$WEEK.json`, rebuilt `index.html`, pushed to GitHub, then the Part 2 summary to Barcus.

## 0. Setup (cloud shell)
```
git clone https://github.com/High-Shot/NIC.git /home/claude/NIC && cd /home/claude/NIC
mkdir -p data/raw/$WEEK
python3 scripts/fx_update.py
```
Publishing happens FROM THE MAC (step 6). If the cloud clone fails for network reasons, work from the Mac copy through the connected folder instead.

## 1. Scale Insights: Cerakote Auto markets (US, CA, UK, DE, FR, IT, ES, NL, AU)
Three calls per market, dates = START to END. Country codes are the `si_country` values in `config/accounts.json`.

1a. `mcp__Scale_Insights__get_sales_data` with `country, start_date, end_date, mode: "raw", count: 100, include_growth: false`. Page 2 if `Meta.has_next_page`.
Write `data/raw/$WEEK/si_sales_<CC>.csv`, header exactly:
```
market,asin,sku,title,sales,units,orders,ppc_cost,ppc_sales,sessions
```
First data row is the account total from `Summary`: `market,_TOTAL_,,,TotalSales,TotalUnits,TotalOrders,TotalPPCCost,TotalPPCSales,TotalSessions`. Then one row per ASIN: ASIN, SKU, Title (first 80 chars, no commas needed since the field is quoted), TotalSales, TotalUnits, TotalOrders, TotalPPCCost, TotalPPCSales, TotalSessions. Include zero-sales ASINs. When the result overflows to a tool-results file, convert it with `python3 scripts/tools/sales_to_csv.py <file> <CC> <dest>` instead of retyping.

Page Views: Scale Insights and Helium10 do not report Page Views, so it is sourced from the Amazon Business Report. To populate it for a market, drop that market's "Detail Page Sales and Traffic by Child Item" export (same Mon–Sun range) at `data/raw/$WEEK/business_report_<TAB>.csv` (e.g. `business_report_CC_US.csv`). normalize.py sums its `Page Views - Total` by `(Child) ASIN` into each product and the account. The file is optional: no file leaves Page Views at 0 for that market, nothing else is affected.

1b. `mcp__Scale_Insights__get_campaign_performance` with `country, start_date, end_date, mode: "raw", count: 1, sort_by: "cost"`. Only the `agg` block matters.
Write `data/raw/$WEEK/si_campaigns_<CC>.csv`:
```
market,campaign,ad_type,state,spend,sales,orders
<CC>,_TOTAL_,,,<agg.TotalSpend>,<agg.TotalAdSales>,<agg.TotalOrders>
```
(numbers without currency symbols). Optional: add SB rows with `ad_type: "SB", count: 500` for the SB cross-check; not required for the build.

1c. `mcp__Scale_Insights__get_bsr_data` with `country, start_date, end_date, count: 20, asin_list: [the 12 main ASINs]` where the main ASINs are `B084RQKLV8, B07SHJVK4G, B0B94G13CN, B0F45C2YHV, B0FYRJ1966, B0CN8HJSYM, B0DJMW6283, B0DKVZRX69, B0CQN1RXYB, B0DVB4P9KQ, B0FW6WFX4D, B0FX5WH19H` (US: also `B0DVV6K9Y6`).
Write `data/raw/$WEEK/si_bsr_<CC>.csv`:
```
market,asin,category,category_rank,subcategory,subcategory_rank
```
category = `Category`, category_rank = `LatestRank`, subcategory and subcategory_rank = the first entry of `OtherCategoryRanks` split on the last `: #` (strip commas from the rank). Skip ASINs the call does not return.

Prior-week refresh: repeat 1a and 1b for WEEK minus 7 days into `data/raw/<prior WEEK>/` (overwrite the two files). Skip 1c.

## 2. Helium10: Legacy, Prismatic, SA (MX archived 2026-09-09, skip it)
`mcp__Helium10__get_account_profit_and_loss_summary_series` and `get_product_profit_and_loss_summary_series` with `current_date_from: START, current_date_to: END, granularity: "week"`; the single bucket key is START.
- CL_US: `seller_ids: ["A1KUYEQ8RRQVVI"], marketplace: ["US"]`, products `product_level: "asin", page_size: 10, sort_by: "sales"` (top 10 by revenue, that is the product block rule).
- PP_US: `seller_ids: ["A21D21T8B6U09C"], marketplace: ["US"]`, same product call.
- CC_SA: `seller_ids: ["A3BMUMIXNXIR6G"], marketplace: ["SA"], currency: "SAR"`, products `page_size: 20`.
Write `data/raw/$WEEK/h10_<TAB>.csv`:
```
tab,asin,name,sales,gross_revenue,units,sessions,ad_cost,ads_acos
<TAB>,_TOTAL_,,<sales>,<gross_revenue>,<units_sold>,<sessions>,<abs advertising_cost>,<ads_acos>
<TAB>,<asin>,<short name>,...
```
Short name: strip "CERAKOTE"/"PRISMATIC POWDERS", keep colour/size/code, under 45 chars. ad_cost as a positive number.

## 3. NTB (until the Ads API is connected)
Source: the scheduled Reports Beta report "NIC Weekly Tracker - Master Ad Report - 30" (daily rows, last 30 days, all advertiser accounts). Amazon emails it Monday, Wednesday and Thursday around 05:00 CT from no-reply@ads.amazon.com (schedule changed 2026-09-29 from Wednesday-only, so the Monday run has NTB; the report schedule ends 2026-12-31 and must be extended in Reports Beta before then). The email has NO attachment: it holds a pre-signed S3 download link that expires 48 hours after sending. (Before 2026-09-24 this step searched `has:attachment` at 06:00 CT, two hours before the email lands, so it never found anything and WE 9/13 and 9/20 shipped with NTB = 0.)

3a. Gmail search `from:no-reply@ads.amazon.com subject:"Master Ad Report" newer_than:2d`. Take the newest message, `mcp__Gmail__get_message` with `messageFormat: FULL_CONTENT`, write its `htmlBody` to a scratch file, then:
```
python3 scripts/tools/fetch_ntb_report.py <scratch html file> inbox
```
It prints the saved CSV path. If no email is found or the download fails, also use any file Barcus dropped in `inbox/` by hand.
3b. For each file in `inbox/`: `python3 scripts/ingest_ntb.py $WEEK inbox/<file>` and again for the prior WEEK (the 30-day window covers both), and once more with `--period <1st of MONTH> END` (see 4b), then move the file to `inbox/processed/`. Commit `inbox/processed/` with the rest.
The ingest also writes `ads.csv` (spend and ad sales per tab and product, all campaign types). normalize.py uses it for the Helium10 tabs (CL_US, PP_US, CC_SA) instead of Helium10's ACoS-derived ad sales, which miss most SB/SD sales.
3c. Check `data/raw/$WEEK/ntb_spend_check.csv` against the Scale Insights and Helium10 spend totals: they match to the cent when the export is complete; normalize.py flags any tab under 95% coverage.
No report at all: continue, the week is flagged "NTB not loaded", and say so at the TOP of the summary to Barcus (the dashboard shows 0 NTB until it is loaded).

## 4. Normalize, build, QA
```
python3 scripts/normalize.py <prior WEEK>
python3 scripts/normalize.py $WEEK
python3 scripts/build.py
```
QA before publishing: every tab present (`missing: none`); CC_US sessions above 50,000 and units within 30% of the prior week; product revenue sum within 3% of the account total per CC tab; ad spend account total within 5% of the sum of per-ASIN spend plus the flagged unattributed amount. Anything outside goes into the summary as a flag, it does not stop the publish.

## 4b. Month-to-date period (feeds the site's Month view with exact totals)
MONTH = the month of END. PDIR = `data/raw/P_<1st of MONTH>_<END>/`.
- Scale Insights, 9 markets: steps 1a and 1b with `start_date` = 1st of MONTH, `end_date` = END, written to PDIR (same file names and headers). Skip 1c.
- Helium10, 3 tabs: `get_account_profit_and_loss_summary` and `get_product_profit_and_loss_summary` (no series) for the same window, same seller ids and product rules as step 2, written to `PDIR/h10_<TAB>.csv` in the step 2 format.
- NTB: `python3 scripts/ingest_ntb.py --period <1st> END inbox/<file>` (step 3b).
- `python3 scripts/normalize.py --period <1st> END` writes `data/periods/<YYYY-MM>.json`.
Month rollover: when END is in a new month and the prior month is not yet closed (`complete: false` in its periods file), repeat the four steps for the prior month's 1st through last day so it closes on full numbers. Older P_ folders for the same month can stay; build uses the newest periods file per month.

## 5. Notes
Write `notes/$WEEK.md`: the Part 2 analysis (global summary with WoW, brand snapshots, action flags: ACoS above 30%, TACoS above 15%, CVR below 1%, zero spend on a live product, unmapped ASINs, missing data). Keep the rolling last 4 weeks readable at the top of `notes/README.md` (newest first, one paragraph each).

## 6. Publish (from the Mac)
6a. `SendUserFile` + `mcp__remote-devices__device_commit_files` for: `index.html`, `data/weeks/$WEEK.json`, `data/weeks/<prior WEEK>.json`, every file in `data/raw/$WEEK/` and the refreshed prior-week raw files, PDIR and `data/periods/<YYYY-MM>.json`, `notes/$WEEK.md`, `notes/README.md`, `config/fx.json`, into the matching paths under `/Users/barcus/Documents/Claude/Projects/Cerakote Management/nic-tracker/`.
6b. `mcp__remote-devices__Control_your_Mac__osascript`:
```
do shell script "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; cd \"$HOME/Documents/Claude/Projects/Cerakote Management/nic-tracker\" && git pull -q --rebase origin main; git add -A && git commit -q -m 'Weekly update $WEEK' && git push -q origin main && git log --oneline -1"
```
6c. Mac unreachable: report "not published" in the summary; the files are already in the folder and the next run pushes them.
6d. Confirm within 5 minutes: `https://raw.githubusercontent.com/High-Shot/NIC/main/index.html` contains `"label":"WE M/D"` for this week.

## 7. Summary message to Barcus (SendUserMessage)
Lead line: "NIC $WEEK: global $X USD (WoW %), spend $Y (WoW %), TACoS Z%". Then one line per brand: revenue, WoW, TACoS, ACoS, the top and bottom product by revenue. Then action flags. Then data flags (unmapped ASINs, unattributed ad spend %, NTB status, any market with no data, prior-week restatement if it moved more than 1%). Then publish status and the link https://high-shot.github.io/NIC/. No other prose.

## Rules
- Never invent a number. A market with no data is "no data", never zero.
- Never pause to ask a question. Make the reasonable call, flag it in the summary.
- A failed step must not stop the run. Skip it, continue, report it.
- Read-only: nothing here touches ads, listings, the Google Sheet, or Drive.
