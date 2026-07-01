"""sniff_promo.py — Penyadap API Shopee untuk AKSI promo yang MEMBLOKIR ubah harga.

Tujuan: menangkap endpoint AKSI (URL + params + payload + response) untuk jenis
promo yang belum punya handler di Fase 2:
  - PAKET DISKON  (add-on deal / bundle)  -> takedown item dari paket
  - GARANSI HARGA TERBAIK (best price guarantee) -> opt-out item
  - FLASH SALE    (kalau ada sesi aktif)   -> takedown item
  - get_campaign_info_by_item_list         -> baca semua campaign per item (Fase 1)

Cara pakai (login dulu: python run.py login):
  python sniff_promo.py            # multi-tab, buka Produk Saya, lakukan aksi di browser
  python sniff_promo.py <label>    # label bebas -> nama file __sniff_<label>.json

Hasil: __sniff_promo.json (default). Kirim file ini balik untuk dianalisis.

Metode multi-tab disalin dari `02 Otomatisasi Monitoring Harga/sniff.py`
(hanya butuh modules.session._buat_options — kompatibel dgn Syntra).
"""
import sys
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage


def _ringkas_nilai(v, _depth=0):
    """Objek JSON-safe + pangkas list panjang biar file enak dibaca."""
    if isinstance(v, dict):
        return {k: _ringkas_nilai(val, _depth + 1) for k, val in v.items()}
    if isinstance(v, list):
        potong = v[:15]
        hasil = [_ringkas_nilai(x, _depth + 1) for x in potong]
        if len(v) > 15:
            hasil.append(f"...(+{len(v) - 15} item lagi, total {len(v)})")
        return hasil
    return v


def _as_json(x):
    if x is None:
        return None
    if isinstance(x, (dict, list)):
        return x
    try:
        return json.loads(x)
    except Exception:
        return str(x)[:2000]


def _simpan(paket, nama_file):
    keluaran = []
    for p in paket:
        try:
            url = p.url
            if "/api/" not in url:
                continue
            keluaran.append({
                "url": url,
                "method": getattr(p, "method", ""),
                "request_params": _ringkas_nilai(_as_json(getattr(p.request, "params", None))),
                "request_body": _ringkas_nilai(_as_json(getattr(p.request, "postData", None))),
                "response": _ringkas_nilai(_as_json(getattr(p.response, "body", None))),
            })
        except Exception as e:
            keluaran.append({"error": str(e)})
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    print(colorama.Fore.GREEN
          + f"\n[sniff] {len(keluaran)} request API tersimpan ke {nama_file}"
          + colorama.Style.RESET_ALL)
    # ringkas endpoint unik (paling penting buat baca cepat)
    seen = set()
    for k in keluaran:
        u = k.get("url", "")
        base = u.split("?")[0]
        if "/api/" in u and base not in seen:
            seen.add(base)
            print(colorama.Fore.CYAN + f"  - {k.get('method',''):4} {base}" + colorama.Style.RESET_ALL)


def _watcher_multitab(page, paket, stop_event):
    """Dengerin SEMUA tab (termasuk tab baru yang dibuka Shopee)."""
    attached = set()

    def _sniff_tab(tab):
        try:
            tab.listen.start("seller.shopee.co.id/api")
            for p in tab.listen.steps():
                paket.append(p)
                if stop_event.is_set():
                    break
        except Exception:
            pass

    while not stop_event.is_set():
        try:
            tab_ids = page.tab_ids
        except Exception:
            tab_ids = []
        for tid in list(tab_ids):
            if tid not in attached:
                try:
                    t = page.get_tab(tid)
                    attached.add(tid)
                    th = threading.Thread(target=_sniff_tab, args=(t,), daemon=True)
                    th.start()
                except Exception:
                    pass
        time.sleep(0.5)


def jalankan(nama_file):
    page = DrissionPage.ChromiumPage(_buat_options())
    page.set.window.max()
    print(colorama.Fore.YELLOW + "[sniff promo] membuka Produk Saya (mode multi-tab)..." + colorama.Style.RESET_ALL)
    page.get("https://seller.shopee.co.id/portal/product/list/all")

    paket = []
    stop_event = threading.Event()
    th = threading.Thread(target=_watcher_multitab, args=(page, paket, stop_event), daemon=True)
    th.start()

    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Tujuan: nangkep endpoint SAVE (yg beneran MENGUBAH), bukan cuma buka editor.
  ⚠️ WAJIB sampai klik SIMPAN/KONFIRMASI & muncul notif "tersimpan" —
     kalau cuma buka halaman, yg ketangkep cuma 'validate' (percuma).
  (boleh buka tab baru, semua tetap ketangkep)

  [A] PAKET DISKON (Add-on Deal) — PALING PENTING:
      Marketing Centre -> Paket Diskon / Add-on Deal
      -> klik EDIT salah satu paket yg berjalan
      -> HAPUS 1 produk dari daftar paket (klik ikon hapus/silang)
      -> klik SIMPAN / KONFIRMASI sampai muncul notif tersimpan.
      (boleh ditambahin balik lagi habis itu)

  [B] GARANSI HARGA TERBAIK (Best Price Guarantee):
      Produk Saya -> cari produk berlabel 'Garansi Harga Terbaik'
      -> buka pengaturan program itu -> NONAKTIFKAN utk 1 produk
      -> klik SIMPAN sampai notif tersimpan.

  [C] FLASH SALE (kalau ada sesi aktif/terjadwal) — opsional:
      Flash Sale Toko -> buka sesi -> HAPUS 1 produk -> SIMPAN.

  Lakukan A dulu (wajib), lalu B. Selesai? Balik ke sini & tekan ENTER.
================================================================
""" + colorama.Style.RESET_ALL)
    input("Tekan ENTER setelah aksi tersimpan... ")
    time.sleep(1)
    stop_event.set()
    th.join(timeout=5)
    _simpan(paket, nama_file)
    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "promo"
    jalankan(f"__sniff_{label}.json")
