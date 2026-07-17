# Perbaikan Takedown Fase 2 (Flash/Campaign/Garansi) — Implementation Plan

> **For agentic workers:** implement task-by-task, urut. Repo ini **TIDAK punya test suite** (CLAUDE.md: "scripts are run directly"). Jadi tiap task diverifikasi lewat **probe/DRY-run/bukti-hidup** (pola asli repo), BUKAN pytest. Checkbox (`- [ ]`) buat tracking.

**Goal:** Nyalain takedown per-jam Flash + Campaign + Garansi yang selama ini mati (nerima 0 / executor ga ada), plus benerin bug pencatatan campaign, biar Fase 2 poin 3③④⑤ jalan sesuai STATUS.

## 📐 SPEC KPI CAMPAIGN PASANG (owner, 16 Jul) — buat Task 9 (nyusul)

Verif live 16 Jul: 7 sesi kimmioshop kebagi **3 grup** (per campaign_id). Owner mau bot otomatis daftarin per-grup, **skip bersih** kalau sesi nolak (jangan ninggalin draft nyangkut kayak 978125).

- **A. Eligibility (produk mana dinominasi):** stok > 50 DAN stok > 10×pjh. *(udah ada di provisioning.campaign)*
- **B. Harga campaign yg di-SET (BARU, per DURASI sesi):** `campaign_price = target × faktor`
  - sesi **1 hari** (session_end − session_start ≤ ~1 hari) → **diskon 1,5%** → faktor `0.985`
  - sesi **>1 hari** (mis. umum 26 Jul–9 Aug) → **diskon 0,15%** → faktor `0.9985`
  - deteksi dari DURASI, BUKAN campaign_id (id ganti tiap bulan).
- **C. Stok campaign yg DIAJUKAN (BARU, tiered ~10%):**
  - stok >1000 → ajukan **100** · 501–1000 → **50** · 251–500 → **25** · ≤250 → **5**
- **D. Skip bersih (reaktif):** nominate per sesi; kalau submit gagal (diskon kurang / sesi nolak) → **buang preview draft** biar ga numpuk. Ekspektasi owner: tiap grup ada ≥1 sesi yg keterima.
- **E. Takedown (cabut, terpisah — udah ada):** stok<30 / stok<pjh / harga < target×0.985.

⚠️ **Implementasi (Task 9, belum dikerjain):** `nominate()` skrg pakai `fill_recommend_price` (Shopee yg ngitung harga) + GA set campaign_stock. Buat tegakin B & C, tambah langkah **preview/edit** (set `campaign_price` + `campaign_stock` per nomination_id, kaya alur manual owner di sniff) sebelum submit.

**🔬 TEMUAN INVESTIGASI 16 Jul (selector/verify + draft):**
- `selector/verify` (pre-filter eligibility Shopee) **KENA ANTI-BOT** (`Failed to fetch` via injected call) — sama kaya nominated_entity_list. Pre-filter via endpoint Shopee GA BISA otomatis.
- Kategori kimmioshop mostly aksesoris → cuma **~6 item Home&Living** (kriteria 8.8) dari 222. Campaign 8.8 buat toko ini emang cocoknya dikit (bukan bug).
- **Draft nyangkut BUKAN alur normal**: sniff bukti `preview/add` nolak produk ga-eligible DI SITU (978067: 12 ok/1 gagal), `submit` SELALU 12/12 bersih (0 gagal). Draft nyangkut 978125 = akibat bug Rp0 lama (submit gagal), bukan operasi normal.
- **Keputusan (owner 16 Jul): REAKTIF.** Discard draft GA dibutuhin di operasi normal (harga bener → submit bersih; ga-eligible reject di preview/add). Discard cuma buat RECOVERY draft sisa run crash — sniff terpisah nanti, GA ngeblok Task 9.
- Yg WAJIB dijaga: **preview_no fresh per sesi** (`preview_no:""` katanya ga selalu fresh — pastiin pas implementasi).

**🔬 TEMUAN VERIF LIVE TASK 9 (16 Jul):**
- ✅ Alur add→edit→submit JALAN, submit BERSIH (0 draft nyangkut), takedown JALAN di sesi bersih. Deteksi durasi bener (86399s→1.5%). KPI hitung bener.
- ⚠️ **HARGA GAK NYANGKUT**: set 4432 (1.5%), committed dapet 3825 (harga rekomendasi Shopee). Edit versi GABUNG (price+stock 1 entry) → gagal. FIX: edit DIPISAH per entry (sniff owner). **BELUM re-verif** apa pisah bikin nyangkut ATAU Shopee CLAMP ke `max_campaign_entry_price` (perlu baca ceiling + retest bersih).
- ❌ **FULL API (no browser) GAK BISA**: `preview/add`+`edit`+`submit`+`opt_out`+`get_landing`+`get_session_list` LOLOS requests polos, TAPI `preview_list`+`nominated_entity_list`+`selector/verify` (baca nomination_id) = ANTI-BOT 90309999 → WAJIB browser navigate-listen. nominate butuh nomination_id → browser tetap perlu (buat baca). Optimasi mungkin: write plain + browser CUMA buat 1 read nomination_id (lebih ringkas dari skrg yg browser semua).
- ⚠️ Sisa lama item `49909255539` (~12 model status 30) di sesi 978125 dari kerjaan pre-compaction — owner putusin hapus/biarin.

**Architecture:** Diagnosa (`fase2_harga.diagnosa_toko`) mutusin per-variasi promo apa yang harus dicabut, berdasar keikutsertaan promo di `harga_promo_konteks` + fakta table. Eksekutor (`eksekusi_takedown_*`) jalanin cabutnya. Akar masalah: (1) Flash ga kelabel di konteks (ct=7 ga dikenal), (2) executor garansi/jam ga ada, (3) campaign nyimpen DB pakai username tapi baca pakai nama-display → ga ketemu, + cuma baca 3/7 sesi.

