"""Helper request API Shopee: retry + validasi struktur respons (anti error transient/rate-limit)."""
import time
from modules.log_siklus import log
import requests


class AntiBotError(RuntimeError):
    """Endpoint kena anti-bot Shopee (butuh tanda-tangan SDK x-sap-sec) → GAGAL PERMANEN,
    retry percuma. Signature: error 90309999 / redirect_to_error_page. Caller mesti SKIP,
    bukan retry (mis. komisi & campaign-nominasi tertentu). Lihat modules/komisi_api.py."""


# Kode error Shopee yang = gagal permanen (anti-bot) → jangan retry, langsung nyerah.
_ANTI_BOT_ERR = {90309999}


def _cek_anti_bot(data):
    """True kalau respons = interstitial anti-bot Shopee (percuma di-retry)."""
    if not isinstance(data, dict):
        return False
    return data.get("error") in _ANTI_BOT_ERR or bool(data.get("redirect_to_error_page"))


def _valid(data, kunci):
    # respons normal = dict yang punya `kunci` berisi dict (mis. 'data' / 'result')
    return isinstance(data, dict) and isinstance(data.get(kunci), dict)


def _minta(method, url, headers, params, payload, kunci, attempts):
    delay = 2
    cuplikan = ''
    # timeout TUPLE (connect, read): connect 15s biar SSL-handshake yg gantung
    # (bug hang di Windows) diabort cepat, read 60s utk respons besar.
    TO = (15, 60)
    for attempt in range(attempts):
        try:
            if method == 'get':
                r = requests.get(url, headers=headers, params=params, timeout=TO)
            elif method == 'put':
                r = requests.put(url, headers=headers, params=params, json=payload, timeout=TO)
            else:
                r = requests.post(url, headers=headers, params=params, json=payload, timeout=TO)
            try:
                data = r.json()
            except ValueError:
                cuplikan = f'HTTP {r.status_code}, bukan JSON: {r.text[:200]}'
            else:
                if _valid(data, kunci):
                    return data
                if _cek_anti_bot(data):
                    # gagal permanen (anti-bot) → JANGAN retry, langsung nyerah biar ga badai.
                    raise AntiBotError(
                        f'Endpoint kena anti-bot Shopee (error {data.get("error")}) di {url} — '
                        f'butuh tanda-tangan SDK, ga bisa via requests. SKIP.')
                cuplikan = f'HTTP {r.status_code}: {str(data)[:250]}'
        except requests.RequestException as e:
            cuplikan = f'{type(e).__name__}: {e}'
        if attempt < attempts - 1:
            log(f'respons API tidak valid → {cuplikan} | coba lagi dalam {delay}s ({attempt+1}/{attempts-1})', level="warning", modul="api")
            time.sleep(delay); delay = min(delay * 2, 10)   # cap backoff 10s (dari 20) biar ga nunggu kelamaan
    raise RuntimeError(f'Respons API tidak valid dari {url} (kunci "{kunci}"). Terakhir: {cuplikan}')


def api_post(url, headers, params, payload, kunci='data', attempts=4):
    return _minta('post', url, headers, params, payload, kunci, attempts)


def api_get(url, headers, params, kunci='result', attempts=4):
    return _minta('get', url, headers, params, None, kunci, attempts)


def api_put(url, headers, params, payload, kunci='data', attempts=4):
    return _minta('put', url, headers, params, payload, kunci, attempts)
