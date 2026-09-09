# NIC weekly sales tracker: Wednesday run

Runs every Wednesday 06:00 CT as a Cowork scheduled task. Fresh session, no memory. Everything needed is below.
Repo: https://github.com/High-Shot/NIC (Pages serves `index.html` from main). Local clone on Barcus's Mac: `~/Documents/Claude/Projects/Cerakote Management/nic-tracker` (connected folder "Cerakote Management"; gh is logged in there, no token stored anywhere).

Reporting week = Monday to Sunday. WEEK = the Sunday just passed, formatted `WE_YYYY-MM-DD`; START = that Monday. On a Wednesday run: WEEK = `date -d 'last sunday' +WE_%F`, START = `date -d 'last sunday -6 days' +%F`, END = the Sunday.
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

## 2. Helium10: Legacy, Prismatic, SA, MX
`mcp__Helium10__get_account_profit_and_loss_summary_series` and `get_product_profit_and_loss_summary_series` with `current_date_from: START, current_date_to: END, granularity: "week"`; the single bucket key is START.
- CL_US: `seller_ids: ["A1KUYEQ8RRQVVI"], marketplace: ["US"]`, products `product_level: "asin", page_size: 10, sort_by: "sales"` (top 10 by revenue, that is the product block rule).
- PP_US: `seller_ids: ["A21D21T8B6U09C"], marketplace: ["US"]`, same product call.
- CC_SA: `seller_ids: ["A3BMUMIXNXIR6G"], marketplace: ["SA"], currency: "SAR"`, products `page_size: 20`.
- CC_MX: `seller_ids: ["AOXMQPMOL1F1Y"], marketplace: ["MX"], currency: "MXN"`, account call only unless it shows sales.
Write `data/raw/$WEEK/h10_<TAB>.csv`:
```
tab,asin,name,sales,gross_revenue,units,sessions,ad_cost,ads_acos
<TAB>,_TOTAL_,,<sales>,<gross_revenue>,<units_sold>,<sessions>,<abs advertising_cost>,<ads_acos>
<TAB>,<asin>,<short name>,...
```
Short name: strip "CERAKOTE"/"PRISMATIC POWDERS", keep colour/size/code, under 45 chars. ad_cost as a positive number.

## 3. NTB (until the Ads API is connected)
If `inbox/*.xlsx` or `inbox/*.csv` exist (the Reports Beta master report, daily rows, last 30 days): `python3 scripts/ingest_ntb.py $WEEK inbox/<file>` then move the file to `inbox/processed/`. If the Gmail search `from:amazon subject:"report" newer_than:3d has:attachment` finds the scheduled report attachment, save it to `inbox/` first (`mcp__Gmail__get_message` for the attachment). No file: continue, the week is flagged "NTB not loaded".

## 4. Normalize, build, QA
```
python3 scripts/normalize.py <prior WEEK>
python3 scripts/normalize.py $WEEK
python3 scripts/build.py
```
QA before publishing: every tab present (`missing: none`); CC_US sessions above 50,000 and units within 30% of the prior week; product revenue sum within 3% of the account total per CC tab; ad spend account total within 5% of the sum of per-ASIN spend plus the flagged unattributed amount. Anything outside goes into the summary as a flag, it does not stop the publish.

## 5. Notes
Write `notes/$WEEK.md`: the Part 2 analysis (global summary with WoW, brand snapshots, action flags: ACoS above 30%, TACoS above 15%, CVR below 1%, zero spend on a live product, unmapped ASINs, missing data). Keep the rolling last 4 weeks readable at the top of `notes/README.md` (newest first, one paragraph each).

## 6. Publish (from the Mac)
6a. `SendUserFile` + `mcp__remote-devices__device_commit_files` for: `index.html`, `data/weeks/$WEEK.json`, `data/weeks/<prior WEEK>.json`, every file in `data/raw/$WEEK/` and the refreshed prior-week raw files, `notes/$WEEK.md`, `notes/README.md`, `config/fx.json`, into the matching paths under `/Users/barcus/Documents/Claude/Projects/Cerakote Management/nic-tracker/`.
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