**Tech Stack:** Python 3.13, DrissionPage (browser-context), SQLAlchemy + Supabase Postgres, `requests`. Jalanin via `python run.py <cmd>`.

## ✅ STATUS EKSEKUSI (update 16 Jul) — kode + DRY beres, LIVE belum

Semua 8 task **code-complete + DRY-verified + di-commit/push**. **BELUM ADA yang jalan LIVE** (`MODE_LIVE=False`). Langkah "owner ACC → live" tiap task = PENDING.

| Task | Code | DRY-verified | LIVE |
|---|---|---|---|
| 0 STATUS jujur | ✅ | ✅ grep klaim palsu kosong | — (docs) |
| 1 Flash ct=7 | ✅ | ✅ 276 flash di konteks; 276 ke-flag pas ambang dipaksa | ✅ self-heal stop→hapus→recreate produk sama (sesi 481492786769946→481954642538724, slot sama) |
| 2 Executor garansi | ✅ | ✅ inject bid sintetis → executor nerima garansi_target=1 | ✅ withdraw live di Alialia (count 168→167, bid ilang), lalu restore |
| 3 Fix nama toko | ✅ | ✅ _nama_display→display, DB bersih | ⏳ probe nominate live |
| 4 Baca 7 sesi | ✅ | ✅ 7 sesi kebaca live, 978125 ada | ✅ (read-only) |
| 5 Campaign diagnosa | ✅ | ✅ inject test → ke-flag takedown | ⏳ |
| 6 Fase 3 | ✅ | ✅ 1217 alasan ketulis (DRY full) | ⏳ live sekali |
| 7 Rem paket | ✅ | ✅ syntax+import (logic simpel) | ⏳ probe toko flaky (ZIO/BEVERRA) |
| 8 Bisect voucher | ✅ | ✅ mock poison {3,7}/8 → 4 voucher | ⏳ probe poison asli |

**Sisa:** verifikasi LIVE per-task (flip MODE_LIVE=True + ACC angka DRY per-task) · draft nyangkut sesi 978067/978125 (bersihin manual UI) · Task 7-8 probe butuh toko flaky masuk scope (fase rollout).

## 🗺️ SISA PEKERJAAN KESELURUHAN PROGRAM (update 16 Jul) — bukan cuma takedown

Status per fase (kimmioshop + Alialia buat garansi): **cabut/takedown udah mateng + LIVE-verified. Pasang campaign + poin 1-4 harga + rollout = belum.** Program BELUM production-ready.

**✅ Udah mateng (kode + live-verified):**
- Fase 1 grab semua modul (campaign baca 7 sesi)
- Poin 3③④⑤ CABUT garansi/flash/campaign — garansi withdraw (Alialia), flash self-heal (stop→hapus→recreate), campaign takedown (sesi bersih)
- Poin 5 pasang paket/voucher/garansi/flash

**⏳ SISA — urut prioritas (owner putusin urutan):**
- [x] **S1. Campaign pasang — harga clamp (Task 9 lanjutan). KELAR 16 Jul mlm (commit 6fd9d19):**
  CLAMP KEBUKTI + GATE DIIMPLEMENT & LIVE-PROVEN. Temuan kunci:
  - `preview_list` bawa `pricing_application_info.max_campaign_entry_price` (= `reference_price_by_shopee`) = CEILING. Harga yg di-set > ceiling di-CLAMP turun (4432→3825 kemaren = ceiling model itu, BUKAN bug edit).
  - Gate di `nominate()`: desired > ceiling → model gate-fail → opt_out abis submit (endpoint discard-draft GA ADA). ⚠️ Temuan live: abis submit nominasi bisa NAHAN status 10 (review) → opt_out inline ditolak `329400012` → fallback: baris DB dibiarin, takedown per-jam nyabut pas status 30 (self-heal).
  - 🔴 **TEMUAN BISNIS (owner wajib tau):** 6/6 kandidat tes GAGAL gate — ceiling ≈ **0.95×harga tampil** (verif eksak item 24148110949: tampil 11900, ceiling 11305). Rule sesi (sniff): min-diskon + "pengecekan harga". Karena bot jaga harga konstan di target, ceiling selalu ~5% di bawah target → **KPI 1.5%/0.15% ga akan pernah lolos di sesi2 ini → bot bakal skip SEMUA (sesuai KPI, "klo ga bisa d daftarin skip")**. Kalau owner mau produk keikut campaign → pilihan: (a) relax KPI diskon ke ≥5%, (b) biarin skip semua, (c) naikin harga tampil dulu pre-campaign (lawan filosofi poin 1-4). KEPUTUSAN OWNER.
  - Konsekuensi: verif "harga nyangkut via edit-pisah" belum kebukti (ga ada kandidat lolos gate buat dites) — otomatis kebukti nanti kalau owner relax KPI / ada produk yg ceiling-nya longgar.
