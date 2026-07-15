"""sniff_flash_hapus.py — sniff endpoint HAPUS sesi flash sale (beda dari STOP/akhiri).

Konteks (grilling 15 Jul): sesi flash yang di-STOP (set_shop_flash_sale status=2, sudah
terverifikasi jalan) TIDAK OTOMATIS bikin slot jamnya bisa dipakai lagi buat sesi baru.
Shopee Seller Center kemungkinan punya aksi "Hapus" terpisah (dari list sesi yang statusnya
udah Berakhir/Nonaktif) yang BENERAN ngosongin slot. Endpoint ini yang mau ditangkep.

Cara pakai (login dulu kalau sesi lama: python run.py login):
  python sniff_flash_hapus.py

Hasil: __sniff_flash_hapus.json + endpoint yang ketangkep dicetak ke layar.
"""
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage


def _ringkas_nilai(v, _depth=0):
    if isinstance(v, dict):
        return {k: _ringkas_nilai(val, _depth + 1) for k, val in v.items()}
    if isinstance(v, list):
        potong = v[:15]
        hasil = [_ringkas_nilai(x, _depth + 1) for x in potong]
        if len(v) > 15:
            hasil.append(f"...(+{len(v) - 15} item lagi, total {len(v)})")
        return hasil
    return v


def _as_json(x):
    if x is None:
        return None
    if isinstance(x, (dict, list)):
        return x
    try:
        return json.loads(x)
    except Exception:
        return str(x)[:2000]


def _simpan(paket, nama_file):
    keluaran = []
    for p in paket:
        try:
            url = p.url
            if "/api/" not in url:
                continue
            keluaran.append({
                "url": url,
                "method": getattr(p, "method", ""),
                "request_params": _ringkas_nilai(_as_json(getattr(p.request, "params", None))),
                "request_body": _ringkas_nilai(_as_json(getattr(p.request, "postData", None))),
                "response": _ringkas_nilai(_as_json(getattr(p.response, "body", None))),
            })
        except Exception as e:
            keluaran.append({"error": str(e)})
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    print(colorama.Fore.GREEN
          + f"\n[sniff] {len(keluaran)} request API tersimpan ke {nama_file}"
          + colorama.Style.RESET_ALL)
    seen = set()
    for k in keluaran:
        u = k.get("url", "")
        base = u.split("?")[0]
        if "/api/" in u and base not in seen:
            seen.add(base)
            print(colorama.Fore.CYAN + f"  - {k.get('method',''):4} {base}" + colorama.Style.RESET_ALL)


def _watcher_multitab(page, paket, stop_event):
    attached = set()

    def _sniff_tab(tab):
        try:
            tab.listen.start("seller.shopee.co.id/api")
            for p in tab.listen.steps():
                paket.append(p)
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
                    t = page.get_tab(tid)
                    attached.add(tid)
                    th = threading.Thread(target=_sniff_tab, args=(t,), daemon=True)
                    th.start()
                except Exception:
                    pass
        time.sleep(0.5)


def jalankan():
    page = DrissionPage.ChromiumPage(_buat_options())
    page.set.window.max()
    print(colorama.Fore.YELLOW + "[sniff flash hapus] membuka Marketing Centre..." + colorama.Style.RESET_ALL)
    page.get("https://seller.shopee.co.id/portal/marketing")

    paket = []
    stop_event = threading.Event()
    th = threading.Thread(target=_watcher_multitab, args=(page, paket, stop_event), daemon=True)
    th.start()

    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Tujuan: nangkep endpoint HAPUS sesi flash (BEDA dari stop/akhiri, yang udah
  ketangkep sebelumnya = set_shop_flash_sale status:2).

  Langkah:
  1. Buka menu Flash Sale Toko (biasanya di Marketing Centre -> Flash Sale Toko).
  2. Cari 1 sesi yang statusnya sudah BERAKHIR / NONAKTIF (atau akhirin dulu 1 sesi
     kalau belum ada yang berakhir).
  3. Cari tombol/menu titik-tiga di sesi itu -> apakah ada opsi "Hapus"?
     - Kalau ADA: klik Hapus -> KONFIRMASI di popup sampai sesi beneran hilang
       dari daftar / muncul notif "berhasil dihapus".
     - Kalau TIDAK ADA opsi hapus sama sekali (cuma ada Lihat/Akhiri): itu artinya
       Shopee MEMANG tidak punya fitur hapus terpisah — cukup tekan ENTER langsung,
       laporan bakal nunjukin 0 endpoint baru ketangkep (itu juga jawaban yang valid).
  4. (Opsional, buat mastiin slot beneran kebuka lagi) abis hapus, coba juga klik
     "Buat Sesi Baru" -> pilih jam yang PERSIS SAMA dengan slot sesi yang td dihapus
     -> lanjut sampai step pilih produk (ga usah sampai submit produk, cukup sampai
     Shopee ngizinin/nolak milih slot itu lagi) -> baru ENTER di sini.

  Selesai? Balik ke sini & tekan ENTER.
================================================================
""" + colorama.Style.RESET_ALL)
    input("Tekan ENTER setelah aksi di atas selesai... ")
    time.sleep(1)
    stop_event.set()
    th.join(timeout=5)
    _simpan(paket, "__sniff_flash_hapus.json")
    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    jalankan()
