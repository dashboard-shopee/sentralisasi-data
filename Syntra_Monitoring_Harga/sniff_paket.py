"""sniff_paket.py — auto-capture endpoint LIST paket diskon (bundle_deal) Shopee.

`bundle_deal/list/` (dipakai modules/paket_diskon.list_deals) balik KOSONG (code=0 tapi 0 deal)
walau jelas ada paket → kemungkinan butuh param/pagination yg belum dikirim. Skrip ini buka
halaman Paket Diskon di Seller Center, nangkep request API bundle_deal yang firing saat load
(method + params + body + response ASLI) -> tinggal disalin ke paket_diskon.list_deals.

Cara pakai (login dulu: python run.py login):
  python sniff_paket.py

Hasil: __sniff_paket.json + langsung dicetak request 'bundle_deal' yang ketangkep.
Kalau kosong: klik tab "Paket Diskon" / ganti filter status di browser yg kebuka,
lalu tekan ENTER pas diminta.
"""
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage

# Halaman Paket Diskon Seller Center (SPA). Kalau redirect ke pemilih-akun, navigasi MANUAL
# di browser yg kebuka ke: Marketing Centre -> Paket Diskon (skrip nangkep semua tab).
URL_PAKET_PAGE = "https://seller.shopee.co.id/portal/marketing/bundle"


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

    print(colorama.Fore.YELLOW + f"[sniff paket] buka {URL_PAKET_PAGE} ..." + colorama.Style.RESET_ALL)
    page.get(URL_PAKET_PAGE)
    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Halaman PAKET DISKON lagi kebuka. Diemin ~10 detik biar daftar paket ke-load
  (request bundle_deal/list bakal ketangkep otomatis).
  Kalau daftar belum muncul: klik tab "Paket Diskon" / ganti filter status
  (Sedang Berjalan / Akan Datang / Semua) SEKALI di browser.
  Selesai? Balik ke sini & tekan ENTER (atau tunggu auto 2 menit).
================================================================
""" + colorama.Style.RESET_ALL)

    # auto-stop 120s kalau user gak tekan ENTER
    done = threading.Event()
    def _tunggu_enter():
        try:
            input("Tekan ENTER kalau daftar paket udah tampil... ")
        except (EOFError, OSError):
            return
        done.set()
    threading.Thread(target=_tunggu_enter, daemon=True).start()
    for _ in range(240):
        if done.is_set():
            break
        time.sleep(0.5)

    stop.set()
    time.sleep(0.5)

    # kumpulkan semua request bundle_deal
    deals = []
    semua = []
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
            if "bundle_deal" in url.lower():
                deals.append(item)
        except Exception:
            pass

    with open("__sniff_paket.json", "w", encoding="utf-8") as f:
        json.dump({"bundle_deal_requests": deals, "semua_api": semua}, f, ensure_ascii=False, indent=2)

    print(colorama.Fore.GREEN + f"\n[sniff] {len(semua)} request API, {len(deals)} nyerempet 'bundle_deal' -> __sniff_paket.json" + colorama.Style.RESET_ALL)
    for v in deals:
        base = v["url"].split("?")[0]
        code = (v["response"] or {}).get("code") if isinstance(v["response"], dict) else "?"
        print(colorama.Fore.CYAN + f"  {v['method']:4} {base}  (resp code={code})" + colorama.Style.RESET_ALL)
        if "list" in base.lower():
            print(colorama.Fore.WHITE + f"       params: {json.dumps(v['params'], ensure_ascii=False)[:400]}" + colorama.Style.RESET_ALL)
            print(colorama.Fore.WHITE + f"       body  : {json.dumps(v['body'], ensure_ascii=False)[:400]}" + colorama.Style.RESET_ALL)
            resp = v["response"] if isinstance(v["response"], dict) else {}
            data = resp.get("data") if isinstance(resp, dict) else None
            keys = list(data.keys()) if isinstance(data, dict) else ("<list>" if isinstance(data, list) else "?")
            print(colorama.Fore.WHITE + f"       resp.data keys: {keys}" + colorama.Style.RESET_ALL)

    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    jalankan()
