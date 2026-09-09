#!/usr/bin/env python3
"""
NIC weekly tracker: raw pulls -> data/weeks/WE_<date>.json

Reads  data/raw/WE_<YYYY-MM-DD>/
  si_sales_<MKT>.csv      Scale Insights get_sales_data, one row per ASIN plus _TOTAL_   (CC markets)
  si_campaigns_<MKT>.csv  Scale Insights get_campaign_performance totals (_TOTAL_ row; SB rows optional)
  si_bsr_<MKT>.csv        Scale Insights get_bsr_data, main ASIN per product              (optional)
  h10_<TAB>.csv           Helium10 P&L weekly series, _TOTAL_ row plus products             (CL_US, PP_US, CC_SA, CC_MX)
  ntb.csv                 New-to-brand by market and product (from scripts/ingest_ntb.py)  (optional)
Writes data/weeks/WE_<date>.json in the shape the dashboard template reads.

Usage:  python3 scripts/normalize.py WE_2026-09-06
        python3 scripts/normalize.py --backfill sheet_dump.json   (one-time import of the old Google Sheet)
"""
import csv, json, os, sys, re, datetime as dt
from collections import defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS = json.load(open(os.path.join(ROOT, 'config', 'accounts.json')))
DM = json.load(open(os.path.join(ROOT, 'config', 'data_map.json')))
PRODUCTS = DM['products']
A2P = DM['asin_to_product']
KPI = DM['kpi']
ACC = {a['tab']: a for a in ACCOUNTS}
TABS = [a['tab'] for a in ACCOUNTS]


def f(v, d=0.0):
    try:
        return float(v) if v not in (None, '') else d
    except (TypeError, ValueError):
        return d


def r2(x):
    return round(x + 0.0, 2)


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def week_meta(we):
    """we = datetime.date of the Sunday. Returns id/label/range/fullLabel matching the old Apps Script export."""
    mon = we - dt.timedelta(days=6)
    return {
        'we': we.isoformat(),
        'id': f"WE_{we.month:02d}{we.day:02d}",
        'label': f"WE {we.month}/{we.day}",
        'range': f"{mon.month}/{mon.day} – {we.month}/{we.day}",
        'fullLabel': f"Week Ending Sun {we.strftime('%B')} {we.day}, {we.year}",
    }


def derive(d):
    """Fill cvr/acos/tacos/roas/organic/ntbPct from the base metrics. Percentages are 0-100."""
    d['cvr'] = r2(d['units'] / d['sessions'] * 100) if d.get('sessions') else 0
    d['acos'] = r2(d['adSpend'] / d['adSales'] * 100) if d.get('adSales') else 0
    d['tacos'] = r2(d['adSpend'] / d['revenue'] * 100) if d.get('revenue') else 0
    d['roas'] = r2(d['adSales'] / d['adSpend']) if d.get('adSpend') else 0
    d['ntbPct'] = r2(d['ntbOrders'] / d['units'] * 100) if d.get('units') else 0
    return d


def status_of(p):
    if p['acos'] > KPI['acos_crit'] or p['tacos'] > KPI['tacos_crit']:
        return 'crit'
    if p['tacos'] > KPI['tacos_warn']:
        return 'warn'
    return 'ok'


def blank_acct():
    return {'revenue': 0, 'units': 0, 'orders': 0, 'sessions': 0, 'pageviews': 0, 'adSpend': 0, 'adSales': 0,
            'organicSales': 0, 'ntbOrders': 0, 'ntbSales': 0}


def blank_prod(name):
    return {'name': name, 'asins': [], 'revenue': 0, 'units': 0, 'orders': 0, 'sessions': 0, 'pageviews': 0,
            'adSpend': 0, 'adSales': 0, 'organic': 0, 'ntbOrders': 0, 'ntbSales': 0,
            'bsr': '', 'categoryBSR': None, 'subcategory': None, 'subcategoryBSR': None}


def finish_products(prods):
    out = []
    for p in prods:
        p['organic'] = r2(p['revenue'] - p['adSales'])
        p['organicSales'] = p['organic']
        for k in ('revenue', 'adSpend', 'adSales', 'ntbSales'):
            p[k] = r2(p[k])
        derive(p)
        p['status'] = status_of(p)
        out.append(p)
    return out


def finish_acct(a):
    a['organicSales'] = r2(a['revenue'] - a['adSales'])
    for k in ('revenue', 'adSpend', 'adSales', 'ntbSales'):
        a[k] = r2(a[k])
    return derive(a)