- [x] **S2. Optimasi API campaign. KELAR 16 Jul mlm (commit d4ba8e0):** `_api_post` router (browser kebuka→browser, nggak→requests polos). **Takedown per-jam sekarang FULL TANPA BROWSER** (get_open_sessions + opt_out + DB polos semua; ga ada lagi buka_page/segarkan di jalur itu). Nominate mingguan tetep browser (preview_list anti-bot). ⏳ live-verif jalur polos nyusul (bareng cleanup item tes).
- [x] **S3. POIN 1-4 HARGA LIVE. KELAR 17 Jul pagi (ACC owner "gas live semua"):** fase2 LIVE kimmioshop — diagnosa 1063 sesuai/153 koreksi/1 rem · Promo Toko **2 entri LIVE 0 gagal** · Campaign cabut LIVE (detail di bawah). Kasus `harga_dasar` (ubah harga awal) **0 kejadian** di data skrg → jalur itu belum keuji live (nunggu ada kasus nyata).
  - 🔴 **TEMUAN FAKE-SUCCESS opt_out:** 31 nominasi "ter-takedown" code=0 semua, TAPI bukti-hidup full-map: yg **status 30 BENERAN kecabut** (item lama 23 nominasi → sesi 957909+978182 KOSONG, verified) sedangkan **status 10 (pending review) GA KECABUT** walau code=0. Fix: takedown filter `nominate_status==30`, yg <30 ditunda (baris DB dipertahanin); opt_out inline di nominate() DIBUANG.
  - 2 fix diagnosa nyusul kebukti DRY: (a) takedown liat sesi belum-mulai (gabung window sesi+nominasi), (b) item "sesuai" tetep diaudit nominasi campaign-nya (nominasi nempel pas harga on-target).
- [x] **S4. Task 7 (rem paket) + Task 8 (bisect voucher). KELAR 17 Jul (Task 8 LIVE-VERIFIED):**
  - Task 7 probe ZIO+BEVERRA: `bundle_deal/list` **error keras 1400101507** → `_call` raise → toko skip (rem LAMA nangkep, aman ga dobel). Rem BARU (list KOSONG+code 0+total_count>0) belum ketemu kejadian nyata — mock-verified, kepasang nunggu.
  - Task 8 **LIVE di BEVERRA (ACC owner)**: band B1 kena ERROR_PARAM → bisect misahin → **poison `6007354859` ketemu & dibuang**, 10 voucher kebuat (BEVEU05I4..BEVEU15I), **verified live fe_status=1** semua. Item bersih tetep dapet voucher — persis desainnya.
- [x] **S5. Fase 3 LIVE full-cycle. KELAR 17 Jul pagi:** siklus penuh LIVE (fase 1→2→3, tier JAM+HARIAN) kimmioshop — **1217 alasan terkini ketulis DB** (verified query: narasi "✓ sesuai"/"⚠ belum" bener).
- [~] **S6. Rollout 9 toko lain.** Verif di kimmioshop + Alialia (garansi) + **BEVERRA (voucher, 17 Jul)**. Keputusan owner 17 Jul: **live kimmioshop dulu seminggu, baru rollout** (`TOKO_AKTIF=[]`).
- [x] **S7. Config final (ACC owner 17 Jul):** `MODE_LIVE=True` + `TOKO_AKTIF=["kimmioshop"]` + `FASE_AKTIF=[1,2,3]` — scheduler live 1 toko; 6 item pending-review kecabut otomatis pas approved. Rollout = tinggal `TOKO_AKTIF=[]`.
- [x] **S8. Housekeeping (mayoritas KELAR 17 Jul):**
  - ✅ Item lama `49909255539` DICABUT SEMUA (ACC owner): 957909 (12) + 978182 (11) via fase2 live + 978125 (12) via opt_out langsung — re-read verified 0 sisa.
  - ⚠️ SISA: **6 item tes pending-review (status 10)**: 1 di 957874 + 5 di 978125. Ga bisa dicabut selama review (fake-success trap). Baris DB kejaga → **kecabut OTOMATIS begitu approved (status 30) ASAL scheduler jalan** — kalau mau cepet, cabut manual via UI.
  - Mekanisme discard-draft recovery: masih belum di-sniff (belum kepake — draft nyangkut ga kejadian lagi di alur normal).

## 🔬 TEMUAN VERIF LIVE (16 Jul) — Task 3 write-path OK, gap opt_out DIBONGKAR

Verif live Task 3 (nominate 1 model isolated ke sesi 978125):
- ✅ **Write-path LIVE-PROVEN**: nominate `committed 1 model`, DB nyatet `toko='Kimmioshop'` (display, bukan 'kimmioshop') — bug nama toko Task 3 beneran kelar di live.
- ❌ **opt_out gagal `10002 not found`** → diselidiki (bedah `__sniff_campaign_aksi.json`, read-only).

**HASIL INVESTIGASI (kesimpulan penting buat Task 5):**
- nomination_id **STABIL** melewati transisi staged→committed. Sniff bukti: id `2300000005165047425` muncul di `preview_list` (nominate_status **10**) DAN `nominated_entity_list` (nominate_status **30**) — **id SAMA PERSIS**. Jadi premis Task 3/5 (simpen preview-id → pakai buat opt_out) **VALID**, bukan cacat.
- Kegagalan opt_out gua **BUKAN** karena desain, tapi karena **sesi 978125 TERCEMAR**: ada draft nyangkut (item 24148110949 Rp0) yg bikin tiap submit "1 gagal" + sisa state tes lama → id yg ke-capture jadi ga valid. Sesi BERSIH → konsisten (kebukti di sniff).

**OPEN ITEM (belum kelar):**
- [ ] **Manual (owner):** cabut item tes `51309165959` dari sesi 978125 tab "Dinominasikan" + buang draft nyangkut `24148110949` tab "Menunggu Didaftarkan". Ini ngebersihin sesi → `nominated_entity_list` kebaca lagi.
- [ ] **Verif live Task 5 (campaign takedown) HARUS di sesi BERSIH** — JANGAN pakai 978125 selama draft nyangkut belum dibuang (testbed tercemar → hasil ga bisa dipercaya).
- [ ] Robustness: `takedown_products` opt_out yg `10002 not found` (id stale krn state sesi berubah) udah non-fatal (log + lanjut per-chunk) — cukup; kalau sering, tambah re-grab id sebelum opt_out.

