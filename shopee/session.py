"""shopee/session.py — harvest sesi Shopee via browser (copy pola dari referensi).

Pakai profil & port Chrome SENDIRI (shopee/config). Login sekali:
    python -m shopee.session   (atau panggil buka_login())
"""

import random
import time

import colorama; colorama.init()
import DrissionPage

from shopee import config
from shopee.api import SesiKedaluwarsa

page = None


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


def shop_switcher(shop, i):
    config.log(f"[shop switcher] [{shop}] - ganti sub-toko", colorama.Fore.YELLOW)
    attempt = 0
    while True:
        try:
            page.get("https://seller.shopee.co.id/portal/shop")
            page.wait(random.randint(1, 3))
            page.ele(f'xpath=(//button[@type="button"]//span[text()="Detail"])[{i}]', timeout=10).click()
            page.wait(random.randint(1, 3))
            username = page.ele('xpath=//div[@class="subaccount-info"]//span[@class="subaccount-name"]', timeout=10).text
            page.wait(random.randint(2, 3))
            if username == shop:
                config.log(f"[shop switcher] [{shop}] - sukses", colorama.Fore.GREEN)
                break
        except Exception:
            attempt += 1
            if attempt % 5 == 0:
                config.log(f"[shop switcher] [{shop}] - belum berhasil ({attempt}x). Pastikan sudah LOGIN "
                           f"(python -m shopee.session)", colorama.Fore.RED)
            time.sleep(1)


def _harvest(shop, i):
    global page
    page = DrissionPage.ChromiumPage(_buat_options()); page.set.window.max(); page.set.timeouts(100)
    shop_switcher(shop=shop, i=i); page.wait(random.randint(1, 3))
    page.listen.start("https://seller.shopee.co.id/api/v2/login")
    page.get("https://seller.shopee.co.id/datacenter/product/performance?ADTAG=productranking")
    page.wait(random.randint(1, 3))
    try:
        page.ele('xpath=//input[@type="password"]', timeout=10).input(config.SHOPEE_PASSWORD)
        page.wait(random.randint(1, 3))
        page.ele('xpath=//button[@class="eds-button eds-button--primary eds-button--normal ios-action"]', timeout=10).click()
        page.wait(random.randint(1, 3))
    except Exception:
        pass
    paket = page.listen.wait(timeout=30); page.listen.stop()
    if not paket:
        raise SesiKedaluwarsa(f"[session] [{shop}] - gagal tangkap /api/v2/login 30s (cek LOGIN / akses sub-toko)")
    return {"headers": paket.request.headers, "params": paket.request.params}


def grab_session(shop, i):
    sess = _harvest(shop=shop, i=i)

    def refresh():
        config.log(f"[session] [{shop}] - ambil ulang cookie...", colorama.Fore.YELLOW)
        baru = _harvest(shop=shop, i=i)
        sess["headers"] = baru["headers"]; sess["params"] = baru["params"]
        config.log(f"[session] [{shop}] - sesi diperbarui", colorama.Fore.GREEN)
        return sess

    sess["refresh"] = refresh
    return sess


def close_session():
    try:
        page.quit()
    except Exception:
        pass


def buka_login():
    global page
    page = DrissionPage.ChromiumPage(_buat_options()); page.set.window.max()
    page.get("https://seller.shopee.co.id/portal/shop")
    print(colorama.Fore.LIGHTCYAN_EX + "\nSilakan LOGIN Shopee Seller di jendela Chrome." + colorama.Style.RESET_ALL)
    input("Setelah login & lihat dashboard, tekan ENTER untuk simpan & tutup... ")
    close_session()
    print(colorama.Fore.GREEN + "Login tersimpan di profil modul sentralisasi." + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    buka_login()
