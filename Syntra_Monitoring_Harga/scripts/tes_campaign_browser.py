"""scripts/tes_campaign_browser.py — ISOLASI: diagnosa kenapa campaign_util.api_post_browser
(fetch via run_js di browser) gagal (live test 15 Jul: percobaan-1 "js result parsing error",
percobaan berikutnya "Failed to fetch"). READ-ONLY, GA nyambung ke tes_harga.bat / siklus live
— jalanin manual sampe ketemu caranya yang stabil, baru sambungin balik ke campaign_util.py.

Nyoba 2 varian:
  [1] ORIGINAL — return object langsung dari fetch().then(r=>r.json()) (versi campaign_util.py
      sekarang). DrissionPage parse generic JS object via CDP Runtime.getProperties — ini yang
      diduga jadi biang "js result parsing error".
  [2] JSON.stringify — return STRING dari JS (json.dumps-kan di sisi browser), py-side json.loads()
      balik. Ngindarin CDP object-walking yang (diduga) buggy.

Jalanin: python scripts/tes_campaign_browser.py
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from modules.session import grab_session, close_session, buka_page_toko, tutup_page, get_page
from modules import campaign_util as CU

TOKO = "kimmioshop"

JS_ORIGINAL = """
const url = arguments[0];
const payload = arguments[1];
return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*'}
    , body: JSON.stringify(payload)
}).then(response => {
    if (!response.ok) { return { 'error': 'HTTP error ' + response.status, 'status': response.status }; }
    return response.json();
}).catch(error => { return { 'error': error.message }; });
"""

JS_STRINGIFY = """
const url = arguments[0];
const payload = arguments[1];
return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*'}
    , body: JSON.stringify(payload)
}).then(response => {
    return response.text().then(txt => JSON.stringify({status: response.status, ok: response.ok, body: txt}));
}).catch(error => { return JSON.stringify({error: String(error && error.message || error)}); });
"""


def _coba(label, js, url, params, payload):
    from urllib.parse import urlencode
    page = get_page()
    full_url = url + ("&" if "?" in url else "?") + urlencode(params)
    print(f"\n--- [{label}] {full_url[:120]}...")
    try:
        res = page.run_js(js, full_url, payload)
        print(f"[{label}] TYPE={type(res)} RAW={str(res)[:600]}")
        return res
    except Exception as e:
        print(f"[{label}] EXCEPTION: {type(e).__name__}: {str(e)[:400]}")
        return None


def main():
    info = config.SHOP_DATABASE[TOKO]
    session = grab_session(shop=TOKO, i=info["i"])
    idx = info["i"]

    buka_page_toko(TOKO, idx)
    page = get_page()
    print("mengarahkan browser ke Portal Campaign…")
    page.get("https://seller.shopee.co.id/portal/marketing/cmt/campaign?source=2")
    page.wait(2)

    payload = {"campaign_scene": [], "view_flag": 1,
               "pagination": {"offset": 0, "limit": 50, "sort_type": 9}, "sc_page": 0}

    r1 = _coba("ORIGINAL", JS_ORIGINAL, config.URL_GET_LANDING_CAMPAIGN, session["params"], payload)
    r2 = _coba("STRINGIFY", JS_STRINGIFY, config.URL_GET_LANDING_CAMPAIGN, session["params"], payload)
    if isinstance(r2, str):
        try:
            parsed = json.loads(r2)
            print(f"[STRINGIFY] json.loads OK — status={parsed.get('status')} ok={parsed.get('ok')} body_len={len(parsed.get('body') or '')}")
            if parsed.get("body"):
                try:
                    body_json = json.loads(parsed["body"])
                    print(f"[STRINGIFY] body code={body_json.get('code')} message={body_json.get('message')}")
                except Exception:
                    print(f"[STRINGIFY] body bukan JSON valid, cuplikan: {parsed['body'][:300]}")
        except Exception as e:
            print(f"[STRINGIFY] json.loads GAGAL: {e}")

    tutup_page()
    close_session()
    print("\nSELESAI. Bandingin [ORIGINAL] vs [STRINGIFY] di atas — pilih yang datanya kebaca bener.")


if __name__ == "__main__":
    main()
