# Deploy Dashboard ke Streamlit Community Cloud (gratis)

Dashboard baca dari Supabase (sudah online), jadi tinggal hosting tampilannya.
Folder bot (01/02/03), `.env`, dan profil Chrome **tidak** ikut ter-upload (lihat `.gitignore`).

## 1. Upload code ke GitHub
Di terminal folder `00 Sentralisasi Data` (git sudah di-init oleh Claude):
```powershell
# Buat repo kosong dulu di https://github.com/new (mis. nama: dashboard-shopee), JANGAN centang README.
git remote add origin https://github.com/USERNAME/dashboard-shopee.git
git branch -M main
git push -u origin main
```
(Saat push, login GitHub / pakai Personal Access Token bila diminta.)

## 2. Deploy di Streamlit Cloud
1. Buka https://share.streamlit.io → **Sign in with GitHub**.
2. **Create app** → **Deploy a public app from GitHub**.
3. Pilih repo `dashboard-shopee`, branch `main`, **Main file path:** `dashboard/app.py`.
4. Klik **Advanced settings → Secrets**, paste (isi nilainya):
   ```toml
   DATABASE_URL = "postgresql://postgres.xxxx:PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
   password = "rahasia-bos-2026"
   ```
   (DATABASE_URL = sama persis dengan yang di `.env` lokal.)
5. **Deploy**. Tunggu ~2-3 menit → dapat URL publik `https://xxxx.streamlit.app`.

## 3. Kasih ke bos
Kirim URL + password. Bos buka, masukkan password, langsung lihat dashboard.

> Update kode: cukup `git push` lagi, Streamlit Cloud auto-redeploy.
