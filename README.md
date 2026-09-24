# Sistem Informasi Masjid

Aplikasi web untuk transparansi kegiatan dan keuangan masjid. Dibangun dengan **Flask** + **SQLite** (tanpa perlu instalasi database terpisah).

## Fitur

**Halaman Publik**
- Beranda (waktu shalat, kegiatan mendatang)
- Kegiatan (dengan filter kategori)
- Laporan Kas (grafik pemasukan/pengeluaran, rincian kategori)

**Panel Admin** (login diperlukan)
- Dashboard (ringkasan kas & jamaah, grafik, transaksi terbaru)
- Data Jamaah (tambah, edit, hapus, cari, pagination)
- Kegiatan & Pengumuman (tambah, publikasikan/draft, hapus)
- Kas Masjid (input transaksi pemasukan/pengeluaran, upload bukti)
- Laporan Kas (rincian per kategori, publikasikan ke halaman publik)

## Cara Menjalankan

1. Pastikan Python 3.9+ sudah terinstall.
2. Buka terminal di folder ini, lalu buat virtual environment (opsional tapi disarankan):
   ```
   python -m venv venv
   source venv/bin/activate      # Mac/Linux
   venv\Scripts\activate         # Windows
   ```
3. Install dependency:
   ```
   pip install -r requirements.txt
   ```
4. Jalankan aplikasi:
   ```
   python backend/app.py
   ```
5. Buka browser ke `http://localhost:5000`

Database SQLite (`instance/masjid.db`) beserta data contoh akan **otomatis dibuat** saat pertama kali dijalankan.

## Login Admin (Demo)

- URL: `http://localhost:5000/admin/login`
- Email: `admin@masjid.id`
- Password: `admin123`

## Reset Database

Jika ingin mengulang dari awal dengan data contoh yang segar, hapus file `instance/masjid.db` lalu jalankan ulang `python backend/app.py`.

Atau jalankan langsung:
```
python backend/database.py
```
(perhatian: ini akan menimpa ulang skema jika file lama masih ada — untuk reset total, hapus dulu file `instance/masjid.db`)

## Struktur Folder

```
sim-masjid/
├── backend/
│   ├── app.py              # Aplikasi Flask utama (semua route)
│   └── database.py         # Skema & seed data SQLite
├── frontend/
│   ├── static/
│   │   ├── css/style.css   # Styling tema hijau-emas
│   │   └── uploads/        # Upload bukti transaksi
│   └── templates/
│       ├── base.html       # Layout halaman publik
│       ├── index.html      # Beranda
│       ├── kegiatan.html   # Kegiatan publik
│       ├── laporan_kas.html
│       ├── login.html
│       └── admin/          # Template panel admin
├── instance/
│   └── masjid.db           # Database (dibuat otomatis)
├── requirements.txt
└── README.md
```

## Catatan

- Ini adalah aplikasi **untuk dijalankan secara lokal** di komputer Anda (development server Flask). Untuk deploy ke internet (VPS/hosting), gunakan WSGI server seperti Gunicorn di belakang Nginx, dan ganti `app.secret_key` di `backend/app.py` dengan nilai rahasia Anda sendiri.
- Data waktu shalat pada Beranda masih berupa contoh statis — bisa dihubungkan ke API jadwal shalat (misalnya Kemenag/Aladhan) jika diperlukan.
- Fitur upload bukti transaksi menyimpan file ke folder `frontend/static/uploads/`.