## Global Constraints

- **MODE_LIVE sekarang `True`, scope `TOKO_AKTIF=["kimmioshop"]`.** Tiap task DRY dulu (`MODE_LIVE=False`) → tunjukin angka → owner ACC → baru live. JANGAN live tanpa ACC.
- **Nama toko di SEMUA tabel = NAMA DISPLAY** (mis. `"Kimmioshop"`, dari `SHOP_DATABASE[username]["name"]`), BUKAN username (`"kimmioshop"`). Verified: `harga_olah_data`/`harga_fakta_flash_item` pakai display. Ini kunci bug #3.
- **Verifikasi HIDUP wajib** (aturan owner): sukses = bukti status Shopee berubah (count naik/turun, fe_status), bukan cuma API code=0.
- **Harga di API promo/campaign = rupiah × `config.FAKTOR_HARGA` (100000).** Bandingin ke target harus dibagi dulu.
- **Jangan bikin file .md baru selain plan ini.** Update progres di STATUS.md + catatan di PANDUAN §11.
- Commit pas selesai per-task (owner minta commit tiap task beres), pesan bahasa santai + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 0: Jujurin STATUS.md (cabut klaim campaign palsu)

**Kenapa duluan:** STATUS.md sekarang ngeklaim campaign "✅ SOLVED FINAL verified live" — itu BOHONG (bug nama toko bikin takedown ga pernah nyambung). Sesi baru bakal salah ambil keputusan kalau dokumen bohong.

**Files:**
- Modify: `STATUS.md` (bagian PROGRES SEKARANG, baris ~110–126)

**Interfaces:** —

- [ ] **Step 1: Ganti baris 110** dari `🟡 Garansi / Promo Toko / Campaign / Flash — logika beres, belum tes live` jadi:
  ```
  - ✅ Promo Toko — nyambung (Shopee kasih ct=8 di API produk)
  - 🔴 Garansi/Flash/Campaign CABUT per-jam — belum jalan (lihat docs/plans/2026-07-16-perbaikan-takedown-fase2.md)
  ```
- [ ] **Step 2: Ganti blok M4 campaign** (baris ~115–126, yang "SOLVED FINAL verified live" + diagnosa 1-5) jadi 3 baris jujur:
  ```
  **campaign 🔧 (16 Jul):** nominate sisi Shopee JALAN (count naik-turun kebukti live), TAPI
  pencatatan DB rusak — nulis pakai username 'kimmioshop', baca pakai display 'Kimmioshop' →
  takedown ga pernah ketemu. Plus get_open_sessions cuma baca 3/7 sesi. Fix di plan 16 Jul.
  ```
- [ ] **Step 3: Verifikasi** — `grep -n "SOLVED FINAL" STATUS.md` → harus KOSONG.
- [ ] **Step 4: Commit**
  ```bash
  git add STATUS.md
  git commit -m "docs(status): cabut klaim campaign 'solved final' yg keliru -- bug nama toko"
  ```

---

## Task 1: Flash masuk konteks (label ct=7)

**Kenapa:** Flash MUNCUL di API produk `ongoing_campaigns` sebagai `campaign_type=7` (probe 16 Jul: item 51559153188, 8 model, harga 15140, window 6 jam). Tapi `PROMO_LABEL` ga kenal 7 → ke-label "Tipe 7" → `_cek_koreksi_turun` nyari `by_jenis.get("Flash Sale")` ga ketemu → takedown flash nerima 0. Tambah 1 mapping = flash masuk konteks → diagnosa 3c nyala.

**⚠️ DECISION (owner tadi milih "semua sesi termasuk akan datang"):** Cara konteks ini **cuma nangkep flash yang LAGI JALAN** (ongoing_campaigns ga masukin sesi akan-datang). Sesi akan-datang ga akan kesentuh takedown per-jam. Plan ini pakai **live-only** (rekomendasi — sesi akan-datang stoknya bisa keisi lagi sebelum mulai, dan provisioning mingguan daftar ulang). Kalau owner tetap mau akan-datang → butuh task terpisah baca `harga_fakta_flash_item` (lebih mahal, ditunda).

**Files:**
- Modify: `config.py:212` (`PROMO_LABEL`)

**Interfaces:**
- Produces: konteks row `jenis="Flash Sale"` buat variasi yang lagi di flash → dikonsumsi `fase2_harga._cek_koreksi_turun` 3c (udah ada).

- [ ] **Step 1: Tambah mapping ct=7** di `config.py:212`:
  ```python
  PROMO_LABEL = {0: "Campaign", 3: "Paket Diskon", 7: "Flash Sale", 8: "Promo Toko", 11: "Garansi Harga Terbaik"}
  ```
- [ ] **Step 2: Probe konteks kebentuk** — grab kimmioshop live, cek konteks dapet "Flash Sale":
  ```bash
  python run.py grab
  ```
  Lalu:
  ```bash
  python -c "from modules.db import get_engine; from sqlalchemy import text;
  print(get_engine().connect().execute(text(\"select count(*) from harga_promo_konteks where toko='Kimmioshop' and jenis='Flash Sale'\")).scalar())"
  ```
  Expected: angka > 0 (sebelum fix = 0).
- [ ] **Step 3: DRY diagnosa — cek flash ke-flag** (`MODE_LIVE=False` di config):
  ```bash
  python run.py fase2
  ```
  Cari di log baris `takedown flash` dengan target > 0 (sebelum fix selalu 0). CATAT berapa sesi/item bakal kena.
