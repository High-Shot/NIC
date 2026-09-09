#!/usr/bin/env python3
"""Refresh config/fx.json from open.er-api.com (USD base). Keeps the old file on any failure."""
import json, os, sys, urllib.request, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'config', 'fx.json')
try:
    d = json.load(urllib.request.urlopen('https://open.er-api.com/v6/latest/USD', timeout=20))
    r = d['rates']
    fx = json.load(open(P))
    for c in ('CAD', 'GBP', 'EUR', 'AUD', 'SAR', 'MXN'):
        fx[c] = round(float(r[c]), 6)
    fx['as_of'] = dt.datetime.utcnow().strftime('%Y-%m-%d')
    json.dump(fx, open(P, 'w'), indent=1)
    print('fx updated', fx['as_of'], {c: fx[c] for c in ('CAD', 'GBP', 'EUR', 'AUD', 'SAR', 'MXN')})
except Exception as e:
    print('fx update failed, keeping previous rates:', e); sys.exit(0)
