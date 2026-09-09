#!/usr/bin/env python3
"""tool-results dump of get_campaign_performance -> si_campaigns_<MKT>.csv"""
import json, sys, csv, re
src, mkt, dst = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(src).read()
try:
    d = json.loads(raw)
    if isinstance(d, list): d = json.JSONDecoder().raw_decode(d[0]['text'])[0]
except json.JSONDecodeError:
    d = json.JSONDecoder().raw_decode(raw)[0]
def num(s):
    if s is None: return 0
    return float(re.sub(r'[^0-9.\-]', '', str(s)) or 0)
w = csv.writer(open(dst, 'w', newline=''))
w.writerow(['market','campaign','ad_type','state','spend','sales','orders'])
agg = d.get('agg', {})
w.writerow([mkt,'_TOTAL_','','',num(agg.get('TotalSpend')),num(agg.get('TotalAdSales')),num(agg.get('TotalOrders'))])
n=0
for o in d.get('opps', []):
    m = o.get('metrics', {})
    w.writerow([mkt,o['entity'],m.get('AdType'),m.get('State'),num(m.get('Spend')),num(m.get('Sales')),num(m.get('Orders'))]); n+=1
om = d.get('oppMeta', {})
print(dst, 'rows', n, 'of', om.get('total_count'), 'has_next', om.get('has_next_page'), 'total spend', agg.get('TotalSpend'))
