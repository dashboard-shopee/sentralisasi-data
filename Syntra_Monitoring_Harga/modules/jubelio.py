"""modules/jubelio.py — ambil HPP (last_cogs) dari Jubelio -> erp_sku_list.hpp.

Metode (cepat, sesuai mau user):
  1. TOKEN: JWT diambil dari localStorage __SNID__ Jubelio. Browser dibuka SEKALI
     (port 9557, profil __jubelio_profile), baca token, tutup. Token valid ~12 jam ->
     di-cache (__jubelio_token.json) -> browser cuma kebuka lagi kalau token expired.
  2. DATA: inventory ditarik via API murni (Authorization: Bearer <token>), paginasi.
     Jubelio TANPA OTP. item_code Jubelio == erp_sku_list.sku (match langsung).

Dipanggil tiap Fase 1 (grab). Fetch ~11rb SKU = beberapa detik (pure API).
"""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import colorama; colorama.init()
from sqlalchemy import text

from modules.db import get_engine

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / "__jubelio_token.json"
PROFILE = str(ROOT / "__jubelio_profile")
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9557
INV_URL = "https://open.jubelio.com/core-api/inventory/v2/"


def _harvest_token():
    """Buka browser Jubelio -> baca token dari localStorage __SNID__ -> tutup."""
    import DrissionPage
    o = DrissionPage.ChromiumOptions()
    o.set_browser_path(CHROME_PATH)
    o.set_local_port(PORT)
    o.set_user_data_path(PROFILE)
    page = DrissionPage.ChromiumPage(o)
    try:
        page.get("https://v2.jubelio.com/inventory/stock_position/total")
        page.wait(4)
        raw = page.run_js("return window.localStorage.getItem('__SNID__')")
        if not raw:
            raise RuntimeError("Token Jubelio kosong (localStorage __SNID__). Login dulu: python sniff_jubelio.py")
        snid = json.loads(raw)
        tok = {"token": snid["token"], "expiredOn": snid.get("expiredOn")}
        TOKEN_FILE.write_text(json.dumps(tok), encoding="utf-8")
        print(colorama.Fore.GREEN + f"[jubelio] token dipanen (exp {tok['expiredOn']})" + colorama.Style.RESET_ALL)
        return tok["token"]
    finally:
        try:
            page.quit()
        except Exception:
            pass
        time.sleep(2)


def _token_valid(tok):
    exp = tok.get("expiredOn")
    if not exp:
        return False
    try:
        e = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < e - timedelta(minutes=15)  # buffer
    except Exception:
        return False


def get_token(paksa=False):
    """Token valid dari cache; kalau expired/tdk ada -> panen ulang via browser."""
    if not paksa and TOKEN_FILE.exists():
        try:
            tok = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            if _token_valid(tok):
                return tok["token"]
        except Exception:
            pass
    return _harvest_token()


def ambil_semua_hpp(token, page_size=500):
    """Paginasi inventory Jubelio -> {item_code: last_cogs(float)}."""
    h = {"Accept": "application/json", "Authorization": "Bearer " + token}
    peta = {}
    page = 1
    while True:
        r = requests.get(INV_URL, params={"page": page, "page_size": page_size, "sort_direction": "NONE"},
                         headers=h, timeout=60)
        j = r.json()
        items = j.get("data") or []
        for it in items:
            code = (it.get("item_code") or "").strip()
            cogs = it.get("last_cogs")
            if code and cogs not in (None, ""):
                try:
                    peta[code] = float(cogs)
                except (TypeError, ValueError):
                    pass
        total = int(j.get("totalCount") or 0)
        if not items or page * page_size >= total or page > 200:
            break
        page += 1
    return peta


def simpan_hpp_ke_erp(peta):
    """Update erp_sku_list.hpp untuk sku yang cocok. Return jumlah sku ter-update."""
    if not peta:
        return 0
    rows = [{"sku": k, "hpp": v} for k, v in peta.items()]
    n = 0
    with get_engine().begin() as c:
        for i in range(0, len(rows), 1000):
            batch = rows[i:i + 1000]
            res = c.execute(text("update erp_sku_list set hpp = :hpp where sku = :sku"), batch)
            n += res.rowcount or 0
    return n


def sync_hpp():
    """Orkestrator: token -> tarik semua HPP -> simpan ke erp_sku_list.hpp."""
    token = get_token()
    peta = ambil_semua_hpp(token)
    n = simpan_hpp_ke_erp(peta)
    print(colorama.Fore.LIGHTGREEN_EX
          + f"[jubelio] HPP: {len(peta)} sku ditarik, {n} ter-update di erp_sku_list" + colorama.Style.RESET_ALL)
    return len(peta), n


if __name__ == "__main__":
    sync_hpp()
