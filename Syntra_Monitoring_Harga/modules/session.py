import colorama; colorama.init()
import DrissionPage
import random
import time
import config

page = None


def get_page():
    global page
    return page


# BUAT OPTIONS (path + port + profil bot)
def _buat_options():
    options = DrissionPage.ChromiumOptions()
    options.set_argument('--force-device-scale-factor=0.8')
    if config.CHROME_PATH: options.set_browser_path(config.CHROME_PATH)
    if config.CHROME_PORT: options.set_local_port(config.CHROME_PORT)
    if config.CHROME_USER_DATA: options.set_user_data_path(config.CHROME_USER_DATA)
    return options


# SHOP SWITCHER
def shop_switcher(shop, i):
    print(colorama.Fore.YELLOW + f'[shop switcher] [{shop}] - bot sedang melakukan ganti sub-toko' + colorama.Style.RESET_ALL )
    attempt = 0
    while True:
        try:
            page.get('https://seller.shopee.co.id/portal/shop')
            page.wait(random.randint(1,3))
            page.ele(f'xpath=(//button[@type="button"]//span[text()="Detail"])[{i}]', timeout=10).click()
            page.wait(random.randint(1,3))
            username=page.ele('xpath=//div[@class="subaccount-info"]//span[@class="subaccount-name"]', timeout=10).text
            page.wait(random.randint(2,3))
            if username == shop: print(colorama.Fore.GREEN + f'[shop switcher] [{shop}] - bot sukses melakukan ganti sub-toko' + colorama.Style.RESET_ALL ); break
        except:
            attempt += 1
            if attempt % 5 == 0:
                print(colorama.Fore.RED + f'[shop switcher] [{shop}] - belum berhasil ({attempt}x). Pastikan sudah LOGIN Shopee Seller di jendela Chrome. (sekali login: python new.py login)' + colorama.Style.RESET_ALL )
            time.sleep(1)


# GRAB SESSION
def grab_session(shop, i):
    global page
    page=DrissionPage.ChromiumPage(_buat_options()); page.set.window.max(); page.set.timeouts(100)
    shop_switcher(shop=shop, i=i); page.wait(random.randint(1,3))
    page.listen.start('https://seller.shopee.co.id/api/v2/login')
    page.get("https://seller.shopee.co.id/datacenter/product/performance?ADTAG=productranking")
    page.wait(random.randint(1,3))
    try:
        page.ele('xpath=//input[@type="password"]', timeout=10).input(config.SHOPEE_PASSWORD)
        page.wait(random.randint(1,3))
        page.ele('xpath=//button[@class="eds-button eds-button--primary eds-button--normal ios-action"]', timeout=10).click()
        page.wait(random.randint(1,3))
    except:
        pass
    get_requests=page.listen.wait().request; get_headers=get_requests.headers; get_params=get_requests.params; page.listen.stop()
    return {'headers': get_headers, 'params': get_params}


# CLOSE SESSION
def close_session():
    try:
        page.quit()
    except:
        pass


# BUKA LOGIN (sekali) — buka profil bot ke halaman login, tunggu user login manual
def buka_login():
    global page
    page = DrissionPage.ChromiumPage(_buat_options()); page.set.window.max()
    page.get('https://seller.shopee.co.id/portal/shop')
    print(colorama.Fore.LIGHTCYAN_EX + '\nSilakan LOGIN Shopee Seller di jendela Chrome yang terbuka.' + colorama.Style.RESET_ALL)
    input('Setelah berhasil login & melihat dashboard, tekan ENTER di sini untuk menyimpan & menutup... ')
    close_session()
    print(colorama.Fore.GREEN + 'Login tersimpan di profil bot. Lanjut: python new.py test' + colorama.Style.RESET_ALL)