- [ ] **Step 4: Owner ACC angka DRY → baru live.** (flash takedown = AKHIRI SESI, collateral 1 sesi penuh — pastiin owner OK jumlahnya.)
- [ ] **Step 5: Commit**
  ```bash
  git add config.py
  git commit -m "fix(flash): kenalin campaign_type 7 = Flash Sale biar masuk konteks & takedown 3c nyala"
  ```

---

## Task 2: Executor Garansi cabut per-jam

**Kenapa:** STATUS poin 3③ = cabut garansi tiap jam kalau best < target−500 ATAU margin < 7%. Diagnosa UDAH nge-flag `{"promo":"Garansi","aksi":"takedown"}` (fase2_harga.py:68), tapi `eksekusi_takedown_garansi` GA ADA — `run.py` cuma manggil takedown flash+campaign. Jadi alasan nulis "Garansi dicabut" padahal aksinya kosong. Data (`bid_id`) udah ada di flag.

**Files:**
- Modify: `modules/fase2_harga.py` (tambah `eksekusi_takedown_garansi`, niru `eksekusi_takedown_flash` :446)
- Modify: `run.py` (2 titik: `siklus_terpadu` ~:146, `jalankan_fase2` ~:245)

**Interfaces:**
- Consumes: `_kunci_takedown(diagnosa, "Garansi")` — TAPI `_kunci_takedown` (fase2_harga.py:440) match by `a.get("promo")`; flag garansi promo="Garansi", aksi="takedown", plus bawa `bid_id`. Perlu ambil bid_id, bukan cuma (item,model).
- Consumes: `garansi.withdraw(session, bid_ids)` (garansi.py:185, DRY-aware).
- Produces: `eksekusi_takedown_garansi(shop, nama_toko, session, diagnosa) -> {"garansi_takedown": int, "garansi_target": int}`.

- [ ] **Step 1: Tambah fungsi** di `modules/fase2_harga.py` (abis `eksekusi_takedown_campaign`):
  ```python
  def eksekusi_takedown_garansi(shop, nama_toko, session, diagnosa):
      """SOLUSI poin 3③. Withdraw variasi 'koreksi_turun' yg garansi-nya undercut (best<target-500)
      atau margin@program<7%. bid_id dibawa langsung di flag diagnosa. DRY-aware (garansi.withdraw)."""
      from modules import garansi as G
      bids = [a["bid_id"] for d in diagnosa for a in d["aksi"]
              if a.get("promo") == "Garansi" and a.get("aksi") == "takedown" and a.get("bid_id")]
      if not bids:
          return {"garansi_takedown": 0, "garansi_target": 0}
      n = G.withdraw(session, bids)[0] if not config.DRY_RUN else 0
      mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
      catat(f"({mode}) {len(bids)} bid garansi target -> {n} ter-withdraw",
            status=("live" if (not config.DRY_RUN and n) else "ok"),
            fase="F2", toko=nama_toko, modul="garansi", detail={"target": len(bids), "withdraw": n, "dry": config.DRY_RUN})
      return {"garansi_takedown": n, "garansi_target": len(bids)}
  ```
- [ ] **Step 2: Panggil di `run.py` `siklus_terpadu`** (abis baris `takedown campaign`, ~:146):
  ```python
                      _aman(nama, "takedown garansi", lambda: F2.eksekusi_takedown_garansi(username, nama, session, d))
  ```
- [ ] **Step 3: Panggil di `run.py` `jalankan_fase2`** (abis `takedown campaign`, ~:245):
  ```python
              _aman(nama, "takedown garansi", lambda: F2.eksekusi_takedown_garansi(username, nama, session, d))
  ```
- [ ] **Step 4: DRY verifikasi** (`MODE_LIVE=False`): `python run.py fase2` → cari log `takedown garansi` dengan target. Bandingin manual sama jumlah flag garansi di dashboard alasan.
- [ ] **Step 5: Owner ACC → live → cek bukti** — abis live, garansi yg di-withdraw item-nya harusnya ilang dari `list_ongoing_status` next grab.
- [ ] **Step 6: Commit**
  ```bash
  git add modules/fase2_harga.py run.py
  git commit -m "feat(garansi): executor takedown per-jam (poin 3-3) -- withdraw bid yg undercut/margin tipis"
  ```

---

## Task 3: Fix bug nama toko campaign (standarisasi nama display)

**Kenapa:** `campaign_util.nominate` nyimpen ke DB pakai `shop` (= username `"kimmioshop"` pas dipanggil provisioning), tapi `baca_campaign_item` dibaca pakai `nama_toko` (= display `"Kimmioshop"`). Ketemu di DB: `harga_fakta_campaign_item.toko='kimmioshop'` (huruf kecil, sendirian di antara semua tabel lain yg display). Standar semua tabel = DISPLAY. Fix: campaign write pakai display.

**Files:**
- Modify: `modules/campaign_util.py` (`nominate` ~:329, `get_preview_nomination_ids` upsert call)
- Modify: `modules/sql_harga.py` (`upsert_fakta_campaign_item` :447 — tambah guard `is_toko_resmi` biar konsisten `_snapshot_toko`)

**Interfaces:**
- Consumes: `config.SHOP_DATABASE[shop]["name"]` buat resolve display dari username (kalau `shop` username). Kalau `shop` udah display, `is_toko_resmi` True → pakai apa adanya.
- Produces: `harga_fakta_campaign_item.toko` SELALU display name.

- [ ] **Step 1: Helper resolve display** di `campaign_util.py` (atas file):
  ```python
  def _nama_display(shop):
      """username -> nama display; kalau udah display, balikin apa adanya."""
      info = config.SHOP_DATABASE.get(shop)
      return info["name"] if info else shop
  ```
