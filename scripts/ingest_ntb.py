#!/usr/bin/env python3
"""
Reports Beta master report (daily rows, Last 30 days, SP+SB+SD) -> data/raw/WE_<date>/ntb.csv

Keeps only rows whose Date falls inside the Mon-Sun week, routes each campaign to a tab and a product,
and writes new-to-brand orders and sales per tab (_TOTAL_) and per product. SB rows have no marketplace
in the export, so the [XX]_ campaign-name prefix decides the market; a campaign with neither is flagged.

Usage: python3 scripts/ingest_ntb.py WE_2026-09-06 inbox/master_report.xlsx [more files...]
Column names are matched loosely (case-insensitive substrings), so a renamed export still works.
"""
import csv, json, os, re, sys, datetime as dt
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS = json.load(open(os.path.join(ROOT, 'config', 'accounts.json')))
DM = json.load(open(os.path.join(ROOT, 'config', 'data_map.json')))
A2P, TOKENS, PRODUCTS = DM['asin_to_product'], DM['campaign_tokens'], DM['products']
MKT_TAB = {a['market']: a['tab'] for a in ACCOUNTS if a['brand'] == 'CC'}
MKT_TAB['AUS'] = 'CC_AUS'
ACCOUNT_BRAND = [('NIC-CERAKOTE', 'CL_US'), ('LEGACY', 'CL_US'), ('PRISMATIC', 'PP_US')]  # everything else is Cerakote Auto


def rows_from(path):
    if path.lower().endswith(('.xlsx', '.xlsm')):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(c or '').strip() for c in next(it)]
        for r in it:
            yield dict(zip(hdr, r))
    else:
        with open(path, newline='', encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh):
                yield r


def find_col(cols, *needles, exclude=()):
    for c in cols:
        lc = c.lower()
        if all(n in lc for n in needles) and not any(x in lc for x in exclude):
            return c
    return None


def num(v):
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return float(re.sub(r'[^0-9.\-]', '', str(v)) or 0)


def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()[:10]
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def route(campaign, account, marketplace):
    tab = None
    acc = (account or '').upper()
    for needle, t in ACCOUNT_BRAND:
        if needle in acc:
            tab = t
    if tab is None:
        m = re.match(r'\[([A-Z]{2,3})\]', campaign or '')
        mk = m.group(1) if m else (marketplace or '').upper()[:3]
        mk = {'AMAZON.COM': 'US', 'UNITED STATES': 'US', 'UNITED KINGDOM': 'UK', 'GB': 'UK', 'AUSTRALIA': 'AU', 'GERMANY': 'DE', 'FRANCE': 'FR',
              'ITALY': 'IT', 'SPAIN': 'ES', 'NETHERLANDS': 'NL', 'CANADA': 'CA', 'MEXICO': 'MX', 'SAUDI ARABIA': 'SA'}.get((marketplace or '').upper(), mk)
        tab = MKT_TAB.get(mk)
    prod = None
    m = re.search(r'\b(B0[A-Z0-9]{8})\b', campaign or '')
    if m:
        prod = A2P.get(m.group(1))
    if prod is None:
        for tok, p in TOKENS.items():
            if re.search(r'(^|[_\s\[\]])' + re.escape(tok) + r'([_\s\]]|$)', (campaign or '').upper()):
                prod = p; break
    if prod and prod.startswith('OTHER:'):
        prod = None
    return tab, prod


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    week = sys.argv[1]
    we = dt.date.fromisoformat(week.replace('WE_', ''))
    mon = we - dt.timedelta(days=6)
    out_dir = os.path.join(ROOT, 'data', 'raw', week)
    os.makedirs(out_dir, exist_ok=True)
    totals = defaultdict(lambda: [0.0, 0.0])       # (tab, product|_TOTAL_) -> [orders, sales]
    spend = defaultdict(float)                       # tab -> spend inside the week (cross-check vs Scale Insights)
    unmatched = []
    seen_dates = set()
    for path in sys.argv[2:]:
        first = True
        for r in rows_from(path):
            if first:
                cols = list(r.keys())
                c_date = find_col(cols, 'date')
                c_camp = find_col(cols, 'campaign name') or find_col(cols, 'campaign')
                c_acct = find_col(cols, 'account') or find_col(cols, 'advertiser') or find_col(cols, 'profile')
                c_mkt = find_col(cols, 'marketplace') or find_col(cols, 'country')
                c_spend = find_col(cols, 'spend') or find_col(cols, 'cost')
                c_ntbo = find_col(cols, 'new-to-brand', 'order') or find_col(cols, 'new to brand', 'order') or find_col(cols, 'ntb', 'order')
                c_ntbs = find_col(cols, 'new-to-brand', 'sales') or find_col(cols, 'new to brand', 'sales') or find_col(cols, 'ntb', 'sales')
                if not (c_date and c_camp and c_ntbo and c_ntbs):
                    print(f'{path}: cannot find columns (date={c_date}, campaign={c_camp}, ntb orders={c_ntbo}, ntb sales={c_ntbs}). Columns: {cols}')
                    sys.exit(2)
                first = False
            d = to_date(r.get(c_date))
            if d is None or d < mon or d > we:
                continue
            seen_dates.add(d)
            tab, prod = route(r.get(c_camp), r.get(c_acct) if c_acct else '', r.get(c_mkt) if c_mkt else '')
            o, s_ = num(r.get(c_ntbo)), num(r.get(c_ntbs))
            if tab is None:
                unmatched.append([r.get(c_camp), r.get(c_acct) if c_acct else '', o, s_]); continue
            totals[(tab, '_TOTAL_')][0] += o; totals[(tab, '_TOTAL_')][1] += s_
            if c_spend:
                spend[tab] += num(r.get(c_spend))
            if prod:
                totals[(tab, prod)][0] += o; totals[(tab, prod)][1] += s_
            elif o or s_:
                unmatched.append([r.get(c_camp), tab, o, s_])
    with open(os.path.join(out_dir, 'ntb.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['tab', 'product', 'ntb_orders', 'ntb_sales'])
        for (tab, prod), (o, s_) in sorted(totals.items()):
            w.writerow([tab, prod, int(round(o)), round(s_, 2)])
    with open(os.path.join(out_dir, 'ntb_spend_check.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['tab', 'report_spend_in_week']); [w.writerow([t, round(v, 2)]) for t, v in sorted(spend.items())]
    if unmatched:
        agg = defaultdict(lambda: [0.0, 0.0])
        for c, t, o, s_ in unmatched:
            agg[(c, t)][0] += o; agg[(c, t)][1] += s_
        unmatched = [[c, t, int(round(v[0])), round(v[1], 2)] for (c, t), v in sorted(agg.items()) if v[0] or v[1]]
        with open(os.path.join(out_dir, 'ntb_unmatched.csv'), 'w', newline='') as fh:
            w = csv.writer(fh); w.writerow(['campaign', 'account_or_tab', 'ntb_orders', 'ntb_sales']); w.writerows(unmatched)
    days = sorted(seen_dates)
    print(f"{week}: {len(days)} days in window ({days[0] if days else '-'} to {days[-1] if days else '-'}), tabs {sorted({t for t, _ in totals})}, campaigns with NTB but no product: {len(unmatched)} (see ntb_unmatched.csv; their NTB is in the tab total)")
    if days and len(days) < 7:
        print('WARNING: fewer than 7 days inside the week. Check the report period.')


if __name__ == '__main__':
    main()
