"""sniff_campaign_aksi.py — sniff endpoint SET (nominasi) & TAKEDOWN (opt-out) campaign,
LENGKAP dengan header request asli (termasuk signature x-sap-sec kalau ada) — bukan cuma
URL+payload kayak sniff sebelumnya. Tujuan: bandingin header request BENERAN (dari klik UI
Shopee asli) vs yang kita kirim sendiri (fetch/run_js) — endpoint nominated_entity_list/
opt_out balik kode anti-bot 90309999 pas kita panggil sendiri (15 Jul), kemungkinan karena
kurang signature yang cuma di-generate SDK Shopee pas user beneran klik.

Cara pakai (login dulu kalau sesi lama: python run.py login):
  python sniff_campaign_aksi.py

Hasil: __sniff_campaign_aksi.json (url+method+params+body+response+HEADERS lengkap).
"""
import json
import time
import threading
import colorama; colorama.init()
from modules.session import _buat_options
import DrissionPage

URL_CAMPAIGN_PAGE = "https://seller.shopee.co.id/portal/marketing/cmt/campaign?source=2"


def _ringkas(v, _depth=0):
    if isinstance(v, dict):
        return {k: _ringkas(val, _depth + 1) for k, val in v.items()}
    if isinstance(v, list):
        potong = v[:15]
        hasil = [_ringkas(x, _depth + 1) for x in potong]
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
            if "/api/mkt/cmt/" not in url:
                continue
            keluaran.append({
                "url": url,
                "method": getattr(p, "method", ""),
                "request_headers": _ringkas(dict(getattr(p.request, "headers", None) or {})),
                "request_params": _ringkas(_as_json(getattr(p.request, "params", None))),
                "request_body": _ringkas(_as_json(getattr(p.request, "postData", None))),
                "response": _ringkas(_as_json(getattr(p.response, "body", None))),
            })
        except Exception as e:
            keluaran.append({"error": str(e)})
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    print(colorama.Fore.GREEN + f"\n[sniff] {len(keluaran)} request /api/mkt/cmt/ tersimpan ke {nama_file}" + colorama.Style.RESET_ALL)
    for k in keluaran:
        u = k.get("url", "")
        base = u.split("?")[0]
        print(colorama.Fore.CYAN + f"  - {k.get('method',''):4} {base}" + colorama.Style.RESET_ALL)
        hdrs = k.get("request_headers") or {}
        sig_keys = [h for h in hdrs if "sap" in h.lower() or "sign" in h.lower() or "sec" in h.lower()]
        if sig_keys:
            print(colorama.Fore.YELLOW + f"      header signature: {sig_keys}" + colorama.Style.RESET_ALL)


def _watcher_multitab(page, paket, stop_event):
    attached = set()

    def _sniff_tab(tab):
        try:
            tab.listen.start("seller.shopee.co.id/api/mkt/cmt")
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
    print(colorama.Fore.YELLOW + f"[sniff campaign aksi] membuka {URL_CAMPAIGN_PAGE} ..." + colorama.Style.RESET_ALL)
    page.get(URL_CAMPAIGN_PAGE)

    paket = []
    stop_event = threading.Event()
    th = threading.Thread(target=_watcher_multitab, args=(page, paket, stop_event), daemon=True)
    th.start()

    print(colorama.Fore.LIGHTCYAN_EX + """
================================================================
  Tujuan: nangkep HEADER LENGKAP (termasuk signature) dari aksi campaign
  yang BENERAN diklik lewat UI Shopee asli.

  Lakuin di browser yang kebuka (BEBAS campaign apa aja, ga harus tanggal
  kembar, yang penting sesi 'buka nominasi' atau 'sesi berjalan'):

  [A] LIHAT PRODUK TERNOMINASI (paling penting, ini yang gagal via API):
      Campaign -> pilih 1 campaign -> buka 1 sesi -> tab "Produk Ternominasi"
      (atau nama serupa) -> tunggu list produk muncul.

  [B] NOMINASI (SET) produk baru:
      Di sesi yang sama -> "Tambah/Nominasi Produk" -> pilih 1-2 produk
      -> klik SIMPAN/KONFIRMASI sampai muncul notif berhasil.

  [C] TAKEDOWN (batalkan nominasi):
      Pilih 1 produk yang UDAH ternominasi -> klik hapus/batal nominasi
      -> KONFIRMASI sampai notif berhasil.

  Lakuin A dulu (wajib, paling penting), B & C kalau sempat. Selesai?
  Balik ke sini & tekan ENTER.
================================================================
""" + colorama.Style.RESET_ALL)
    input("Tekan ENTER setelah aksi di atas selesai... ")
    time.sleep(1)
    stop_event.set()
    th.join(timeout=5)
    _simpan(paket, "__sniff_campaign_aksi.json")
    try:
        page.quit()
    except Exception:
        pass


if __name__ == "__main__":
    jalankan()
