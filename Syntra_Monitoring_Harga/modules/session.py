"""modules/session.py — harvest sesi Shopee via browser (metode Syntra_Iklan).

Browser dibuka SECUKUPNYA buat manen sesi (cookie + params dari /api/v2/login)
lalu LANGSUNG DITUTUP. Semua kerja API setelah itu lewat `requests` (cepat, tanpa
browser nganggur) -> tidak bentrok & tidak berat. Login sekali: python run.py login
"""
import random
import time
import colorama; colorama.init()
import DrissionPage
import config

# HANYA dipakai buka_login (login manual). Siklus normal pakai page LOKAL & nutup sendiri.
page = None

# PAGE PERSISTEN utk aksi browser-context (campaign/komisi yg kena anti-bot Shopee).
# Siklus harga normal TIDAK memakainya (harvest sesi -> tutup -> requests). Hanya
# dibuka saat butuh aksi yg wajib via run_js dari halaman Shopee asli.
_page_ctx = None


def get_page():
    """Page browser yang sedang terbuka utk aksi browser-context (None kalau belum dibuka).
    Dipakai campaign_util / komisi_api (api_post_browser via run_js)."""
    return _page_ctx


def buka_page_toko(shop, i):
    """Buka browser (port 9556) + switch ke sub-toko `shop`, kembalikan page yang
    TETAP TERBUKA utk aksi browser-context. Panggil tutup_page() setelah selesai.
    Catatan: jangan barengan dengan harvest sesi (sama-sama pakai port 9556)."""
    global _page_ctx
    tutup_page()
    _page_ctx = DrissionPage.ChromiumPage(_buat_options())
    try:
        _page_ctx.set.window.max()
    except Exception:
        pass
    shop_switcher(page=_page_ctx, shop=shop, i=i)
    _page_ctx.wait(random.randint(1, 2))
    return _page_ctx


def tutup_page():
    """Tutup page browser-context (kalau ada) + beri jeda agar port 9556 lepas."""
    global _page_ctx
    if _page_ctx is not None:
        try:
            _page_ctx.quit()
        except Exception:
            pass
        _page_ctx = None
        time.sleep(3)


def _buat_options():
    options = DrissionPage.ChromiumOptions()
    options.set_argument("--force-device-scale-factor=0.8")
    if config.CHROME_PATH:
        options.set_browser_path(config.CHROME_PATH)
    if config.CHROME_PORT:
        options.set_local_port(config.CHROME_PORT)
    if config.CHROME_USER_DATA:
        options.set_user_data_path(config.CHROME_USER_DATA)
    return options


def shop_switcher(page, shop, i, maks_percobaan=20):
    """Pindah ke sub-toko `shop` (index i). BOUNDED: kalau setelah `maks_percobaan`
    tetap tidak ketemu (mis. sedang di SUB-AKUN LAIN / toko bukan milik kita) ->
    RAISE supaya toko itu di-SKIP mulus (bukan loop selamanya)."""
    print(colorama.Fore.YELLOW + f"[shop switcher] [{shop}] - ganti sub-toko" + colorama.Style.RESET_ALL)
    attempt = 0
    while attempt < maks_percobaan:
        attempt += 1
        try:
            page.get("https://seller.shopee.co.id/portal/shop")
            page.wait(random.randint(1, 3))
            page.ele(f'xpath=(//button[@type="button"]//span[text()="Detail"])[{i}]', timeout=10).click()
            page.wait(random.randint(1, 3))
            username = page.ele('xpath=//div[@class="subaccount-info"]//span[@class="subaccount-name"]', timeout=10).text
            page.wait(random.randint(2, 3))
            if username == shop:
                print(colorama.Fore.GREEN + f"[shop switcher] [{shop}] - sukses" + colorama.Style.RESET_ALL)
                return
            if username and username != shop:
                print(colorama.Style.DIM + colorama.Fore.WHITE
                      + f"[shop switcher] [{shop}] - posisi {i} berisi '{username}' (bukan target); coba lagi ({attempt}/{maks_percobaan})"
                      + colorama.Style.RESET_ALL)
        except Exception:
            if attempt % 5 == 0:
                print(colorama.Fore.RED + f"[shop switcher] [{shop}] - belum berhasil ({attempt}x). "
                      f"Pastikan sudah LOGIN (python run.py login)" + colorama.Style.RESET_ALL)
        time.sleep(1)
    # Gagal setelah maks_percobaan -> SKIP toko ini (sub-akun lain / toko tak ditemukan).
    raise RuntimeError(f"toko '{shop}' tidak ditemukan di shop switcher "
                       f"({maks_percobaan}x) - kemungkinan sedang di sub-akun lain; DI-SKIP")


