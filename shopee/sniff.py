"""
shopee/sniff.py — SNIFFER API Shopee Seller (modul mandiri sentralisasi).

Buka browser (profil sentralisasi yang sudah login), nangkep SEMUA request ke
`/api/` selama beberapa menit sambil kamu browsing, lalu simpan tiap request
(URL + params + response) ke folder data/sniff/. Setelah itu Claude baca file-nya
untuk menemukan endpoint yang dibutuhkan (mis. total pesanan per toko).

Jalankan (setelah re-backfill selesai biar Chrome tidak rebutan):
    python -m shopee.sniff
Lalu di Chrome yang terbuka: buka halaman yang menampilkan TOTAL PESANAN toko
(menu Data / Bisnis / Analisis Penjualan), klik-klik & ganti tanggal.
Sniffer berhenti otomatis setelah DURASI detik.
"""

import json
import re
import time
from pathlib import Path

import colorama; colorama.init()
import DrissionPage

from shopee.session import _buat_options

DURASI = 120  # detik menangkap
OUT = Path(__file__).resolve().parents[1] / "data" / "sniff"


def _simpan(packet):
    url = packet.url
    if "/api/" not in url:
        return None
    try:
        body = packet.response.body
    except Exception:
        body = None
    data = {
        "url": url,
        "method": getattr(packet.request, "method", "?"),
        "params": dict(getattr(packet.request, "params", {}) or {}),
        "postData": getattr(packet.request, "postData", None),
        "response": body,
    }
    nama = re.sub(r"[^A-Za-z0-9]+", "_", url.split("?")[0].split("shopee.co.id")[-1]).strip("_")[:90] or "root"
    teks = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    (OUT / f"{nama}.json").write_text(teks[:300000], encoding="utf-8")
    return url


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()  # bersihkan hasil lama

    page = DrissionPage.ChromiumPage(_buat_options()); page.set.window.max()
    page.get("https://seller.shopee.co.id/datacenter/dashboard")
    print(colorama.Fore.LIGHTCYAN_EX +
          f"\nSNIFFER AKTIF {DURASI} detik. Di Chrome: buka halaman yang menampilkan "
          "TOTAL PESANAN toko (Data / Bisnis / Analisis Penjualan), klik-klik & ganti tanggal.\n" +
          colorama.Style.RESET_ALL)

    page.listen.start("seller.shopee.co.id/api/")
    seen = set()
    end = time.time() + DURASI
    try:
        for packet in page.listen.steps(timeout=DURASI):
            u = _simpan(packet)
            if u and u.split("?")[0] not in seen:
                seen.add(u.split("?")[0])
                tag = ""
                low = u.lower()
                if any(k in low for k in ("order", "sales", "overview", "dashboard", "income")):
                    tag = colorama.Fore.GREEN + "  <-- mungkin ini!" + colorama.Style.RESET_ALL
                print(f"  tangkap: {u.split('?')[0]}{tag}")
            if time.time() >= end:
                break
    finally:
        page.listen.stop()
        page.quit()
    print(colorama.Fore.LIGHTGREEN_EX +
          f"\nSelesai. {len(seen)} endpoint unik tersimpan di data/sniff/. Kabari Claude untuk dibaca." +
          colorama.Style.RESET_ALL)


if __name__ == "__main__":
    main()