- [ ] **Step 2: Di `nominate`, pas manggil upsert** (di dalam `get_preview_nomination_ids` block), ganti `SQL.upsert_fakta_campaign_item(shop, baris)` jadi:
  ```python
              SQL.upsert_fakta_campaign_item(_nama_display(shop), baris)
  ```
- [ ] **Step 3: Guard di `sql_harga.upsert_fakta_campaign_item`** (:447, sesudah `if not baris: return 0`):
  ```python
      if not config.is_toko_resmi(toko):
          return 0
  ```
- [ ] **Step 4: Bersihin baris nyasar lama** (huruf kecil dari tes gua kemarin):
  ```bash
  python -c "from modules.db import get_engine; from sqlalchemy import text;
  c=get_engine().begin(); c.__enter__().execute(text(\"delete from harga_fakta_campaign_item where toko='kimmioshop'\"))"
  ```
  (atau lewat `python run.py` helper — pastiin cuma hapus yg huruf-kecil.)
- [ ] **Step 5: Probe konsisten** — nominate 1 model tes, cek DB ketulis 'Kimmioshop' lalu `baca_campaign_item('Kimmioshop', sid)` nemu. Lalu takedown lagi (bersihin tes). Bukti hidup: `get_session_nomination_statistics` count naik→turun.
- [ ] **Step 6: Commit**
  ```bash
  git add modules/campaign_util.py modules/sql_harga.py
  git commit -m "fix(campaign): standarisasi nama toko display di fakta_campaign_item + guard toko resmi"
  ```

---

## Task 4: Campaign baca 7 sesi (data.list[])

**Kenapa:** `get_open_sessions` cuma baca `data.general.product_session` (3 sesi "umum", potongan ketat 0,15%). Sniff: `get_session_list` juga balikin `data.list[]` = 4 sesi lagi (25 Jul & 8.8, termasuk 978125 yg owner bilang bisa didaftarin). Tiap sesi punya `campaign_id` sendiri. Tanpa ini, provisioning cuma nyoba sesi ketat (0 lolos terus) + takedown ga liat sesi bagus.

**Files:**
- Modify: `modules/campaign_util.py` `get_open_sessions` (:97–196, bagian parse `product_sessions`)

**Interfaces:**
- Consumes: response `URL_GET_SESSION_LIST` — `data.general.product_session[]` + `data.list[].product_session[]`. Tiap sesi punya `campaign_id` sendiri (verified sniff: general=2048121675, list=2048121764/765). PENTING: pakai `s.get("campaign_id")` PER SESI, bukan campaign induk.
- Produces: `open_sessions[]` lengkap (7 sesi kimmioshop, bukan 3).

- [ ] **Step 1: Ekstrak sesi dari DUA sumber** — di `get_open_sessions`, ganti baris `product_sessions = session_res.get("data", {}).get("general", {}).get("product_session") or []` jadi kumpulin dua-duanya:
  ```python
          data_sr = session_res.get("data", {}) or {}
          product_sessions = list((data_sr.get("general", {}) or {}).get("product_session") or [])
          for grp in (data_sr.get("list") or []):
              product_sessions.extend(grp.get("product_session") or [])
  ```
- [ ] **Step 2: Pakai campaign_id PER SESI** — di loop `for s in product_sessions`, pas append `open_sessions`, ganti `"campaign_id": str(campaign_id)` (campaign induk) jadi:
  ```python
                  "campaign_id": str(s.get("campaign_id") or campaign_id),
  ```
- [ ] **Step 3: Probe — 7 sesi kebaca** (browser-context):
  ```bash
  python -c "import config; from modules.session import grab_session, close_session, buka_page_toko, tutup_page; from modules import campaign_util as CU;
  s=grab_session(shop='kimmioshop', i=1); buka_page_toko('kimmioshop',1);
  ses=CU.get_open_sessions(s,'kimmioshop',window='nominasi');
  [print(x['session_id'], x['campaign_id'], x['session_name'][:40]) for x in ses];
  tutup_page(); close_session()"
  ```
  Expected: ~7 sesi (bukan 3), 978125 ADA.
- [ ] **Step 4: Commit**
  ```bash
  git add modules/campaign_util.py
  git commit -m "fix(campaign): baca 7 sesi (data.general + data.list) + campaign_id per-sesi"
  ```

---

## Task 5: Campaign masuk diagnosa (cross-ref fakta_campaign_item)

**Kenapa:** Takedown campaign per-jam (poin 3⑤) butuh diagnosa nge-flag item campaign yg harga<target×0,985 / stok<30 / stok<pjh. Diagnosa bangun `by_jenis` dari `harga_promo_konteks` — campaign nominasi (cmt/tanggal-kembar) GA muncul konsisten di situ (ct=0 cuma pas sesi live). Sumber andal = `harga_fakta_campaign_item` (nomination_id + campaign_price, diisi Task 3). Inject sbagai "Campaign" promo ke diagnosa.

**Files:**
- Modify: `modules/fase2_harga.py` `diagnosa_toko` (:112, sesudah `promo = SQL.baca_promo_detail(...)`)

**Interfaces:**
- Consumes: `SQL.baca_campaign_item(nama_toko)` -> `{(item,model): {campaign_price(micro), nomination_id, session_id}}`.
- Produces: entri promo `{"jenis":"Campaign","harga_promo": campaign_price//FAKTOR_HARGA, "status":"aktif", "stok": <dari olah_data>}` masuk `promo[key]` → `_cek_koreksi_turun` 3d nyala → `_kunci_takedown(diagnosa,"Campaign")` populated → `eksekusi_takedown_campaign` (udah baca DB nomination_id).

