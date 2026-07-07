"""sniff_voucher.py — auto-capture endpoint LIST voucher Shopee.

`voucher/list/` (dipakai modules/voucher.list_vouchers) balik ERROR_PARAM utk semua
tebakan param. Skrip ini buka halaman Voucher di Seller Center, nangkep request API
voucher yang firing saat load (params + body + response ASLI) -> tinggal disalin ke config.

Cara pakai (login dulu: python run.py login):
  python sniff_voucher.py

Hasil: __sniff_voucher.json + langsung dicetak request 'voucher/list' yang ketangkep.
Kalau kosong: buka manual tab "Voucher Saya" / ganti filter di browser yg kebuka,
lalu jalankan lagi (atau tekan ENTER pas diminta setelah halaman voucher tampil).
"""
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage

# Halaman voucher Seller Center (SPA). Kalau redirect ke pemilih-akun, navigasi MANUAL
# di browser yg kebuka ke: Marketing Centre -> Voucher Toko Saya (skrip nangkep semua tab).
URL_VOUCHER_PAGE = "https://seller.shopee.co.id/portal/marketing/voucher"


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

    print(colorama.Fore.YELLOW + f"[sniff voucher] buka {URL_VOUCHER_PAGE} ..." + colorama.Style.RESET_ALL)
    page.get(URL_VOUCHER_PAGE)
    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Halaman VOUCHER lagi kebuka. Diemin ~10 detik biar daftar voucher ke-load
  (request voucher/list bakal ketangkep otomatis).
  Kalau daftar belum muncul: klik tab "Voucher Saya" / ganti filter status
  (Sedang Berlangsung / Akan Datang) SEKALI di browser.
  Selesai? Balik ke sini & tekan ENTER (atau tunggu auto 2 menit).
================================================================
""" + colorama.Style.RESET_ALL)

    # auto-stop 120s kalau user gak tekan ENTER
    done = threading.Event()
    def _tunggu_enter():
        try:
            input("Tekan ENTER kalau daftar voucher udah tampil... ")
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

    # kumpulkan semua request voucher
    vouchers = []
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
            if "voucher" in url.lower():
                vouchers.append(item)
        except Exception:
            pass

    with open("__sniff_voucher.json", "w", encoding="utf-8") as f:
        json.dump({"voucher_requests": vouchers, "semua_api": semua}, f, ensure_ascii=False, indent=2)

    print(colorama.Fore.GREEN + f"\n[sniff] {len(semua)} request API, {len(vouchers)} nyerempet 'voucher' -> __sniff_voucher.json" + colorama.Style.RESET_ALL)
    for v in vouchers:
        base = v["url"].split("?")[0]
        code = (v["response"] or {}).get("code") if isinstance(v["response"], dict) else "?"
        print(colorama.Fore.CYAN + f"  {v['method']:4} {base}  (resp code={code})" + colorama.Style.RESET_ALL)
        if "list" in base.lower() or "get" in base.lower():
            print(colorama.Fore.WHITE + f"       params: {json.dumps(v['params'], ensure_ascii=False)[:300]}" + colorama.Style.RESET_ALL)
            print(colorama.Fore.WHITE + f"       body  : {json.dumps(v['body'], ensure_ascii=False)[:300]}" + colorama.Style.RESET_ALL)

    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    jalankan()
