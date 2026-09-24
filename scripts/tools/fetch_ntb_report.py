#!/usr/bin/env python3
"""
Download the scheduled Reports Beta master report from its Amazon Ads email.

The email ("Your report is ready: NIC Weekly Tracker - Master Ad Report - 30", from no-reply@ads.amazon.com)
has NO attachment. It carries a pre-signed S3 link that expires 48 hours after the email is sent.
This script pulls that link out of the email HTML, unwraps Amazon's click-tracking redirect, and downloads the CSV.

Usage: python3 scripts/tools/fetch_ntb_report.py <email_html_file> [dest_dir=inbox]
<email_html_file> = the htmlBody of mcp__Gmail__get_message (FULL_CONTENT) saved to a file (a JSON dump of the
whole message also works). Prints the saved path. Exit 2 if no link, 3 if the link has expired or the download fails.
"""
import html, json, os, re, sys, urllib.parse, urllib.request

src = open(sys.argv[1], encoding='utf-8').read()
dest_dir = sys.argv[2] if len(sys.argv) > 2 else 'inbox'
try:
    src = json.loads(src).get('htmlBody', src)
except Exception:
    pass
src = html.unescape(src)

m = re.search(r'https://[^"\s]*?decorated-reports[^"\s]*', src)
if not m:
    sys.exit('no report link found in the email (expected a decorated-reports S3 link)') or 2
link = m.group(0)
# Tracking wrapper: https://na.r.ads.amazon.com/CL0/<url-encoded target>/<n>/<id>/<token>=452
inner = re.search(r'/CL0/(https:%2F%2F[^/]+)/', link)  # the encoded target has no literal slashes
target = urllib.parse.unquote(inner.group(1)) if inner else link

name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(target).path)) or 'master_ad_report.csv'
date = re.search(r'X-Amz-Date=(\d{8})', target)
stem, ext = os.path.splitext(name)
out = os.path.join(dest_dir, f"{stem}_{date.group(1) if date else 'latest'}{ext}".replace(' ', '_'))
os.makedirs(dest_dir, exist_ok=True)
try:
    with urllib.request.urlopen(target, timeout=120) as r, open(out, 'wb') as fh:
        fh.write(r.read())
except Exception as e:
    print(f'download failed ({e}); the S3 link expires 48h after the email. Re-run the report in Reports Beta.', file=sys.stderr)
    sys.exit(3)
if os.path.getsize(out) < 1000:
    sys.exit(f'downloaded file is suspiciously small: {out}') or 3
print(out)