- [ ] **Step 1: Merge campaign nominasi ke promo map** di `diagnosa_toko`, sesudah `promo = SQL.baca_promo_detail(nama_toko)`:
  ```python
      camp = SQL.baca_campaign_item(nama_toko)   # {(item,model): {campaign_price micro, ...}}
      for (iid, mid), cv in camp.items():
          harga = int((cv.get("campaign_price") or 0)) // config.FAKTOR_HARGA
          if harga <= 0:
              continue
          promo.setdefault((iid, mid), []).append({
              "jenis": "Campaign", "harga_promo": harga, "status": "aktif",
              "stok": 0,   # stok diisi dari baris di loop bawah (b["stok"])
          })
  ```
  (Catatan: `_cek_koreksi_turun` 3d pakai `stok` dari argumen `stok`, bukan dari entri promo — jadi field stok di entri ga kepake, aman.)
- [ ] **Step 2: DRY verifikasi** — pastiin ada nominasi campaign di DB dulu (Task 3/4 provisioning), lalu `python run.py fase2` (DRY) → cari log `takedown campaign` target > 0 kalau ada yg langgar kriteria.
- [ ] **Step 3: Owner ACC → live → bukti hidup** — abis live, `get_session_nomination_statistics` sesi terkait count turun.
- [ ] **Step 4: Commit**
  ```bash
  git add modules/fase2_harga.py
  git commit -m "feat(campaign): inject nominasi (fakta_campaign_item) ke diagnosa biar takedown 3-5 nyala"
  ```

---

## Task 6: Verifikasi Fase 3 sekali live

**Kenapa:** Fase 3 (Loop B grab-ulang + alasan terkini) logika ada tapi BELUM pernah live. Butuh 1 run buat bukti alasan ketulis + status terkini bener.

**Files:** — (cuma jalanin, `FASE_AKTIF=[1,2,3]` udah set)

- [ ] **Step 1: DRY full siklus** (`MODE_LIVE=False`): `python run.py tes full` → cek log ada blok `FASE 3 (LAPORAN)` + `X alasan terkini`.
- [ ] **Step 2: Cek alasan ketulis** ke DB:
  ```bash
  python -c "from modules.db import get_engine; from sqlalchemy import text;
  r=get_engine().connect().execute(text(\"select alasan from harga_olah_data where toko='Kimmioshop' and alasan is not null and alasan<>'' limit 5\")).fetchall();
  [print(x.alasan[:100]) for x in r]"
  ```
  Expected: alasan ada isi (narasi aksi + `✓ sesuai`/`⚠ belum`).
- [ ] **Step 3: Owner ACC → live tes full sekali** → verifikasi dashboard /log ada heartbeat `laporan`.
- [ ] **Step 4: Update STATUS + PANDUAN** — turunin penanda Fase 3 & campaign/flash/garansi jadi ✅ kalau kebukti live. Commit.
  ```bash
  git add STATUS.md PANDUAN_PROGRAM.md
  git commit -m "docs: update progres fase 2/3 -- takedown flash/campaign/garansi + fase 3 verified live"
  ```

---

## Task 7: Rem anti-dobel paket (3 toko flaky: Topikece/ZIO/BEVERRA)

**Kenapa:** `bundle_deal/list/` buat ZIO & BEVERRA sering `1400101507 database unavailable` (flaky sisi Shopee). Kalau list **error** → `_call` raise (3x retry) → `paket()` throw → `_aman` skip toko → aman, ga dobel (rem ini UDAH ada). Tapi kalau Shopee balik `code=0` dengan list **KOSONG/sebagian** (sukses palsu) → bot anggap "belum ada UPSELL" → `buat_deal` baru → **UPSELL dobel + deal numpuk (30-70)**. Rem buat kasus ini BELUM ada.

**Design (rem konservatif):** sebelum `buat_deal`, cross-check ke `baca_kapasitas().total_count` (count authoritative dari Shopee). Kalau list kebaca KOSONG TAPI Shopee bilang ada deal (`total_count > 0`) → list flaky → SKIP toko (jangan buat, jangan enroll), tunggu grab konsisten. ⚠️ ASUMSI: `total_count` (time_status=2/berjalan) reliable walau list body flaky — kalau ternyata total_count juga ikut flaky, fallback: retry `list_deals` 3x ambil MAX count.

**Files:**
- Modify: `modules/provisioning.py` `paket` (~:32–67, sebelum cabang buat-baru)

**Interfaces:**
- Consumes: `PD.baca_kapasitas(session) -> {"total_count", "max_active_count", "is_exceed"}` (paket_diskon.py:154).
- Produces: `paket()` return `{"paket": None, "skip": "list_flaky"}` kalau kena rem.

- [ ] **Step 1: Guard flaky** di `paket()`, sesudah `deals = PD.list_deals(session) or []` (baris ~32) + `kap = PD.baca_kapasitas(session)` (pindahin ke atas kalau perlu):
  ```python
      kap = PD.baca_kapasitas(session)
      if not deals and (kap.get("total_count") or 0) > 0:
          log(f"list deal KOSONG tapi Shopee bilang ada {kap['total_count']} deal — FLAKY, skip (rem anti-dobel)",
              level="warning", fase="F2", toko=nama_toko, modul="paket")
          return {"paket": None, "skip": "list_flaky", "total_count": kap.get("total_count")}
  ```
- [ ] **Step 2: DRY probe di 1 toko flaky** — set `TOKO_AKTIF=["zioscarfsupplierhijabimport"]` (cek username persis di SHOP_DATABASE), `MODE_LIVE=False`, `python run.py provisioning paket`. Amati: kalau list kosong+total_count>0 → log "FLAKY, skip" muncul (BUKAN "bakal BUAT baru").
- [ ] **Step 3: Commit**
  ```bash
  git add modules/provisioning.py
  git commit -m "fix(paket): rem anti-dobel -- skip kalau list kosong tapi Shopee bilang ada deal (flaky)"
  ```

