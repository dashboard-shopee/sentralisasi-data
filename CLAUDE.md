# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**SYNTRA** — unifies data from 3 parallel Shopee automation bots (10 sub-shops) into one
Supabase/PostgreSQL database, surfaced through a Next.js dashboard. Indonesian identifiers
throughout (*iklan*=ads, *harga*=price, *penjualan*=sales, *toko*=shop, *produk*=product).

```
Shopee (internal JSON API, session harvested via browser login)
   │  3 independent Python bots — each its own Chrome port, own schedule
   ▼
Supabase PostgreSQL (ap-southeast-1)
   ▼
web/ — Next.js dashboard (Vercel) → https://sentralisasi-data.vercel.app
```

**Full architecture, schema, and schedules:** [`HANDOFF.md`](HANDOFF.md) — read it before non-trivial
changes; it's the source of truth and stays current (unlike `README.md`, which describes an old
Streamlit/Google-Sheets design that has since been replaced — don't trust it).

## Repo layout & git boundary — important

Only **`web/`** and **`Syntra_Monitoring_Harga/`** are tracked by git. Everything else is local-only
(gitignored — holds `.env` / live Shopee sessions):

| Folder | Tracked? | Purpose |
|---|---|---|
| `web/` | ✅ git | Dashboard (Next.js), deployed to Vercel |
| `Syntra_Monitoring_Harga/` | ✅ git | Price-monitoring bot (Chrome port 9556) |
| `Syntra_Iklan/` | ❌ local | ETL (all Shopee data → Supabase) + ad-budget/ROAS bot (port 9560) |
| `Syntra_Riset_Kompetitor/` | ❌ local | Competitor-research scraper (port 9604) — imports `config.db` from `Syntra_Iklan/`, so that folder must sit alongside it |
| `01 Otomatisasi Iklan/`, `02 Otomatisasi Monitoring Harga/` | ❌ local | Legacy reference bots — **do not modify**, kept only as historical/porting reference |
| `04 Purchase Data/` | ❌ local | Scratch ERP purchase-data integration |
| `99. Server/` | ❌ local | Staging mirror of `Syntra_Iklan/` + `Syntra_Riset_Kompetitor/` for server deploy (`robocopy /MIR`) |

Each bot is self-contained (own `.env`, own `db/*.sql` schema file) and shares only the Supabase
database — never assume shared Python state between `Syntra_Iklan/`, `Syntra_Monitoring_Harga/`, and
`Syntra_Riset_Kompetitor/` beyond that DB.

## Commands

### Dashboard (`web/`)
```powershell
cd web
npm install
npm run dev      # localhost:3000, needs web/.env.local (DATABASE_URL, DASH_PASSWORD, SMTP_*)
npm run build
npm run lint
```
No test suite. Deploy is `git push origin main` → Vercel auto-redeploy (Root Directory = `web`,
region `sin1`). **Read `web/AGENTS.md` before touching Next.js code** — this project pins a Next.js
version with breaking API/convention changes vs. training-data assumptions; check
`node_modules/next/dist/docs/` for anything unfamiliar rather than assuming.

### ETL + ad bot (`Syntra_Iklan/`, local only)
```powershell
cd Syntra_Iklan
python -m shopee.session     # one-time login (harvests cookies into __chrome_profile/)
python -m etl.sync           # pull everything since last run (resumable, skips existing periods)
python -m iklan.run test     # one ad-bot cycle now, DRY-RUN by default
python -m iklan.run          # scheduler loop (hourly)
```
No test suite — scripts are run directly. `IKLAN_LIVE=1` env var flips the ad bot from dry-run to
live Shopee writes.

### Price bot (`Syntra_Monitoring_Harga/`)
```powershell
cd Syntra_Monitoring_Harga
python run.py tes            # one cycle now (tes_harga.bat)
python run.py                # scheduler
python run.py fase2          # pricing diagnose+execute, DRY-RUN forced
```
`STATUS.md` (locked spec + progress via symbols) and `PANDUAN_PROGRAM.md` (explanation + owner spec)
are the working docs for this bot — keep them current instead of creating new `.md` files, and don't
invent unconfirmed progress there.

### Competitor scraper (`Syntra_Riset_Kompetitor/`, local only)
```powershell
cd Syntra_Riset_Kompetitor
python SYNTRA_Riset_Kompetitor.py test   # one cycle, oldest-queue priority
python SYNTRA_Riset_Kompetitor.py        # daily scheduler
```

## Architecture notes that require reading multiple files to piece together

- **Session pattern (all 3 bots):** open a real Chrome via DrissionPage just long enough to harvest
  cookies/`sc-fe-session`/URL params from a sniffed login request, close the browser, then do all
  actual work via plain `requests`. Never keep a browser open across an API-heavy pull. Each bot has
  its own Chrome port + profile so all three can run concurrently without colliding.
- **Frozen cycle clock (ad bot):** `iklan/jam_siklus.py` freezes the reference time once per cycle so
  schedule gates (reset/ROAS/report hours) don't drift mid-cycle if a run crosses an hour boundary.
  Data-window math stays on live `datetime.now()` on purpose.
- **Rolling analysis window, not calendar weeks:** `iklan/analisa.py`'s scoring engine always looks at
  a rolling 7-day window (WIB yesterday back 7 days), recomputed fresh regardless of which weekday it
  runs — moving the trigger day (e.g. Monday→Tuesday) doesn't require touching the windowing logic,
  only `iklan/config_iklan.py`'s `HARI_ROAS`/`HARI_ROAS_TAMBAHAN`.
- **`analisa.py` is a SQL port of `01 Otomatisasi Iklan/analisa iklan.js`** (Google Apps Script) — when
  debugging weird scoring output, diff against that source rather than assuming the Python is
  independently correct; several subtle porting bugs (unit mismatches, weight-by-wrong-axis) have been
  found this way.
- **ROAS is a multiplier scale everywhere** (`7` = 7×) — `fact_iklan.roas` and `iklan_setting.target_roas`
  share that scale; only the Shopee API layer (`iklan/aksi.py`) needs `roas * 100000`. Budgets are also
  in Shopee's micro-units (×100000) at the API boundary only.
- **Retention/pruning runs piggybacked on the ad bot's hourly cycle**, not as a separate scheduled job
  (`config/retensi.py` + `config/pruning.py`).
- **`fact_harga` / `fact_kompetitor` tables are legacy/dead** — superseded by `harga_*` (price bot,
  upsert-based) and `riset_*` (competitor bot). Writers for the old tables still exist in
  `Syntra_Iklan/etl/load.py` but nothing calls them; don't resurrect them.
- **Transient Shopee errors need different recovery paths**: `SesiKedaluwarsa`/401/"not login" means the
  harvested session actually died → re-harvest. `code 60001 "data isn't ready"` means Shopee's own data
  warehouse lags → sleep + retry the *same* session, re-harvesting here just wastes a cycle re-switching
  sub-shops for nothing.
- **Vercel dashboard reads `web/.env.local` locally / Vercel env vars in prod** — completely separate
  `.env` from the Python bots' `Syntra_Iklan/.env`; don't assume one `DATABASE_URL` change covers both.
