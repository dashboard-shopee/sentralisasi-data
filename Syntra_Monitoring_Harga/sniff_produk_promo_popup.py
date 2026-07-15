"""sniff_produk_promo_popup.py — sniff endpoint di balik POPUP "produk ini ikut promo apa
aja" di halaman Produk Saya (klik ikon promo di baris produk -> muncul kartu Paket Diskon/
Promo Toko/Promo Shopee/Flash Sale dgn durasi+harga). Dugaan (15 Jul, grilling): endpoint ini
beda dari nominated_entity_list yg diblokir anti-bot, dan mungkin punya nomination_id/session_id
per campaign tanpa butuh signature x-sap-sec — kalau bener, bisa jadi jalan buat TAKEDOWN
campaign (butuh nomination_id) yang selama ini mentok.

Cara pakai (login dulu kalau sesi lama: python run.py login):
  python sniff_produk_promo_popup.py

Hasil: __sniff_produk_promo_popup.json.
"""
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage

URL_PRODUK_PAGE = "https://seller.shopee.co.id/portal/product/list/live"


def _ringkas(v, _depth=0):
    if isinstance(v, dict):
        return {k: _ringkas(val, _depth + 1) for k, val in v.items()}
    if isinstance(v, list):
        potong = v[:15]
        hasil = [_ringkas(x, _depth + 1) for x in potong]
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
                "request_headers": _ringkas(dict(getattr(p.request, "headers", None) or {})),
                "request_params": _ringkas(_as_json(getattr(p.request, "params", None))),
                "request_body": _ringkas(_as_json(getattr(p.request, "postData", None))),
                "response": _ringkas(_as_json(getattr(p.response, "body", None))),
            })
        except Exception as e:
            keluaran.append({"error": str(e)})
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    print(colorama.Fore.GREEN + f"\n[sniff] {len(keluaran)} request API tersimpan ke {nama_file}" + colorama.Style.RESET_ALL)
    seen = set()
    for k in keluaran:
        u = k.get("url", "")
        base = u.split("?")[0]
        if base not in seen:
            seen.add(base)
            hdrs = k.get("request_headers") or {}
            has_sig = "x-sap-sec" in hdrs
            print(colorama.Fore.CYAN + f"  - {k.get('method',''):4} {base}  (x-sap-sec: {has_sig})" + colorama.Style.RESET_ALL)


def _watcher_multitab(page, paket, stop_event):
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


def jalankan():
    page = DrissionPage.ChromiumPage(_buat_options())
    page.set.window.max()
    print(colorama.Fore.YELLOW + f"[sniff produk-promo-popup] membuka {URL_PRODUK_PAGE} ..." + colorama.Style.RESET_ALL)
    page.get(URL_PRODUK_PAGE)

    paket = []
    stop_event = threading.Event()
    th = threading.Thread(target=_watcher_multitab, args=(page, paket, stop_event), daemon=True)
    th.start()

    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Cari produk yang lagi ikut CAMPAIGN tanggal kembar (badge/ikon promo di
  baris produk), KLIK ikon/link promo itu sampai muncul POPUP kartu
  (Paket Diskon / Promo Toko / Promo Shopee / Flash Sale, dgn durasi+harga
  kayak di screenshot). Ga usah klik apa-apa lagi, cukup BUKA popup-nya aja.

  Kalau bisa, coba juga klik salah satu KARTU CAMPAIGN di popup itu (biar
  ketangkep kalau ada request LANJUTAN pas kartu di-klik/di-hover).

  Selesai? Balik ke sini & tekan ENTER.
================================================================
""" + colorama.Style.RESET_ALL)
    input("Tekan ENTER setelah popup kebuka... ")
    time.sleep(1)
    stop_event.set()
    th.join(timeout=5)
    _simpan(paket, "__sniff_produk_promo_popup.json")
    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    jalankan()
