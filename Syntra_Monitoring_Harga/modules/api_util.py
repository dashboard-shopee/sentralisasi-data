"""Helper request API Shopee: retry + validasi struktur respons (anti error transient/rate-limit)."""
import time
import colorama; colorama.init()
import requests


def _valid(data, kunci):
    # respons normal = dict yang punya `kunci` berisi dict (mis. 'data' / 'result')
    return isinstance(data, dict) and isinstance(data.get(kunci), dict)


def _minta(method, url, headers, params, payload, kunci, attempts):
    delay = 2
    cuplikan = ''
    for attempt in range(attempts):
        try:
            if method == 'get':
                r = requests.get(url, headers=headers, params=params, timeout=60)
            else:
                r = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
            try:
                data = r.json()
            except ValueError:
                cuplikan = f'HTTP {r.status_code}, bukan JSON: {r.text[:200]}'
            else:
                if _valid(data, kunci):
                    return data
                cuplikan = f'HTTP {r.status_code}: {str(data)[:250]}'
        except requests.RequestException as e:
            cuplikan = f'{type(e).__name__}: {e}'
        if attempt < attempts - 1:
            print(colorama.Fore.RED + f'[api] respons tidak valid -> {cuplikan} | coba lagi dalam {delay}s ({attempt+1}/{attempts-1})' + colorama.Style.RESET_ALL)
            time.sleep(delay); delay = min(delay * 2, 20)
    raise RuntimeError(f'Respons API tidak valid dari {url} (kunci "{kunci}"). Terakhir: {cuplikan}')


def api_post(url, headers, params, payload, kunci='data', attempts=4):
    return _minta('post', url, headers, params, payload, kunci, attempts)


def api_get(url, headers, params, kunci='result', attempts=4):
    return _minta('get', url, headers, params, None, kunci, attempts)
