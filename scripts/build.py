#!/usr/bin/env python3
"""
NIC weekly tracker: data/weeks/*.json -> index.html
Injects MKT_META (from config/accounts.json), MKT_KEYS and WEEKS (newest first) into template.html.
Usage: python3 scripts/build.py [--max-weeks 52]
"""
import json, os, glob, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_WEEKS = int(sys.argv[sys.argv.index('--max-weeks') + 1]) if '--max-weeks' in sys.argv else 52
ACCOUNTS = json.load(open(os.path.join(ROOT, 'config', 'accounts.json')))
FX = json.load(open(os.path.join(ROOT, 'config', 'fx.json')))


PROD_KEYS = ('name', 'revenue', 'units', 'sessions', 'pageviews', 'cvr', 'adSpend', 'adSales', 'organic', 'acos', 'tacos', 'roas',
             'ntbOrders', 'ntbSales', 'ntbPct', 'bsr', 'status', 'subcategory', 'subcategoryBSR', 'categoryBSR')


def slim(p):
    return {k: p.get(k) for k in PROD_KEYS}


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def main():
    files = sorted(glob.glob(os.path.join(ROOT, 'data', 'weeks', 'WE_*.json')))[-MAX_WEEKS:]
    weeks = []
    for p in reversed(files):
        w = json.load(open(p))
        weeks.append({'id': w['id'], 'label': w['label'], 'range': w['range'], 'fullLabel': w['fullLabel'], 'we': w['we'],
                      'markets': {t: {'acct': m['acct'], 'products': [slim(p) for p in m['products']], 'flags': m['flags'], 'source': m.get('source')}
                                  for t, m in w['markets'].items()}})
    meta = {'GLOBAL': {'name': 'Global (All Markets)', 'currency': '', 'flag': ''}}
    for a in ACCOUNTS:
        meta[a['tab']] = {'name': a['name'], 'currency': a['currency'], 'flag': a['market'], 'label': a['label'], 'code': a['code']}
    # archived tabs (config/accounts.json "archived": date) stay in data/weeks and MKT_META but leave the nav and GLOBAL
    keys = ['GLOBAL'] + [a['tab'] for a in ACCOUNTS if not a.get('archived')]
    archived = {a['tab'] for a in ACCOUNTS if a.get('archived')}
    for w in weeks:
        for t in archived:
            w['markets'].pop(t, None)
    tpl = open(os.path.join(ROOT, 'template.html'), encoding='utf-8').read()
    fx = {k: v for k, v in FX.items() if not k.startswith('_')}
    html = tpl.replace('/*__MKT_META__*/', js(meta)).replace('/*__MKT_KEYS__*/', js(keys)).replace('/*__FX__*/', js(fx)).replace('/*__WEEKS__*/', js(weeks))
    out = os.path.join(ROOT, 'index.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f'built index.html: {len(weeks)} weeks ({weeks[-1]["label"]} to {weeks[0]["label"]}), {len(html)//1024} KB')


if __name__ == '__main__':
    main()
