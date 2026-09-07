# NIC Industries — Weekly Performance Dashboard

A weekly Amazon KPI dashboard for NIC Industries brands (Cerakote Ceramics,
Cerakote Legacy, Prismatic Powders) across US and international marketplaces.
The dashboard is a single static HTML file served as a static site; there is no
server or runtime data fetch.

## What actually ships (the live setup)

This repo currently has **two** HTML files plus one orphaned script. Only one
file is the live dashboard. Here is what each is:

| Path | Role |
| --- | --- |
| `index.html` (repo root, ~590 KB) | **The live dashboard.** A fully populated, self-contained page. Its data is embedded inline as JavaScript — `var MKT_META = {…}` and `var WEEKS = [{…}]` near the top of the `<script>` block (`var DATA_WEEKS` is derived from `WEEKS` at runtime). No `fetch`, no `data.json` — the numbers are baked into the file. |
| `NIC/NIC_Dashboard_Template.html` (~40 KB) | **The template `index.html` is derived from.** Same layout, styles, and rendering code, but with an empty data section. At line ~172 it carries the placeholder the build step replaces: `// DATA — Auto-injected by exportDashboard() in Apps Script` followed by `/*__DASHBOARD_DATA__*/`. The live `index.html` is this template with that placeholder swapped for the real `MKT_META` + `WEEKS` payload. |
| `NIC/index.html` (~700 B) | A "Coming soon" placeholder stub. **Not** the live dashboard and not part of the live pipeline. |
| `NIC/scripts/build_dashboard.py` | An **orphaned / non-reproducing** Python script — see the gap below. |

## How the live dashboard is built (as far as this repo shows)

The template placeholder names the real builder: a **Google Apps Script
function `exportDashboard()`** that lives in the Google Sheet tracker, not in
this repository. That function reads the weekly tracker tabs, assembles the
`MKT_META` + `WEEKS` data, injects it into `NIC_Dashboard_Template.html` in
place of `/*__DASHBOARD_DATA__*/`, and the resulting file is committed as the
root `index.html`.

## Known gap / TODO

**The production build step is not committed to, or reproducible from, this
repo.** Specifically:

- The Apps Script `exportDashboard()` that actually generates the live
  `index.html` is not in this repository — it is stored inside the Google
  Sheet. Nothing here lets you regenerate `index.html` from source.
  **TODO:** export the Apps Script source and commit it (e.g. under
  `NIC/scripts/` or an `apps-script/` directory) so the build is reproducible.
- `NIC/scripts/build_dashboard.py` is **not** that builder. It is a separate,
  abandoned Python approach that emits an **incompatible** output: it renders
  its own inline `HTML_TEMPLATE` with a `const DATA = {…}` blob and writes a
  `data.json`, none of which matches the live `MKT_META` / `WEEKS` schema. It
  does not produce, and cannot reproduce, the live dashboard. It is kept only
  for reference. **TODO:** either finish and wire it up to emit the live schema,
  or remove it.
- Despite `build_dashboard.py`'s original docstring, there is **no** GitHub
  Actions workflow in this repo and no automated weekly build. Updates are
  produced manually via the Apps Script and committed by hand (see the single
  `Update dashboard — WE 1/3` commit). **TODO:** add a real CI workflow if
  automation is desired.

## Running `build_dashboard.py` (reference only)

If you want to experiment with the orphaned Python script (it will **not**
reproduce the live dashboard), install its dependencies and provide a Google
service-account credential:

```bash
pip install -r requirements.txt
export GOOGLE_SHEET_ID=<the tracker sheet id>
export GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
python NIC/scripts/build_dashboard.py
```

Never commit the service-account JSON — see `.gitignore`.

## Repository layout note

The `NIC/` subdirectory nests the template, the stub `index.html`, and the
`scripts/` folder one level below the live root `index.html`. This layout is
left as-is; flattening it is a recommended follow-up but is intentionally not
changed here.
