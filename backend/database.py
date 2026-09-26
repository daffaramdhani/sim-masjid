import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "instance", "masjid.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jamaah (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    jenis_kelamin TEXT NOT NULL CHECK(jenis_kelamin IN ('Laki-laki','Perempuan')),
    no_telepon TEXT,
    alamat TEXT,
    tanggal_bergabung TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kegiatan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    tanggal TEXT NOT NULL,
    waktu_mulai TEXT,
    waktu_selesai TEXT,
    lokasi TEXT,
    kategori TEXT NOT NULL CHECK(kategori IN ('Kajian','Ibadah','Sosial','Pendidikan','Lainnya')),
    deskripsi TEXT,
    image_filename TEXT,
    ustadz TEXT,
    status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Dipublikasikan'))
);

CREATE TABLE IF NOT EXISTS pengumuman (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    isi TEXT,
    tanggal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Dipublikasikan','Arsip'))
);

CREATE TABLE IF NOT EXISTS kajian (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    tema TEXT,
    isi TEXT NOT NULL,
    tanggal TEXT NOT NULL,
    penulis TEXT,
    image_filename TEXT,
    status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Dipublikasikan'))
);

CREATE TABLE IF NOT EXISTS berita (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    isi TEXT NOT NULL,
    tanggal TEXT NOT NULL,
    penulis TEXT,
    image_filename TEXT,
    status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Dipublikasikan'))
);