---

## Task 8: Bisect voucher on ERROR_PARAM (poison non-stok-0)

**Kenapa:** Voucher produk ditolak Shopee (ERROR_PARAM) kalau ada 1 item "poison". Stok-0 udah dibuang (provisioning.py:134-137). Tapi kalau ada poison NON-stok-0 (mis. item ke-blokir promosi), `buat_voucher` gagal → seluruh band ke-skip (`gagal+=1`), padahal item bagus di band itu ikut ga dapet voucher. Bisect = split chunk, buang item biang, create yang bersih.

**Files:**
- Modify: `modules/voucher.py` (`buat_voucher` — pastiin ERROR_PARAM ke-raise dengan tipe/pesan yg kebedain)
- Modify: `modules/provisioning.py` `voucher` (~:218–222, bungkus create dengan helper bisect)

**Interfaces:**
- Consumes: `V.buat_voucher(...)` yang raise `RuntimeError` berisi "ERROR_PARAM" kalau poison.
- Produces: helper `_buat_voucher_bisect(session, nama, kode_fn, start, min_b, ids) -> (vid|None, dibuang:list)` — create; kalau ERROR_PARAM & len(ids)>1 → split 2, rekursi tiap half; len==1 & gagal → item itu poison, buang.

- [ ] **Step 1: Helper bisect** di `provisioning.py` (atas `def voucher`):
  ```python
  def _buat_voucher_bisect(session, nama_slot, buat_fn, ids):
      """Create voucher; kalau ERROR_PARAM (poison) & >1 item → split & rekursi buang item biang.
      buat_fn(ids_list) -> vid (raise RuntimeError 'ERROR_PARAM' kalau poison). Return (vids, dibuang)."""
      ids = sorted(ids)
      try:
          return [buat_fn(ids)], []
      except RuntimeError as e:
          if "ERROR_PARAM" not in str(e) or len(ids) <= 1:
              if len(ids) == 1:
                  return [], ids     # 1 item & tetap gagal → itu poison, buang
              raise
      mid = len(ids) // 2
      v1, d1 = _buat_voucher_bisect(session, nama_slot, buat_fn, ids[:mid])
      v2, d2 = _buat_voucher_bisect(session, nama_slot, buat_fn, ids[mid:])
      return v1 + v2, d1 + d2
  ```
- [ ] **Step 2: Pastiin `V.buat_voucher` raise ERROR_PARAM kebedain** — cek `modules/voucher.py` `buat_voucher`: kalau response code != 0 & message ERROR_PARAM, raise `RuntimeError(f"ERROR_PARAM: {msg}")`. (Kalau udah, skip.)
- [ ] **Step 3: Ganti call create** di `provisioning.voucher` (~:218) pakai helper:
  ```python
          vids, dibuang = _buat_voucher_bisect(session, nama_slot,
              lambda _ids: V.buat_voucher(session, nama_slot, _kode_voucher(vouchers, shop, now, idx), start,
                                          start + config.KPI_VOUCHER_DURASI_HARI * 86400,
                                          discount=config.KPI_VOUCHER_DISKON_PCT, min_price=min_b,
                                          max_value=None, item_ids=_ids, **V.TIPE["produk"]), ids)
          if dibuang:
              log(f"{nama_slot}: {len(dibuang)} item poison dibuang via bisect: {dibuang[:10]}",
                  level="warning", fase="F2", toko=nama_toko, modul="voucher")
          buat += len(vids)
  ```
- [ ] **Step 4: DRY/live probe** — di toko yg dulu poison (bukan kimmioshop), `python run.py provisioning voucher`. Amati: band yg dulu total-gagal sekarang jadi (item bersih dapet voucher, item poison ke-log dibuang). Bukti hidup: voucher band itu `fe_status` jalan (lewat start).
- [ ] **Step 5: Commit**
  ```bash
  git add modules/voucher.py modules/provisioning.py
  git commit -m "feat(voucher): bisect-on-ERROR_PARAM -- buang item poison non-stok-0, sisanya tetap dapet voucher"
  ```

---

## Catatan Self-Review

- **Coverage:** Task 1=flash 3④ · Task 2=garansi 3③ · Task 3+4+5=campaign 3⑤+pasang · Task 6=Fase 3 · Task 7=paket 3-toko flaky · Task 8=voucher poison bisect. Poin 1-2/komisi/promo-toko/harga-dasar udah ✅ (ga masuk plan).
- **Belum kebahas (sengaja ditunda, bukan lupa):** (a) Flash sesi AKAN-DATANG (butuh baca fakta_flash_item, konteks cuma ongoing) — owner putusin dulu. (b) Flash self-heal live end-to-end (warisan lama, verifikasi terpisah). (c) config revert MODE_LIVE + rollout voucher/paket ke 9 toko (abis semua verified). (d) voucher lama ga bisa diakhirin via API (biarin expire).
- **⚠️ Ke-2 domain campur (takedown kimmioshop + provisioning 3-toko) atas permintaan owner (gabung 1 plan) — writing-plans normalnya saranin pisah. Task 7-8 bisa dikerjain paralel/terpisah dari Task 1-6.**
- **Urutan aman→berisiko:** Task 0 (docs) → 1 (config 1 baris) → 2 (garansi) → 3 (bug fix) → 4 (baca sesi) → 5 (diagnosa) → 6 (verif) → 7 (rem paket) → 8 (bisect voucher). Tiap yang nyentuh Shopee: DRY → ACC → live.
