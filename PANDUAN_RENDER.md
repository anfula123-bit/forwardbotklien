# Panduan Deploy Bot ke Render.com (Gratis & 24/7)

Agar bot Anda bisa berjalan 24 jam nonstop secara gratis di Render.com, kita menggunakan trik **Dummy Web Server** dikombinasikan dengan layanan **Uptime (Cron-job)**. Kode bot Anda dan `requirements.txt` telah diperbarui untuk mendukung ini.

## Langkah 1: Upload Kode ke GitHub
1. Buat repositori baru (bisa Privat atau Publik) di [GitHub](https://github.com).
2. Upload semua file dari folder `forwardbot` Anda (terutama `bot_klien.py` dan `requirements.txt`) ke repositori tersebut.

## Langkah 2: Buat Web Service di Render.com
1. Daftar atau Login ke [Render.com](https://render.com).
2. Klik tombol **New +** di pojok kanan atas, lalu pilih **Web Service**.
3. Pilih **"Build and deploy from a Git repository"** dan hubungkan akun GitHub Anda.
4. Pilih repositori GitHub yang baru saja Anda buat.
5. Isi konfigurasi sebagai berikut:
   - **Name:** Bebas (misal: `bot-forwarder-klien`)
   - **Region:** Pilih yang terdekat (misal: Singapore)
   - **Branch:** `main` (atau `master`)
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot_klien.py`
   - **Instance Type:** Pilih **Free** ($0/month)
6. Scroll ke bawah, klik **Create Web Service**.
7. Tunggu beberapa menit hingga proses build dan deploy selesai. Jika berhasil, Anda akan melihat pesan **"Live"** berwarna hijau.
8. Salin URL aplikasi Anda yang ada di bagian atas (misal: `https://bot-forwarder-klien.onrender.com`).

> [!NOTE]
> Pada paket Free, Render akan "menidurkan" (sleep) aplikasi Anda jika tidak ada yang mengunjungi URL tersebut selama 15 menit. Saat aplikasi tertidur, bot Anda akan mati.

## Langkah 3: Membuat Bot Aktif 24/7 (Anti-Sleep)
Agar URL Anda dikunjungi secara otomatis setiap saat sehingga bot tidak pernah tidur, kita gunakan layanan pihak ketiga.

1. Buka [cron-job.org](https://cron-job.org/) (Gratis) atau [UptimeRobot](https://uptimerobot.com/).
2. Buat akun dan login.
3. Buat tugas baru (**Create Cronjob** / **Add New Monitor**).
4. Masukkan URL aplikasi Render Anda (misal: `https://bot-forwarder-klien.onrender.com`).
5. Atur jadwal eksekusi (Schedule/Interval) menjadi **Setiap 10 Menit** atau **Setiap 14 Menit**.
6. Simpan / Create.

🎉 **Selesai!** 
Sekarang cron-job akan "memanggil" dummy web server (Flask) yang kita buat di dalam bot setiap 10-14 menit sekali. Karena batas Render adalah 15 menit, aplikasi Render Anda tidak akan pernah tertidur, dan bot Telegram Anda akan aktif 24 jam sehari secara gratis!
