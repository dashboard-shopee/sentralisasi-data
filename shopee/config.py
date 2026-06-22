"""
shopee/config.py — konfigurasi modul Shopee MANDIRI untuk Sentralisasi Data.

Modul ini SENGAJA berdiri sendiri (tidak impor dari folder "01/02/03") supaya
folder bot referensi tidak tersentuh. Pola di-copy dari referensi.
Chrome pakai port & profil SENDIRI (9560) — beda dari bot (9555/9556/9604).
"""

import os
from datetime import datetime
from pathlib import Path

import colorama; colorama.init()
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

# ── Browser (profil & port khusus modul sentralisasi) ──
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PORT = 9560
CHROME_USER_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__chrome_profile")

# ── Daftar 10 toko (urutan = posisi tombol Detail di shop switcher) ──
SHOP_DATABASE = {
    "kimmioshop": {"name": "Kimmioshop", "i": 1},
    "lolly0310": {"name": "lollysweet", "i": 2},
    "ravellashop": {"name": "Ravella Shop", "i": 3},
    "topikece2023": {"name": "Topikece Store", "i": 4},
    "alialiastore": {"name": "Alialia Store", "i": 5},
    "oliolio.id": {"name": "OLIOLIO.ID", "i": 6},
    "nomidestore": {"name": "NOMIDE STORE", "i": 7},
    "yarrastore": {"name": "YARRA STORE", "i": 8},
    "zioscarf": {"name": "ZIOSCARF SUPPLIER HIJAB IMPORT", "i": 9},
    "beverra": {"name": "BEVERRA OFFICIAL STORE", "i": 10},
}


def daftar_toko():
    return SHOP_DATABASE


def fmt_angka(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def log(pesan, warna="", baris_baru=False):
    awal = "\n" if baris_baru else ""
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{awal}{warna}[{waktu}] {pesan}{colorama.Style.RESET_ALL}")


# ── Template header API Shopee ──
SC_FE_VER = "21.142872"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36")
REFERER = "https://seller.shopee.co.id/datacenter/product/performance"


def grab_headers(session):
    return {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,id;q=0.8",
        "cookie": session["headers"]["cookie"],
        "priority": "u=1, i",
        "referer": REFERER,
        "sc-fe-session": session["headers"]["sc-fe-session"],
        "sc-fe-ver": SC_FE_VER,
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": USER_AGENT,
    }