def apply_ntb(tab, acct, prods, ntb_rows):
    for r in ntb_rows:
        if r['tab'] != tab:
            continue
        if r['product'] == '_TOTAL_':
            acct['ntbOrders'] += f(r['ntb_orders'])
            acct['ntbSales'] += f(r['ntb_sales'])
        else:
            for p in prods:
                if p['name'] == r['product']:
                    p['ntbOrders'] += f(r['ntb_orders'])
                    p['ntbSales'] += f(r['ntb_sales'])
    if acct['ntbOrders'] == 0 and any(r['tab'] == tab for r in ntb_rows):
        acct['ntbOrders'] = sum(p['ntbOrders'] for p in prods)
        acct['ntbSales'] = sum(p['ntbSales'] for p in prods)


# ---------------------------------------------------------------- Scale Insights tabs
def build_si(tab, week_dir, ntb_rows):
    a = ACC[tab]
    mkt = a['si_country']
    sales = read_csv(os.path.join(week_dir, f'si_sales_{mkt}.csv'))
    camps = read_csv(os.path.join(week_dir, f'si_campaigns_{mkt}.csv'))
    bsr = read_csv(os.path.join(week_dir, f'si_bsr_{mkt}.csv'))
    flags = []
    if not sales:
        return None, [f'{tab}: no Scale Insights sales file']
    acct = blank_acct()
    prods = OrderedDict((n, blank_prod(n)) for n in PRODUCTS)
    other = defaultdict(lambda: {'revenue': 0, 'units': 0, 'asins': []})
    attributed_spend = attributed_sales = 0
    for r in sales:
        if r['asin'] == '_TOTAL_':
            acct['revenue'] = f(r['sales']); acct['units'] = f(r['units']); acct['orders'] = f(r['orders'])
            acct['sessions'] = f(r['sessions'])
            continue
        name = A2P.get(r['asin'])
        attributed_spend += f(r['ppc_cost']); attributed_sales += f(r['ppc_sales'])
        if name in prods:
            p = prods[name]
            p['asins'].append(r['asin'])
            p['revenue'] += f(r['sales']); p['units'] += f(r['units']); p['orders'] += f(r['orders'])
            p['sessions'] += f(r['sessions']); p['adSpend'] += f(r['ppc_cost']); p['adSales'] += f(r['ppc_sales'])
        else:
            key = name or f'UNMAPPED {r["asin"]}'
            o = other[key]
            o['revenue'] += f(r['sales']); o['units'] += f(r['units']); o['asins'].append(r['asin'])
            if not name and (f(r['sales']) > 0 or f(r['ppc_cost']) > 0):
                flags.append(f"Unmapped ASIN {r['asin']} ({(r.get('title') or '')[:40]}): {a['currency']}{f(r['sales']):,.2f} revenue, {a['currency']}{f(r['ppc_cost']):,.2f} spend. Add to config/data_map.json")
    for key, o in other.items():
        if key.startswith('OTHER:') and o['revenue'] > 0:
            flags.append(f"{key[7:]}: {a['currency']}{o['revenue']:,.2f} in account total, no product block ({', '.join(o['asins'])})")
    # account ad totals from the campaign pull (all types); product level is ASIN-attributed plus a pro-rata share of the remainder
    tot = next((r for r in camps if r['campaign'] == '_TOTAL_'), None)
    if tot:
        acct['adSpend'] = f(tot['spend']); acct['adSales'] = f(tot['sales'])
    else:
        acct['adSpend'] = attributed_spend; acct['adSales'] = attributed_sales
        flags.append(f'{tab}: no campaign totals file, account ad totals = ASIN-attributed sum')
    gap_spend = acct['adSpend'] - attributed_spend
    gap_sales = acct['adSales'] - attributed_sales
    mapped_spend = sum(p['adSpend'] for p in prods.values())
    mapped_sales = sum(p['adSales'] for p in prods.values())
    if abs(gap_spend) > 0.5 and mapped_spend > 0:
        for p in prods.values():
            p['adSpend'] += gap_spend * p['adSpend'] / mapped_spend
            if mapped_sales > 0:
                p['adSales'] += gap_sales * p['adSales'] / mapped_sales
        flags.append(f"Ad spend not attributed to an ASIN by Scale Insights (multi-ASIN SB/SD campaigns): {a['currency']}{gap_spend:,.2f} ({gap_spend / acct['adSpend'] * 100:.1f}% of spend), allocated to products pro rata")
    # BSR: best main-category rank among the product's ASINs
    by_asin = {r['asin']: r for r in bsr}
    for p in prods.values():
        cands = [by_asin[x] for x in p['asins'] if x in by_asin] or [by_asin[x] for x in by_asin if A2P.get(x) == p['name']]
        if cands:
            best = min(cands, key=lambda r: f(r['category_rank'], 9e9))
            p['categoryBSR'] = int(f(best['category_rank'])); p['bsr'] = str(p['categoryBSR'])
            p['subcategory'] = best.get('subcategory') or None
            p['subcategoryBSR'] = int(f(best['subcategory_rank'])) if best.get('subcategory_rank') else None
    prod_list = list(prods.values())
    apply_ntb(tab, acct, prod_list, ntb_rows)
    prod_list = finish_products(prod_list)
    acct = finish_acct(acct)
    psum = sum(p['revenue'] for p in prod_list)
    if acct['revenue'] and abs(acct['revenue'] - psum) / acct['revenue'] > 0.02:
        flags.append(f"Product revenue sums to {a['currency']}{psum:,.2f} vs account {a['currency']}{acct['revenue']:,.2f} ({(acct['revenue'] - psum) / acct['revenue'] * 100:.1f}% outside product blocks)")
    return {'acct': acct, 'products': prod_list, 'flags': flags, 'source': 'scale_insights'}, flags


