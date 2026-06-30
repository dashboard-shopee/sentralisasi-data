"""
komisi_api.py — API KOMISI AFFILIATE Shopee (GraphQL).
Endpoint terverifikasi via `python sniff.py komisi` (__sniff_komisi.json):

  GET  /api/v1/affiliateplatform/account
       -> data.user_name = OPERATOR (mis. "beverra1:CS_RAISA"), data.shop_id
  POST /api/v3/affiliateplatform/gql?q=QueryItemsOpenCampaign
       -> BACA komisi aktif per item (itemList kosong = item TIDAK ada komisi)
  POST /api/v3/affiliateplatform/gql?q=SetOpenCampaigns
       -> SET komisi (commissionRate = persen × 1000, mis. 10% -> 10000), per item_id
  POST /api/v3/affiliateplatform/gql?q=GetOpenCampaignProducts
       -> DAFTAR produk komisi AKTIF (pagination cursor) -> itemId + commissionId + rate
  POST /api/v3/affiliateplatform/gql?q=RemoveOpenCampaigns
       -> TAKEDOWN/HAPUS komisi pakai commissionId (BUKAN itemId)

CATATAN:
  - Komisi diatur per ITEM (item_id); takedown pakai commissionId (dari GetOpenCampaignProducts).
  - commissionRate dalam satuan persen×1000 (6000 = 6%, 10000 = 10%).
  - ⚠️ Endpoint affiliateplatform/gql DIJAGA anti-bot Shopee (error 90309999) untuk
    panggilan otomatis/sintetis. Fungsi di sini SIAP PAKAI tapi butuh jalur yang lolos
    shield (piggyback panggilan asli halaman / UI-automation) — lihat memory fitur-komisi.
"""
import colorama; colorama.init()
import config
from modules.api_util import api_post, api_get

URL_KOMISI_AKUN = "https://seller.shopee.co.id/api/v1/affiliateplatform/account"
URL_KOMISI_GQL = "https://seller.shopee.co.id/api/v3/affiliateplatform/gql"

# Rate API = persen × FAKTOR_KOMISI. 10% -> 10000 (terverifikasi dari sniff & QueryRcmdCommissionRate).
FAKTOR_KOMISI = 1000

# String query/mutation disalin VERBATIM dari sniff (jangan diubah strukturnya).
_Q_BACA = (
    "\n      query QueryItemsOpenCampaign (\n        $itemIds: [Long!]\n        $shopId: Long\n      ) {"
    "\n        QueryItemsOpenCampaign (\n          itemIds: $itemIds\n          shopId: $shopId\n        ) {"
    "\n          itemList {\n            itemId\n            itemName\n            commissionId\n"
    "            commissionStatus\n            commissionRate\n            periodStartTime\n"
    "            periodEndTime\n          }\n        }\n      }\n    "
)
_Q_SET = (
    "\n      mutation SetOpenCampaigns (\n        $shopId: Long\n        $commissionRate: Int\n"
    "        $operator: String\n        $source: String\n        $items: [SetOpenCampaignItemInput!]\n"
    "        $campaignPageSource: Int\n        $campaignChannelSource: Int\n      ) {"
    "\n        SetOpenCampaigns (\n          items: $items\n          shopId: $shopId\n"
    "          commissionRate: $commissionRate\n          operator: $operator\n          source: $source\n"
    "          campaignPageSource: $campaignPageSource\n          campaignChannelSource: $campaignChannelSource\n        ) {"
    "\n          isAllSuccess\n          results {\n            itemId\n            errCode\n          }\n        }\n      }\n    "
)


# Subset field (valid GraphQL) -> response ringkas. operationName disamakan dgn aslinya.
_Q_DAFTAR_AKTIF = (
    "\n      query GetOpenCampaignProductsQuery($cursor: String, $limit: Int) {"
    "\n        GetOpenCampaignProducts(cursor: $cursor, limit: $limit) {"
    "\n          itemList {\n            itemId\n            itemName\n            commissionId\n"
    "            commissionStatus\n            commissionRate\n            periodStartTime\n            periodEndTime\n          }"
    "\n          totalCount\n          cursor\n        }\n      }\n    "
)
_Q_TAKEDOWN = (
    "\n      mutation RemoveOpenCampaignsMutation($commissionIds: [Long!], $operator: String,"
    " $campaignPageSource: Int, $campaignChannelSource: Int) {"
    "\n        RemoveOpenCampaigns(\n          commissionIds: $commissionIds\n          operator: $operator\n"
    "          campaignPageSource: $campaignPageSource\n          campaignChannelSource: $campaignChannelSource\n        ) {"
    "\n          isAllSuccess\n          results {\n            commissionId\n            errCode\n          }\n        }\n      }\n    "
)


