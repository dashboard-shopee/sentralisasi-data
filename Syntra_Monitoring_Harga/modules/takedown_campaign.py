"""modules/takedown_campaign.py — keluarkan variasi dari CAMPAIGN Shopee (Fase 2B).

Campaign bulanan (tanggal kembar / gajian / 6.6 dst) MENGUNCI harga item -> harga
dasar tidak bisa diubah selama item masih dinominasikan. Ini melepasnya via
campaign_util (browser-context / run_js, wajib lolos anti-bot Shopee).

Alur:
  1. buka_page_toko(shop, i)                  -> browser aktif pada sub-toko itu.
  2. get_open_sessions -> sesi campaign aktif -> get_nominated_products (peta item).
  3. cocokkan (item,model) target -> nomination_id -> takedown_products (opt-out).
  4. tutup_page().

⚠️ BELUM DIUJI LIVE (dibuat saat akun sementara). Keterbatasan warisan
   campaign_util.get_open_sessions: fokus pada sesi dalam WINDOW NOMINASI; sesi yg
   sudah berjalan penuh mungkin tak terjangkau. Perlu verifikasi saat akun asli.
   DRY_RUN -> tidak benar-benar opt-out (hanya deteksi + log).
"""
from modules.log_siklus import log
import config


def takedown_dari_campaign(session, shop, i, kunci_set):
    """Keluarkan variasi (item_id, model_id) di `kunci_set` dari SEMUA sesi campaign
    aktif yang memuatnya. Return jumlah nominasi ter-takedown (0 kalau tak ada)."""
    if not kunci_set:
        return 0
    from modules.session import buka_page_toko, tutup_page
    from modules import campaign_util as C

    total = 0
    try:
        buka_page_toko(shop, i)                       # browser-context ON (anti-bot)
        sesi = C.get_open_sessions(session, shop)
        for s in sesi:
            sid = s.get("session_id")
            if not sid:
                continue
            nominated = C.get_nominated_products(session, shop, sid)  # {(item,model)->info}
            nom_ids = []
            for (iid, mid), info in nominated.items():
                try:
                    key = (int(iid), int(mid))
                except (TypeError, ValueError):
                    continue
                if key in kunci_set and info.get("nomination_id"):
                    nom_ids.append(info["nomination_id"])
            if not nom_ids:
                continue
            if config.DRY_RUN:
                log(f"(DRY) {len(nom_ids)} nominasi akan di-takedown dari sesi '{s.get('session_name','')}'",
                    level="warning", toko=shop, modul="campaign")
                total += len(nom_ids)
            else:
                if C.takedown_products(session, shop, sid, nom_ids):
                    total += len(nom_ids)
    except Exception as e:
        log(f"takedown campaign gagal: {type(e).__name__}: {str(e)[:120]}", level="error", toko=shop, modul="campaign")
    finally:
        try:
            tutup_page()
        except Exception:
            pass
    return total
