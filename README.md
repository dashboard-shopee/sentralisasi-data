# Sentralisasi Data — Shopee Multi-Toko

Menyatukan data dari 3 program otomasi Shopee ke **satu database SQL** (Supabase /
PostgreSQL), lalu menampilkannya di **dashboard** ala Shopee Seller untuk 10 toko.

## Visi arsitektur

```
SEKARANG (Fase 1):  Google Sheets ──ETL Python──► Supabase (SQL) ──► Dashboard
NANTI   (Fase 2):   Program otomasi ──tulis langsung──► Supabase   ──► Dashboard
                    (Google Sheets dipensiunkan)
```

SQL jadi **satu sumber kebenaran**. Sheets cuma jembatan sementara.

## Sumber data

| Program | Folder | Sheet | Tabel tujuan |
|---|---|---|---|
| Iklan | `01 Otomatisasi Iklan` | `1g8w73…` | `fact_iklan`, `fact_penjualan` |
| Harga | `02 Otomatisasi Monitoring Harga` | `1DQpoW…` | `fact_harga` |
| Kompetitor | `03 Otomatisasi Riset Kompetitor` | `1dwFyt…` | `fact_kompetitor` |

10 toko = dimensi bersama (`dim_toko`).

## Struktur project

```
config/        koneksi DB + Sheets (baca dari .env)
db/            schema.sql — definisi tabel
etl/           extract (Sheets) → transform → load (Postgres)
dashboard/     app.py — dashboard Streamlit
scripts/       utilitas sekali jalan (setup_db, seed_toko, dll)
data/raw/      cache CSV mentah (gitignored)
```

## Setup

```powershell
pip install -r requirements.txt
copy .env.example .env      # lalu isi DATABASE_URL + kredensial Google
python scripts/setup_db.py  # buat tabel di Supabase
python -m etl.run           # tarik Sheets -> SQL
streamlit run dashboard/app.py
```

## Status

- [x] Skema SQL draft (`db/schema.sql`)
- [x] Kerangka project
- [ ] Buat project Supabase + isi `.env`
- [ ] ETL per sumber
- [ ] Dashboard