def _potong(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# AMBIL AKUN — operator + shop_id (dipakai SetOpenCampaigns & audit).
def grab_akun(session):
    data = api_get(URL_KOMISI_AKUN, config.grab_headers(session),
                   {"_cache_api_sw_v1_": 1, "_cache_sw_max_time_": 60}, kunci="data")["data"]
    return {"shop_id": data.get("shop_id"), "operator": str(data.get("user_name", ""))}


# BACA KOMISI per item -> {item_id(int): {status, rate, persen, start, end, commissionId}}.
# Item yang TIDAK punya komisi tidak muncul di hasil (itemList kosong).
def baca_komisi_items(session, item_ids, ukuran_chunk=50):
    ids = [int(i) for i in dict.fromkeys(item_ids)]   # unik, jaga urutan
    hasil = {}
    headers = config.grab_headers(session)
    for chunk in _potong(ids, ukuran_chunk):
        payload = {"operationName": "QueryItemsOpenCampaign", "query": _Q_BACA,
                   "variables": {"itemIds": [str(i) for i in chunk]}}
        data = api_post(URL_KOMISI_GQL, headers, {"q": "QueryItemsOpenCampaign"}, payload, kunci="data")
        items = (((data.get("data") or {}).get("QueryItemsOpenCampaign") or {}).get("itemList")) or []
        for it in items:
            try:
                iid = int(it.get("itemId"))
            except (TypeError, ValueError):
                continue
            rate = it.get("commissionRate") or 0
            hasil[iid] = {
                "status": it.get("commissionStatus"),
                "rate": rate,
                "persen": round(rate / FAKTOR_KOMISI, 3),
                "start": it.get("periodStartTime"),
                "end": it.get("periodEndTime"),
                "commissionId": it.get("commissionId"),
            }
    return hasil


# BACA DAFTAR KOMISI AKTIF (pagination cursor) -> list dict per item:
#   {item_id, commission_id, persen, status, item_name, start, end}.
# Inilah cara paling tepat utk AUDIT (toko mana saja & produk mana yang komisinya aktif).
def baca_komisi_aktif(session, limit=100, maks_halaman=200):
    headers = config.grab_headers(session)
    hasil, cursor, halaman = [], "", 0
    while True:
        halaman += 1
        payload = {"operationName": "GetOpenCampaignProductsQuery", "query": _Q_DAFTAR_AKTIF,
                   "variables": {"cursor": cursor, "limit": limit}}
        data = api_post(URL_KOMISI_GQL, headers, {"q": "GetOpenCampaignProducts"}, payload, kunci="data")
        blok = (data.get("data") or {}).get("GetOpenCampaignProducts") or {}
        for it in (blok.get("itemList") or []):
            rate = it.get("commissionRate") or 0
            hasil.append({
                "item_id": int(it["itemId"]) if it.get("itemId") else None,
                "commission_id": it.get("commissionId"),
                "persen": round(rate / FAKTOR_KOMISI, 3),
                "status": it.get("commissionStatus"),
                "item_name": it.get("itemName", ""),
                "start": it.get("periodStartTime"),
                "end": it.get("periodEndTime"),
            })
        cursor = blok.get("cursor") or ""
        if (not blok.get("itemList")) or (not cursor) or halaman >= maks_halaman:
            break
    return hasil


# TAKEDOWN/HAPUS komisi pakai daftar commissionId. Return (isAllSuccess, results[]).
def takedown_komisi(session, commission_ids, operator="", ukuran_chunk=50):
    ids = [str(c) for c in commission_ids if c]
    headers = config.grab_headers(session)
    semua, ok_semua = [], True
    for chunk in _potong(ids, ukuran_chunk):
        payload = {"operationName": "RemoveOpenCampaignsMutation", "query": _Q_TAKEDOWN, "variables": {
            "commissionIds": chunk, "operator": operator,
            "campaignPageSource": 19, "campaignChannelSource": 1,
        }}
        try:
            data = api_post(URL_KOMISI_GQL, headers, {"q": "RemoveOpenCampaigns"}, payload, kunci="data")
            res = (data.get("data") or {}).get("RemoveOpenCampaigns") or {}
            semua += res.get("results", []) or []
            if not res.get("isAllSuccess"):
                ok_semua = False
        except Exception as e:
            ok_semua = False
            print(colorama.Fore.RED + f"[takedown komisi] chunk gagal: {e}" + colorama.Style.RESET_ALL)
    return ok_semua, semua


# SET KOMISI untuk daftar item ke `persen` (%). items = [{"itemId","itemName"}].
# Return (isAllSuccess, results[]). Kirim per chunk 50 item (1 chunk error tak menggugurkan sisa).
def set_komisi(session, items, persen, operator="", ukuran_chunk=50):
    rate = int(round(persen * FAKTOR_KOMISI))
    headers = config.grab_headers(session)
    semua_hasil, sukses_semua = [], True
    for chunk in _potong(items, ukuran_chunk):
        payload = {"operationName": "SetOpenCampaigns", "query": _Q_SET, "variables": {
            "commissionRate": rate,
            "operator": operator,
            "source": "sellercenter",
            "items": [{"itemId": str(it["itemId"]), "itemName": str(it.get("itemName", ""))} for it in chunk],
            "campaignPageSource": 11,
            "campaignChannelSource": 1,
        }}
        try:
            data = api_post(URL_KOMISI_GQL, headers, {"q": "SetOpenCampaigns"}, payload, kunci="data")
            res = (data.get("data") or {}).get("SetOpenCampaigns") or {}
            semua_hasil += res.get("results", []) or []
            if not res.get("isAllSuccess"):
                sukses_semua = False
        except Exception as e:
            sukses_semua = False
            print(colorama.Fore.RED + f"[set komisi] chunk gagal: {e}" + colorama.Style.RESET_ALL)
    return sukses_semua, semua_hasil
