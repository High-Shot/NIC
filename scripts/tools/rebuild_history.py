#!/usr/bin/env python3
"""
One-time QA fix (2026-09-24): replace account-level metrics in the weeks backfilled from the old Google Sheet
(data/weeks/*.json with generated_at 'backfill...') with the API sources the live pipeline uses, so history
lines up with the current weeks.

Sources (saved under data/qa/):
  si_trend_<MKT>.csv     Scale Insights get_sales_trend, 7-day Mon-Sun cycles: sales, units, sessions, ppcCost, ppcSales
  h10_trend_<TAB>.csv    Helium10 account P&L weekly series: sales (or gross_revenue for SA), units, sessions, ad_cost, ads_acos
Rules
  CC tabs: revenue, units, sessions, ad spend, ad sales <- Scale Insights. CC_AUS only from 2026-05-11 (SI starts then).
  CL_US / PP_US / CC_SA: revenue, units, sessions <- Helium10. Ad spend <- Helium10. Ad sales keep the sheet value
    (it came from the real ad report) unless the sheet spend was broken (>10% off Helium10); then spend/ACoS.
  Weeks where the source has no data keep the sheet values. NTB is not touched (no API source for history).
  Products: each additive metric is scaled by new/old account ratio when 0.25 <= ratio <= 4. If revenue or spend
    cannot be scaled (old account 0 or ratio out of range) the product blocks are dropped for that week (account level only).
    If only sessions cannot be scaled, product sessions are re-split by product units share (flagged as estimated).
Writes data/qa/history_rebuild_log.csv with before/after per tab-week.
"""
import csv, glob, json, os, sys, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import normalize as N

ACC = {a['tab']: a for a in json.load(open(os.path.join(ROOT, 'config', 'accounts.json')))}
QA = os.path.join(ROOT, 'data', 'qa')
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

src = {}   # (tab, WE date) -> dict
for a in ACC.values():
    if a['source'] == 'si' and a.get('si_country'):
        p = os.path.join(QA, f"si_trend_{a['si_country']}.csv")
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p)):
            if a['tab'] == 'CC_AUS' and r['start'] < '2026-05-11': continue
            we = (dt.date.fromisoformat(r['start']) + dt.timedelta(days=6)).isoformat()
            src[(a['tab'], we)] = dict(revenue=f(r['sales']), units=f(r['units']), sessions=f(r['sessions']),
                                       adSpend=f(r['ppcCost']), adSales=f(r['ppcSales']), kind='si')
for tab in ('CL_US', 'PP_US', 'CC_SA'):
    p = os.path.join(QA, f'h10_trend_{tab}.csv')
    if not os.path.exists(p): continue
    for r in csv.DictReader(open(p)):
        we = (dt.date.fromisoformat(r['start']) + dt.timedelta(days=6)).isoformat()
        acos = f(r['ads_acos'])
        src[(tab, we)] = dict(revenue=f(r['sales']), units=f(r['units']), sessions=f(r['sessions']),
                              adSpend=f(r['ad_cost']), adSales=(f(r['ad_cost']) / (acos / 100) if acos > 0 else 0), kind='h10')

KEYS = ('revenue', 'units', 'sessions', 'adSpend', 'adSales')
log = []
for path in sorted(glob.glob(os.path.join(ROOT, 'data', 'weeks', 'WE_*.json'))):
    w = json.load(open(path))
    if not str(w.get('generated_at', '')).startswith('backfill'):
        continue
    we = w['we']; changed = False
    for tab in [t for t in ACC if not ACC[t].get('archived')]:
        s = src.get((tab, we))
        if not s or (s['revenue'] <= 0 and s['adSpend'] <= 0):
            continue
        m = w['markets'].get(tab)
        if m is None:
            m = {'acct': N.blank_acct(), 'products': [], 'flags': [], 'source': 'sheet'}
            w['markets'][tab] = m
            if tab in w.get('missing', []): w['missing'].remove(tab)
        a = m['acct']
        old = {k: f(a.get(k)) for k in KEYS}
        new = dict(old)
        new.update(revenue=s['revenue'], units=s['units'], sessions=s['sessions'], adSpend=s['adSpend'])
        if s['kind'] == 'si':
            new['adSales'] = s['adSales']
        else:
            broken = old['adSpend'] <= 0 or abs(old['adSpend'] / s['adSpend'] - 1) > 0.10 if s['adSpend'] else False
            if broken or old['adSales'] <= 0:
                new['adSales'] = s['adSales']
        if all(abs(new[k] - old[k]) <= max(0.5, abs(old[k]) * 0.002) for k in KEYS):
            continue
        changed = True
        ratio = {k: (new[k] / old[k] if old[k] > 0 else None) for k in KEYS}
        ok = {k: (ratio[k] is not None and 0.25 <= ratio[k] <= 4) or (new[k] == 0 and old[k] == 0) for k in KEYS}
        prods = m.get('products') or []
        note = ''
        if prods and not (ok['revenue'] and ok['adSpend']):
            prods = []; note = 'product blocks dropped (sheet product data unusable this week)'
        else:
            for p in prods:
                for k in KEYS:
                    if ok[k] and ratio[k] is not None:
                        p[k] = (p.get(k) or 0) * ratio[k]
            if prods and not ok['sessions'] and new['sessions'] > 0:
                tu = sum(p.get('units') or 0 for p in prods) or 1
                for p in prods: p['sessions'] = new['sessions'] * (p.get('units') or 0) / tu
                note = 'product sessions estimated from unit share'
        a.update({k: new[k] for k in KEYS}); a['orders'] = a['units']
        N.finish_acct(a)
        m['products'] = N.finish_products(prods) if prods else []
        src_name = 'Scale Insights' if s['kind'] == 'si' else 'Helium10'
        m['flags'] = [x for x in m.get('flags', []) if not x.startswith('History rebuilt')] + [
            f"History rebuilt 2026-09-24: revenue, units, sessions and ad totals from {src_name} (old sheet values were off){'; ' + note if note else ''}"]
        m['source'] = f"sheet+{s['kind']}"
        log.append([we, tab] + [round(old[k], 2) for k in KEYS] + [round(new[k], 2) for k in KEYS] + [note])
    if changed:
        with open(path, 'w') as fh: json.dump(w, fh, indent=1, ensure_ascii=False)
with open(os.path.join(QA, 'history_rebuild_log.csv'), 'w', newline='') as fh:
    wr = csv.writer(fh); wr.writerow(['we', 'tab'] + [f'old_{k}' for k in KEYS] + [f'new_{k}' for k in KEYS] + ['note']); wr.writerows(log)
print(f'rebuilt {len(log)} tab-weeks; log -> data/qa/history_rebuild_log.csv')
