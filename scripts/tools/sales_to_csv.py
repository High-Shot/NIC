#!/usr/bin/env python3
import json, sys, csv
src, mkt, dst = sys.argv[1], sys.argv[2], sys.argv[3]
raw=open(src).read()
try:
    d=json.loads(raw)
    if isinstance(d,list): d=json.JSONDecoder().raw_decode(d[0]['text'])[0]
except json.JSONDecodeError:
    d=json.JSONDecoder().raw_decode(raw)[0]
w=csv.writer(open(dst,'w',newline=''))
w.writerow(['market','asin','sku','title','sales','units','orders','ppc_cost','ppc_sales','sessions'])
s=d['Summary']
w.writerow([mkt,'_TOTAL_','','',s['TotalSales'],s['TotalUnits'],s['TotalOrders'],s['TotalPPCCost'],s['TotalPPCSales'],s['TotalSessions']])
for a in d['ASINs']:
    w.writerow([mkt,a['ASIN'],a['SKU'] or '',(a['Title'] or '')[:80],a['TotalSales'],a['TotalUnits'],a['TotalOrders'],a['TotalPPCCost'],a['TotalPPCSales'],a['TotalSessions']])
print(dst, len(d['ASINs']), 'asins; total sales', s['TotalSales'], 'sessions', s['TotalSessions'])
