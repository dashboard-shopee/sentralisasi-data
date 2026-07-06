"""sniff_komisi.py — Penyadap API KOMISI (dan promo lain) di browser TERPISAH.

Beda dari sniff_promo.py:
  - PORT 9600 + PROFIL BARU (tidak bentrok dgn bot Syntra Harga port 9556).
  - Inject cookies dari file (login instan), bisa juga login manual di jendela.
  - Rekam request (params + HEADER, penting utk analisa anti-bot) + response
    SEMUA panggilan /api, dump LIVE tiap 2 detik ke JSON (bisa dibaca sambil jalan).

Cara pakai:
  python sniff_komisi.py <cookies_json> <out_json> <stop_file>
  -> buka jendela Chrome (logged-in). Lakukan aksi komisi manual (pasang/takedown).
  -> berhenti kalau <stop_file> muncul, atau 30 menit, atau tab ditutup.
"""
import sys, os, json, time, threading
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass
import colorama; colorama.init()
import DrissionPage
import config

PORT = 9601
COOKIES_FILE = sys.argv[1]
OUT = sys.argv[2]
STOP = sys.argv[3]
PROFILE = os.path.join(os.path.dirname(OUT), "komisi_profile2")

# endpoint yg PALING penting di-highlight (tetep rekam semua /api).
_PENTING = ("affiliateplatform", "discount", "flash_sale", "bundle_deal", "campaign")


def _opts():
    o = DrissionPage.ChromiumOptions()
    o.set_argument("--force-device-scale-factor=0.8")
    if getattr(config, "CHROME_PATH", ""):
        o.set_browser_path(config.CHROME_PATH)
    o.set_local_port(PORT)
    o.set_user_data_path(PROFILE)
    return o


def _clean_cookies(raw):
    out = []
    for c in raw:
        d = {"name": c["name"], "value": c["value"],
             "domain": c["domain"], "path": c.get("path", "/")}
        if c.get("secure"):   d["secure"] = True
        if c.get("httpOnly"): d["httpOnly"] = True
        if c.get("expirationDate"): d["expires"] = c["expirationDate"]
        ss = str(c.get("sameSite", "")).lower()
        if ss in ("strict", "lax", "none"):
            d["sameSite"] = ss.capitalize()
        out.append(d)
    return out


def _as_json(x):
    if x is None: return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(x)
    except Exception: return str(x)[:4000]


def _dump(paket):
    keluaran = []
    for p in paket:
        try:
            url = p.url
            if "/api/" not in url:
                continue
            keluaran.append({
                "url": url,
                "method": getattr(p, "method", ""),
                "request_params": _as_json(getattr(p.request, "params", None)),
                "request_headers": dict(getattr(p.request, "headers", {}) or {}),
                "request_body": _as_json(getattr(p.request, "postData", None)),
                "response": _as_json(getattr(p.response, "body", None)),
            })
        except Exception as e:
            keluaran.append({"error": str(e)})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    return len(keluaran)


def _watch(page, paket, stop_event):
    attached = set()

    def _sniff_tab(tab):
        try:
            tab.listen.start("seller.shopee.co.id/api")
            for p in tab.listen.steps():
                paket.append(p)
                u = getattr(p, "url", "")
                if any(k in u for k in _PENTING):
                    print(colorama.Fore.CYAN + f"[sniff] {getattr(p,'method','')} {u.split('?')[0].split('/api/')[-1]}" + colorama.Style.RESET_ALL)
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
                    t = page.get_tab(tid); attached.add(tid)
                    threading.Thread(target=_sniff_tab, args=(t,), daemon=True).start()
                    print(colorama.Fore.GREEN + f"[sniff] tab BARU nyambung (total {len(attached)} tab dipantau)" + colorama.Style.RESET_ALL)
                except Exception:
                    pass
        time.sleep(0.2)   # poll cepat biar tab baru langsung ke-attach (gak kelewat request awal)


def main():
    raw = json.load(open(COOKIES_FILE, encoding="utf-8"))
    cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw
    page = DrissionPage.ChromiumPage(_opts())
    try:
        page.set.window.max()
    except Exception:
        pass
    print(colorama.Fore.YELLOW + "[sniff komisi] buka seller.shopee.co.id..." + colorama.Style.RESET_ALL)
    page.get("https://seller.shopee.co.id/")
    try:
        page.set.cookies(_clean_cookies(cookies))
        print(colorama.Fore.GREEN + f"[sniff komisi] {len(cookies)} cookies di-inject." + colorama.Style.RESET_ALL)
    except Exception as e:
        print(colorama.Fore.RED + f"[sniff komisi] inject cookies gagal: {e} (login manual aja di jendela)" + colorama.Style.RESET_ALL)
    page.get("https://seller.shopee.co.id/portal/shop")

    paket, stop_event = [], threading.Event()
    threading.Thread(target=_watch, args=(page, paket, stop_event), daemon=True).start()

    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  BROWSER SIAP (port 9600, profil terpisah). BATCH CAPTURE PROMO:
  Lakukan aksi SAVE (sampai notif berhasil) buat tiap jenis:
    [A] GARANSI HARGA TERBAIK -> nonaktifin/opt-out 1 produk
    [B] FLASH SALE TOKO       -> keluarin 1 produk dari sesi
    [C] PAKET DISKON/Add-on    -> hapus 1 produk dari paket
    [D] VOUCHER               -> ubah/hapus 1 voucher
    (+ jenis lain yg mau ditangkep)
  [PENTING] WAJIB klik SIMPAN/KONFIRMASI sampai notif berhasil (bukan cuma buka).
  Semua request+response ke-rekam LIVE. Kelar? bilang ke Claude.
================================================================
""" + colorama.Style.RESET_ALL)

    t0 = time.time()
    while time.time() - t0 < 3600:          # maks 60 menit (atau sampai file STOP)
        n = _dump(list(paket))
        if os.path.exists(STOP):
            print(colorama.Fore.YELLOW + "[sniff komisi] STOP terdeteksi." + colorama.Style.RESET_ALL); break
        time.sleep(2)
    stop_event.set()
    n = _dump(list(paket))
    print(colorama.Fore.GREEN + f"[sniff komisi] SELESAI. {n} request /api tersimpan ke {OUT}" + colorama.Style.RESET_ALL)
    try: page.quit()
    except Exception: pass


if __name__ == "__main__":
    main()
