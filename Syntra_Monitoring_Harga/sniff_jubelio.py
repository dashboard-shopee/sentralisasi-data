"""sniff_jubelio.py — TANGKAP API Jubelio (login + inventory/HPP).

Tujuan: tahu cara auth Jubelio (token dari login email+password) supaya HPP bisa
ditarik CEPAT via requests TANPA browser (Jubelio tidak pakai OTP).

Cara pakai:
  python sniff_jubelio.py
  1. Jendela Chrome kebuka -> LOGIN manual (email + password Jubelio).
  2. Setelah masuk, script otomatis muat halaman stock position (memicu API inventory).
  3. Semua request/response domain jubelio ditulis ke __sniff_jubelio.json.
  4. Kirim file itu ke sini -> gua bikin fetcher HPP-nya.

Browser TERPISAH (port 9557 + profil __jubelio_profile) biar tak ganggu profil Shopee (9556).
"""
import json
import time
from pathlib import Path

import colorama; colorama.init()
import DrissionPage

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9557
PROFILE = str(Path(__file__).resolve().parent / "__jubelio_profile")
TARGET_URL = "https://v2.jubelio.com/inventory/stock_position/total"
INV_API = ("https://open.jubelio.com/core-api/inventory/v2/"
           "?page=1&page_size=25&sort_direction=NONE&q=aks28")
OUT = Path(__file__).resolve().parent / "__sniff_jubelio.json"


def _opts():
    o = DrissionPage.ChromiumOptions()
    o.set_browser_path(CHROME_PATH)
    o.set_local_port(PORT)
    o.set_user_data_path(PROFILE)
    return o


def _potong(s, n=4000):
    s = str(s)
    return s if len(s) <= n else s[:n] + f"...(+{len(s)-n} char)"


def _rekam(pkt):
    req = getattr(pkt, "request", None)
    res = getattr(pkt, "response", None)
    body = None
    try:
        body = res.body if res is not None else None
    except Exception:
        body = "(gagal baca body)"
    return {
        "url": getattr(pkt, "url", ""),
        "method": getattr(req, "method", "") if req else "",
        "req_headers": dict(getattr(req, "headers", {}) or {}) if req else {},
        "req_params": dict(getattr(req, "params", {}) or {}) if req else {},
        "req_body": _potong(getattr(req, "postData", "") or "") if req else "",
        "status": getattr(res, "status", "") if res else "",
        "res_body": _potong(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False) if body is not None else ""),
    }


def main():
    page = DrissionPage.ChromiumPage(_opts())
    try:
        page.set.window.max()
    except Exception:
        pass
    # Tangkap SEMUA request ke domain jubelio (login + token + inventory).
    page.listen.start("jubelio.com")
    page.get(TARGET_URL)

    print(colorama.Fore.LIGHTCYAN_EX
          + "\n>> LOGIN Jubelio (kalau diminta)."
          + "\n>> Di halaman Stock Position: KETIK SKU 'aks28' (atau apa saja) di kolom SEARCH,"
          + "\n   tekan Enter, TUNGGU sampai hasilnya muncul. (ini yg memicu API + token)"
          + colorama.Style.RESET_ALL)
    input(">> Tekan ENTER di terminal SETELAH data hasil search muncul... ")
    time.sleep(2)

    # AMBIL TOKEN langsung dari browser (localStorage/sessionStorage/cookies) — paling andal.
    auth = {}
    for nama, js in (("localStorage", "return JSON.stringify(window.localStorage)"),
                     ("sessionStorage", "return JSON.stringify(window.sessionStorage)")):
        try:
            auth[nama] = page.run_js(js)
        except Exception as e:
            auth[nama] = f"(gagal: {e})"
    try:
        ck = page.cookies(as_dict=True)
        auth["cookies"] = ck if isinstance(ck, dict) else dict(ck)
    except Exception as e:
        auth["cookies"] = f"(gagal: {e})"
    (Path(__file__).resolve().parent / "__sniff_jubelio_auth.json").write_text(
        json.dumps(auth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(colorama.Fore.GREEN + ">> Token/cookie disimpan ke __sniff_jubelio_auth.json" + colorama.Style.RESET_ALL)

    # Kumpulkan semua paket yang tertangkap.
    rekaman = []
    try:
        for pkt in page.listen.steps(count=0, timeout=3):
            rekaman.append(_rekam(pkt))
    except Exception:
        pass
    # cadangan: ambil sisa via wait
    try:
        sisa = page.listen.wait(count=50, timeout=3, fit_count=False)
        if sisa:
            for pkt in (sisa if isinstance(sisa, list) else [sisa]):
                rekaman.append(_rekam(pkt))
    except Exception:
        pass

    page.listen.stop()
    try:
        page.quit()
    except Exception:
        pass

    # buang duplikat berdasarkan url+method
    uniq = {}
    for r in rekaman:
        uniq[(r["url"], r["method"])] = r
    hasil = list(uniq.values())
    OUT.write_text(json.dumps(hasil, ensure_ascii=False, indent=2), encoding="utf-8")
    print(colorama.Fore.GREEN + f"\n>> {len(hasil)} request Jubelio tersimpan ke {OUT.name}" + colorama.Style.RESET_ALL)
    # ringkas yang penting di terminal
    for r in hasil:
        if any(k in r["url"].lower() for k in ("login", "auth", "token", "inventory", "core-api")):
            print(f"   [{r['method']}] {r['url'][:90]}  (status {r['status']})")


if __name__ == "__main__":
    main()
