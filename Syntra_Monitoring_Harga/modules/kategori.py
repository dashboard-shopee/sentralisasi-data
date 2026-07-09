"""modules/kategori.py — ambil KATEGORI Shopee produk (FASE 1, READ-ONLY).

API list produk (search_product_list) TIDAK ngasih kategori. Kategori didapat per-produk
via get_product_info (param product_id + is_draft=false, verified live 9 Jul):
  data.product_info.category_path            -> [id1, id2, id3]        (path ID)
  data.product_info.category_path_name_list  -> ['Buku..','..','Tempat Pensil']  (nama)
Nama kategori langsung tersedia -> tak perlu resolve category tree.
"""
import config
from modules.api_util import api_get


def ambil_kategori(session, product_id):
    """Return {kategori_id, leaf, full} utk 1 produk, atau None kalau tak ada kategori.
    Lempar exception kalau request gagal (biar collector bisa skip item itu)."""
    data = api_get(config.URL_GET_PRODUCT_INFO, config.grab_headers(session),
                   {**session["params"], "product_id": int(product_id), "is_draft": "false"},
                   kunci="data")["data"]
    pi = (data or {}).get("product_info") or {}
    ids = pi.get("category_path") or []
    names = pi.get("category_path_name_list") or []
    if not names:
        return None
    return {
        "kategori_id": int(ids[-1]) if ids else None,
        "leaf": str(names[-1]),
        "full": " > ".join(str(n) for n in names),
    }
