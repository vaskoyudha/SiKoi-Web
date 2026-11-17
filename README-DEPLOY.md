# SiKoi di Render (gratis)

Folder ini siap dipakai untuk Render free web service.

## Yang sudah disiapkan

- `aplikasi/app.py` membaca `PORT` dan `HOST` dari environment.
- `start.sh` membuat database contoh lalu menjalankan server.
- `render.yaml` berisi konfigurasi Render (plan free).

## Langkah

1. Buat akun gratis di https://render.com (bisa pakai GitHub).
2. Buat repository GitHub baru, unggah isi folder ini.
3. Di Render: **New > Web Service**, hubungkan repository tadi.
4. Render membaca `render.yaml`. Kalau tidak, isi manual:
   - Runtime: Python
   - Build Command: `echo tidak perlu build`
   - Start Command: `bash start.sh`
   - Instance Type: Free
5. Tunggu deploy selesai, buka URL `https://sikoi-xxxx.onrender.com`.

## Batasan gratis Render

- Service tidur setelah 15 menit tanpa pengunjung; bangun sekitar 1 menit.
- Disk bersifat sementara: database kembali ke data contoh setiap restart.
- Cocok untuk demo/juri, bukan untuk data sungguhan.