# ---------------------------------------------------------------- Helium10 tabs
def build_h10(tab, week_dir, ntb_rows):
    a = ACC[tab]
    rows = read_csv(os.path.join(week_dir, f'h10_{tab}.csv'))
    bsr = read_csv(os.path.join(week_dir, f'h10_bsr_{tab}.csv'))
    if not rows:
        return None, [f'{tab}: no Helium10 file']
    rev_field = a.get('h10_revenue_field', 'sales')
    flags = []

    def ad_sales_of(r):
        c, acos = f(r['ad_cost']), f(r['ads_acos'])
        return c / (acos / 100) if acos > 0 and c > 0 else 0

    acct = blank_acct()
    prods = []
    dyn = DM['dynamic_product_tabs'].get(tab)
    for r in rows:
        if r['asin'] == '_TOTAL_':
            acct.update(revenue=f(r[rev_field]), units=f(r['units']), orders=f(r['units']), sessions=f(r['sessions']),
                        adSpend=f(r['ad_cost']), adSales=ad_sales_of(r))
            continue
        name = r['name'] if dyn else A2P.get(r['asin'], f"UNMAPPED {r['asin']}")
        p = next((x for x in prods if x['name'] == name), None)
        if p is None:
            p = blank_prod(name); prods.append(p)
        p['asins'].append(r['asin'])
        p['revenue'] += f(r[rev_field]); p['units'] += f(r['units']); p['orders'] += f(r['units'])
        p['sessions'] += f(r['sessions']); p['adSpend'] += f(r['ad_cost']); p['adSales'] += ad_sales_of(r)
    if dyn:
        prods.sort(key=lambda p: -p['revenue'])
        prods = prods[:dyn['n']]
    else:
        order = {n: i for i, n in enumerate(PRODUCTS)}
        keep = [p for p in prods if p['name'] in order]
        for p in prods:
            if p['name'] not in order and p['revenue'] > 0:
                flags.append(f"{p['name']}: {a['currency']}{p['revenue']:,.2f} in account total, no product block")
        keep.sort(key=lambda p: order[p['name']])
        for n in PRODUCTS:
            if n not in [p['name'] for p in keep]:
                keep.append(blank_prod(n))
        keep.sort(key=lambda p: order[p['name']])
        prods = keep
    by_asin = {r['asin']: r for r in bsr}
    for p in prods:
        c = [by_asin[x] for x in p['asins'] if x in by_asin]
        if c:
            best = min(c, key=lambda r: f(r['category_rank'], 9e9))
            p['categoryBSR'] = int(f(best['category_rank'])); p['bsr'] = str(p['categoryBSR'])
            p['subcategory'] = best.get('subcategory') or None
            p['subcategoryBSR'] = int(f(best['subcategory_rank'])) if best.get('subcategory_rank') else None
    apply_ntb(tab, acct, prods, ntb_rows)
    prods = finish_products(prods)
    acct = finish_acct(acct)
    if acct['adSpend'] and not acct['adSales']:
        flags.append(f'{tab}: Helium10 reports spend but no attributed ad sales this week')
    flags.append(f'{tab}: ad sales derived from Helium10 ACoS (spend / ACoS); SB/SD detail not available until the Ads API is connected')
    return {'acct': acct, 'products': prods, 'flags': flags, 'source': 'helium10'}, flags