def _harvest(shop, i):
    # page LOKAL (bukan global) -> ditutup di finally, browser tak nganggur kebuka.
    page = DrissionPage.ChromiumPage(_buat_options())
    page.set.timeouts(100)
    try:
        try:
            page.set.window.max()
        except Exception:
            pass
        shop_switcher(page=page, shop=shop, i=i)
        page.wait(random.randint(1, 3))
        page.listen.start("https://seller.shopee.co.id/api/v2/login")
        page.get("https://seller.shopee.co.id/datacenter/product/performance?ADTAG=productranking")
        page.wait(random.randint(1, 3))
        # isi password (auto re-login) sebelum tangkap /api/v2/login -> sesi valid
        try:
            page.ele('xpath=//input[@type="password"]', timeout=8).input(config.SHOPEE_PASSWORD)
            page.wait(random.randint(1, 3))
            page.ele('xpath=//button[@class="eds-button eds-button--primary eds-button--normal ios-action"]', timeout=8).click()
            page.wait(random.randint(1, 3))
        except Exception:
            pass
        paket = page.listen.wait(timeout=30)
        page.listen.stop()
        if not paket:
            raise RuntimeError(f"[session] [{shop}] - gagal tangkap /api/v2/login 30s (cek LOGIN / akses sub-toko)")
        hasil = {"headers": paket.request.headers, "params": paket.request.params}
        print(colorama.Fore.WHITE + f"[session] [{shop}] - sesi terpanen, tutup browser & lanjut via API" + colorama.Style.RESET_ALL)
        return hasil
    finally:
        try:
            page.quit()
        except Exception:
            pass
        # beri jeda biar Chrome benar-benar mati & port 9556 lepas
        # (cegah "browser connection fails" pas toko berikutnya buka browser).
        time.sleep(3)


def grab_session(shop, i, percobaan=3):
    # Retry kalau browser gagal connect (race buka/tutup di port sama).
    last = None
    for n in range(1, percobaan + 1):
        try:
            sess = _harvest(shop=shop, i=i)
            break
        except Exception as e:
            last = e
            print(colorama.Fore.YELLOW
                  + f"[session] [{shop}] - panen gagal ({n}/{percobaan}): {str(e)[:80]} -> retry"
                  + colorama.Style.RESET_ALL)
            time.sleep(5)
    else:
        raise last

    def refresh():
        print(colorama.Fore.YELLOW + f"[session] [{shop}] - ambil ulang cookie..." + colorama.Style.RESET_ALL)
        baru = _harvest(shop=shop, i=i)
        sess["headers"] = baru["headers"]
        sess["params"] = baru["params"]
        print(colorama.Fore.GREEN + f"[session] [{shop}] - sesi diperbarui" + colorama.Style.RESET_ALL)
        return sess

    sess["refresh"] = refresh
    return sess


def close_session():
    # siklus normal sudah nutup browser sendiri di _harvest; ini buat nutup browser login manual.
    global page
    try:
        if page is not None:
            page.quit()
    except Exception:
        pass
    finally:
        page = None


def buka_login():
    global page
    page = DrissionPage.ChromiumPage(_buat_options())
    page.set.window.max()
    page.get("https://seller.shopee.co.id/portal/shop")
    print(colorama.Fore.LIGHTCYAN_EX + "\nSilakan LOGIN Shopee Seller di jendela Chrome yang terbuka." + colorama.Style.RESET_ALL)
    input("Setelah berhasil login & melihat dashboard, tekan ENTER untuk menyimpan & menutup... ")
    close_session()
    print(colorama.Fore.GREEN + "Login tersimpan di profil bot. Lanjut: python run.py" + colorama.Style.RESET_ALL)
