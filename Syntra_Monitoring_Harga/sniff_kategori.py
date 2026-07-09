"""sniff_kategori.py — auto-capture endpoint yang ngasih KATEGORI Shopee produk.

API list produk (search_product_list) TIDAK ngasih kategori. Kategori muncul saat
buka halaman EDIT/DETAIL 1 produk. Skrip ini buka Produk Saya, kamu klik 1 produk
buat lihat/edit detailnya -> skrip nangkep semua request API -> nanti dicari yg ngandung
'categor'/'category' (endpoint + params + response), biar bisa dibangun grab-nya.

Cara pakai (login dulu: python run.py login):
  python sniff_kategori.py

Langkah di browser yg kebuka:
  1. Halaman "Produk Saya" kebuka.
  2. KLIK 1 produk -> buka halaman detail/EDIT-nya (yg nampilin Kategori produk).
  3. Tunggu halaman edit ke-load penuh (kategori keliatan).
  4. Balik ke CMD, tekan ENTER (atau tunggu auto 2 menit).

Hasil: __sniff_kategori.json (semua request 'categor' + semua API). Kabarin, gua baca.
"""
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage

URL_PRODUK = "https://seller.shopee.co.id/portal/product/list/all"


def _as_json(x):
    if x is None:
        return None
    if isinstance(x, (dict, list)):
        return x
    try:
        return json.loads(x)
    except Exception:
        return str(x)[:3000]


def _watcher(page, paket, stop):
    attached = set()

    def _sniff(tab):
        try:
            tab.listen.start("seller.shopee.co.id/api")
            for p in tab.listen.steps():
                paket.append(p)
                if stop.is_set():
                    break
        except Exception:
            pass

    while not stop.is_set():
        try:
            ids = page.tab_ids
        except Exception:
            ids = []
        for tid in list(ids):
            if tid not in attached:
                try:
                    t = page.get_tab(tid)
                    attached.add(tid)
                    threading.Thread(target=_sniff, args=(t,), daemon=True).start()
                except Exception:
                    pass
        time.sleep(0.4)


def jalankan():
    page = DrissionPage.ChromiumPage(_buat_options())
    page.set.window.max()
    paket = []
    stop = threading.Event()
    threading.Thread(target=_watcher, args=(page, paket, stop), daemon=True).start()

    print(colorama.Fore.YELLOW + f"[sniff kategori] buka {URL_PRODUK} ..." + colorama.Style.RESET_ALL)
    page.get(URL_PRODUK)
    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Halaman PRODUK SAYA kebuka.
  -> KLIK 1 PRODUK buat buka halaman DETAIL/EDIT-nya (yg nampilin Kategori).
  -> Tunggu halaman edit ke-load penuh (kategori keliatan di layar).
  Selesai? Balik ke sini & tekan ENTER (atau tunggu auto 2 menit).
================================================================
""" + colorama.Style.RESET_ALL)

    done = threading.Event()
    def _tunggu():
        try:
            input("Tekan ENTER kalau halaman edit produk (kategori) udah tampil... ")
        except (EOFError, OSError):
            return
        done.set()
    threading.Thread(target=_tunggu, daemon=True).start()
    for _ in range(240):
        if done.is_set():
            break
        time.sleep(0.5)

    stop.set()
    time.sleep(0.5)

    kat, semua = [], []
    for p in paket:
        try:
            url = p.url
            if "/api/" not in url:
                continue
            item = {
                "url": url,
                "method": getattr(p, "method", ""),
                "params": _as_json(getattr(p.request, "params", None)),
                "body": _as_json(getattr(p.request, "postData", None)),
                "response": _as_json(getattr(p.response, "body", None)),
            }
            semua.append(item)
            blob = json.dumps(item, ensure_ascii=False).lower()
            if "categor" in blob:
                kat.append(item)
        except Exception:
            pass

    with open("__sniff_kategori.json", "w", encoding="utf-8") as f:
        json.dump({"kategori_requests": kat, "semua_api": semua}, f, ensure_ascii=False, indent=2)

    print(colorama.Fore.GREEN + f"\n[sniff] {len(semua)} request API, {len(kat)} ngandung 'categor' -> __sniff_kategori.json" + colorama.Style.RESET_ALL)
    for k in kat:
        print(colorama.Fore.CYAN + f"  {k['method']:4} {k['url'].split('?')[0]}" + colorama.Style.RESET_ALL)

    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    jalankan()
