"""shopee/api.py — wrapper request API Shopee (retry + validasi). Copy pola dari referensi."""

import time

import colorama; colorama.init()
import requests

from shopee import config


class SesiKedaluwarsa(RuntimeError):
    """Sesi Shopee tidak sah / belum login (401 / 'not login' / 'permission denied')."""


def _valid(data, kunci):
    return isinstance(data, dict) and isinstance(data.get(kunci), dict)


def _auth_gagal(status, data):
    if status == 401:
        return True
    if isinstance(data, dict):
        if "not login" in str(data.get("result", "")).lower():
            return True
        if "permission denied" in str(data.get("msg", "")).lower():
            return True
    return False


def _minta(method, url, headers, params, payload, kunci, attempts):
    delay = 2
    cuplikan = ""
    for attempt in range(attempts):
        try:
            if method == "get":
                r = requests.get(url, headers=headers, params=params, timeout=30)
            else:
                r = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
            try:
                data = r.json()
            except ValueError:
                cuplikan = f"HTTP {r.status_code}, bukan JSON: {r.text[:200]}"
            else:
                if _valid(data, kunci):
                    return data
                cuplikan = f"HTTP {r.status_code}: {str(data)[:250]}"
                if _auth_gagal(r.status_code, data):
                    raise SesiKedaluwarsa(f"Sesi tidak sah dari {url}. Terakhir: {cuplikan}")
        except requests.RequestException as e:
            cuplikan = f"{type(e).__name__}: {e}"
        if attempt < attempts - 1:
            config.log(f"[api] respons tidak valid -> {cuplikan} | coba lagi {delay}s ({attempt+1}/{attempts-1})",
                       colorama.Fore.RED)
            time.sleep(delay); delay = min(delay * 2, 20)
    raise RuntimeError(f'Respons API tidak valid dari {url} (kunci "{kunci}"). Terakhir: {cuplikan}')


def api_post(url, headers, params, payload, kunci="data", attempts=4):
    return _minta("post", url, headers, params, payload, kunci, attempts)


def api_get(url, headers, params, kunci="result", attempts=4):
    return _minta("get", url, headers, params, None, kunci, attempts)