CREATE TABLE IF NOT EXISTS transaksi_kas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT NOT NULL,
    jenis TEXT NOT NULL CHECK(jenis IN ('Pemasukan','Pengeluaran')),
    kategori TEXT NOT NULL,
    jumlah INTEGER NOT NULL,
    metode TEXT,
    deskripsi TEXT,
    bukti_filename TEXT,
    dipublikasikan INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pengaturan (
    kunci TEXT PRIMARY KEY,
    nilai TEXT
);
"""


def init_db(force=False):
    first_time = not os.path.exists(DB_PATH) or force
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)
    for table in ("kajian", "berita", "kegiatan"):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "image_filename" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN image_filename TEXT")
        if table == "kegiatan" and "ustadz" not in columns:
            conn.execute("ALTER TABLE kegiatan ADD COLUMN ustadz TEXT")
    conn.execute(
        "UPDATE kegiatan SET lokasi=REPLACE(lokasi, 'Masjid Al-Ikhlas', 'Masjid Nurul Hasanah') "
        "WHERE lokasi LIKE '%Masjid Al-Ikhlas%'"
    )
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) c FROM admin")
    if cur.fetchone()["c"] == 0:
        seed(conn)
    conn.close()


def seed(conn):
    # Admin default
    conn.execute(
        "INSERT INTO admin (nama, email, password_hash) VALUES (?,?,?)",
        ("Admin Masjid", "admin@masjid.id", generate_password_hash("admin123")),
    )

    # Jamaah contoh
    jamaah_list = [
        ("Ahmad Fauzi", "Laki-laki", "0812-3456-7890", "Jl. Melati No. 10", "2024-01-12"),
        ("Siti Aisyah", "Perempuan", "0813-2222-3333", "Jl. Kenanga No. 5", "2024-01-20"),
        ("Muhammad Iqbal", "Laki-laki", "0857-1111-2222", "Jl. Mawar No. 7", "2024-02-05"),
        ("Nurlita Sari", "Perempuan", "0812-9999-8888", "Jl. Anggrek No. 3", "2024-02-18"),
        ("Dedi Kurniawan", "Laki-laki", "0821-6543-2109", "Jl. Dahlia No. 9", "2024-03-01"),
        ("Rina Wijaya", "Perempuan", "0813-4567-1234", "Jl. Melati No. 22", "2024-03-15"),
        ("Bambang Sutrisno", "Laki-laki", "0812-8888-7777", "Jl. Kenanga No. 11", "2024-04-02"),
        ("Fatimah Zahra", "Perempuan", "0857-2233-4455", "Jl. Mawar No. 2", "2024-04-19"),
    ]
    conn.executemany(
        "INSERT INTO jamaah (nama, jenis_kelamin, no_telepon, alamat, tanggal_bergabung) VALUES (?,?,?,?,?)",
        jamaah_list,
    )

    # Tambahan jamaah dummy agar paginasi terlihat realistis
    import random
    nama_depan = ["Agus", "Budi", "Citra", "Dian", "Eka", "Fajar", "Gita", "Hadi", "Indah", "Joko"]
    nama_belakang = ["Santoso", "Wijaya", "Pratama", "Lestari", "Nugroho", "Saputra", "Handayani", "Ramadhan"]
    for i in range(12):
        nama = f"{random.choice(nama_depan)} {random.choice(nama_belakang)}"
        jk = random.choice(["Laki-laki", "Perempuan"])
        no_hp = f"08{random.randint(10,19)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        alamat = f"Jl. {random.choice(['Melati','Kenanga','Mawar','Anggrek','Dahlia'])} No. {random.randint(1,50)}"
        tgl = f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        conn.execute(
            "INSERT INTO jamaah (nama, jenis_kelamin, no_telepon, alamat, tanggal_bergabung) VALUES (?,?,?,?,?)",
            (nama, jk, no_hp, alamat, tgl),
        )

    # Kegiatan contoh
    kegiatan_list = [
        ("Kajian Rutin Ahad Pagi", "2025-05-25", "07:00", "08:30", "Masjid Nurul Hasanah", "Kajian",
         "Kajian rutin membahas tafsir Al-Qur'an untuk jamaah umum.", "Dipublikasikan"),
        ("Shalat Idul Adha 1446 H", "2025-06-06", "06:30", "08:00", "Halaman Masjid Nurul Hasanah", "Ibadah",
         "Pelaksanaan shalat Idul Adha berjamaah dilanjutkan penyembelihan hewan kurban.", "Dipublikasikan"),
        ("Santunan Anak Yatim", "2025-06-15", "09:00", "11:00", "Aula Masjid Nurul Hasanah", "Sosial",
         "Pembagian santunan dan bingkisan untuk anak yatim sekitar masjid.", "Dipublikasikan"),
        ("Pelatihan Remaja Masjid", "2025-06-22", "13:00", "16:00", "Aula Masjid Nurul Hasanah", "Pendidikan",
         "Pelatihan kaderisasi remaja masjid dan manajemen organisasi.", "Draft"),
    ]
    conn.executemany(
        "INSERT INTO kegiatan (judul, tanggal, waktu_mulai, waktu_selesai, lokasi, kategori, deskripsi, status) VALUES (?,?,?,?,?,?,?,?)",
        kegiatan_list,
    )

    pengumuman_list = [
        ("Renovasi Tempat Wudhu", "Pemberitahuan renovasi tempat wudhu selama 2 minggu, mohon menggunakan fasilitas sementara.", "2025-05-20", "Dipublikasikan"),
        ("Jadwal Tejil Ramadhan", "Jadwal pembagian takjil selama bulan Ramadhan setiap hari menjelang berbuka.", "2025-03-10", "Arsip"),
    ]
    conn.executemany(
        "INSERT INTO pengumuman (judul, isi, tanggal, status) VALUES (?,?,?,?)",
        pengumuman_list,
    )

    # Transaksi kas Mei 2025 (agar sesuai contoh chart)
    transaksi = [
        ("2025-05-01", "Pemasukan", "Infaq Shalat Jum'at", 1850000, "Tunai", "Infaq Shalat Jum'at, 2 Mei 2025"),
        ("2025-05-03", "Pengeluaran", "Pembelian Karpet Masjid", 2750000, "Transfer", "Pembelian karpet baru ruang utama"),
        ("2025-05-03", "Pemasukan", "Donasi Pembangunan", 5000000, "Transfer", "Donasi pembangunan dari jamaah"),
        ("2025-05-05", "Pengeluaran", "Pembayaran Listrik", 450000, "Tunai", "Tagihan listrik bulan April"),
        ("2025-05-09", "Pemasukan", "Infaq Kotak Masjid", 780000, "Tunai", "Hasil infaq kotak masjid mingguan"),
        ("2025-05-10", "Pemasukan", "Infaq Shalat Jum'at", 12650000, "Tunai", "Infaq Shalat Jum'at, 10 Mei 2025"),
        ("2025-05-10", "Pengeluaran", "Operasional Masjid", 6000000, "Tunai", "Operasional bulanan masjid"),
        ("2025-05-15", "Pemasukan", "Donasi Kegiatan", 5200000, "Transfer", "Donasi untuk kegiatan santunan"),
        ("2025-05-15", "Pengeluaran", "Kegiatan & Dakwah", 3900000, "Tunai", "Biaya penyelenggaraan santunan anak yatim"),
        ("2025-05-20", "Pemasukan", "Zakat / Fidyah", 2500000, "Transfer", "Zakat dan fidyah jamaah"),
        ("2025-05-24", "Pemasukan", "Infaq Shalat Jum'at", 1850000, "Tunai", "Infaq Shalat Jum'at, 24 Mei 2025"),
        ("2025-05-22", "Pengeluaran", "Pemeliharaan", 4500000, "Transfer", "Pemeliharaan fasilitas masjid"),
        ("2025-05-22", "Pengeluaran", "Utilitas", 3500000, "Tunai", "Biaya air dan kebersihan"),
        ("2025-05-31", "Pemasukan", "Infaq Kotak Masjid", 8300000, "Tunai", "Hasil infaq kotak masjid akhir bulan"),
    ]
    for t in transaksi:
        conn.execute(
            "INSERT INTO transaksi_kas (tanggal, jenis, kategori, jumlah, metode, deskripsi, dipublikasikan) VALUES (?,?,?,?,?,?,1)",
            t,
        )

    conn.execute(
        "INSERT INTO pengaturan (kunci, nilai) VALUES ('laporan_terpublikasi', ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M"),),
    )

    conn.commit()


if __name__ == "__main__":
    init_db(force=True)
    print("Database berhasil dibuat di", DB_PATH)