# ---------------------------------------------------------------- driver
def build_week(week_key):
    we = dt.date.fromisoformat(week_key.replace('WE_', ''))
    week_dir = os.path.join(ROOT, 'data', 'raw', week_key)
    ntb_rows = read_csv(os.path.join(week_dir, 'ntb.csv'))
    out = week_meta(we)
    out['generated_at'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out['markets'] = {}
    out['missing'] = []
    for tab in TABS:
        a = ACC[tab]
        m, flags = (build_si if a['source'] == 'si' else build_h10)(tab, week_dir, ntb_rows)
        if m is None:
            out['missing'].append(tab)
            continue
        if not ntb_rows:
            m['flags'].append('NTB not loaded for this week (drop the Reports Beta master report in inbox/)')
        out['markets'][tab] = m
    return out


def write_week(out):
    os.makedirs(os.path.join(ROOT, 'data', 'weeks'), exist_ok=True)
    path = os.path.join(ROOT, 'data', 'weeks', f"WE_{out['we']}.json")
    with open(path, 'w') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return path


# ---------------------------------------------------------------- one-time sheet backfill
def backfill(dump_path):
    """sheet_dump.json: {tab: {weeks:[labels], acct:{metric:{label:val}}, products:[[name, {metric:{label:val}}], ...]}}"""
    dump = json.load(open(dump_path))
    labels = dump[TABS[0]]['weeks']
    # WE labels are M/D without a year; the sheet started WE 1/11/2026 and runs forward
    year = 2026
    prev = None
    written = []
    for lab in labels:
        m, d = lab.replace('WE ', '').split('/')
        we = dt.date(year, int(m), int(d))
        if prev and we < prev:
            year += 1; we = dt.date(year, int(m), int(d))
        prev = we
        out = week_meta(we)
        out['generated_at'] = 'backfill from Google Sheet 2026-09-09'
        out['markets'] = {}
        out['missing'] = []
        any_data = False
        for tab in TABS:
            t = dump.get(tab)
            if not t:
                out['missing'].append(tab); continue
            g = lambda blk, k: f(blk.get(k, {}).get(lab))
            acct = blank_acct()
            acct.update(revenue=g(t['acct'], 'revenue'), units=g(t['acct'], 'units'), sessions=g(t['acct'], 'sessions'),
                        pageviews=g(t['acct'], 'pageviews'), adSpend=g(t['acct'], 'adSpend'), adSales=g(t['acct'], 'adSales'),
                        ntbOrders=g(t['acct'], 'ntbOrders'), ntbSales=g(t['acct'], 'ntbSales'))
            acct['orders'] = acct['units']
            if not (acct['revenue'] or acct['adSpend'] or acct['units']):
                continue
            any_data = True
            prods = []
            for name, blk in t['products']:
                if name.upper().startswith('PRODUCT '):
                    continue
                canon = next((n for n in PRODUCTS if n.lower() == name.lower()), name.title())
                p = blank_prod(canon)
                p.update(revenue=g(blk, 'revenue'), units=g(blk, 'units'), sessions=g(blk, 'sessions'), pageviews=g(blk, 'pageviews'),
                         adSpend=g(blk, 'adSpend'), adSales=g(blk, 'adSales'), ntbOrders=g(blk, 'ntbOrders'), ntbSales=g(blk, 'ntbSales'))
                p['orders'] = p['units']
                b = blk.get('bsr', {}).get(lab)
                if b not in (None, '', '—'):
                    try:
                        p['categoryBSR'] = int(float(str(b).replace(',', ''))); p['bsr'] = str(p['categoryBSR'])
                    except ValueError:
                        p['bsr'] = str(b)
                prods.append(p)
            out['markets'][tab] = {'acct': finish_acct(acct), 'products': finish_products(prods), 'flags': [], 'source': 'sheet'}
        if any_data:
            written.append(write_week(out))
    return written


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    if sys.argv[1] == '--backfill':
        paths = backfill(sys.argv[2])
        print(f'backfilled {len(paths)} weeks')
        return
    out = build_week(sys.argv[1])
    path = write_week(out)
    print(f"{out['label']} -> {path}  markets: {len(out['markets'])}  missing: {out['missing'] or 'none'}")
    for tab, m in out['markets'].items():
        a = m['acct']
        print(f"  {tab:7} rev {a['revenue']:>12,.2f}  units {a['units']:>7,.0f}  sess {a['sessions']:>7,.0f}  spend {a['adSpend']:>10,.2f}  adsales {a['adSales']:>11,.2f}  tacos {a['tacos']:5.1f}  flags {len(m['flags'])}")


if __name__ == '__main__':
    main()
