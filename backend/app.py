import os
import calendar
import json
import io
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify,
    send_file,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from database import get_db, init_db, DB_PATH

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_FOLDER = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_FOLDER = os.path.join(BASE_DIR, "frontend", "static")
UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
app.secret_key = "ganti-dengan-secret-key-anda-sendiri"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

WAKTU_SHALAT_CONTOH = {
    "Imsyak": "04:19", "Subuh": "04:29", "Dzuhur": "11:49", "Ashar": "15:11",
    "Maghrib": "17:45", "Isya": "19:01",
}

JADWAL_JUMAT_CONTOH = {
    "waktu": "12:00",
    "imam": "Ust. Ahmad Fauzi",
    "khotib": "Ust. Muhammad Iqbal",
    "muadzin": "Bpk. Dedi Kurniawan",
}

STRUKTUR_MASJID_DEFAULT = [
    {"id": "ketua", "jabatan": "Ketua", "nama": "", "atasan": ""},
    {"id": "wakil-ketua", "jabatan": "Wakil Ketua", "nama": "", "atasan": "ketua"},
    {"id": "sekretaris", "jabatan": "Sekretaris", "nama": "", "atasan": "ketua"},
    {"id": "bendahara", "jabatan": "Bendahara", "nama": "", "atasan": "ketua"},
]

PENGATURAN_JADWAL_DEFAULT = {
    "shalat_imsyak": "04:19",
    "imam_imsyak": "Ust. Ahmad Fauzi",
    "shalat_subuh": "04:29",
    "imam_subuh": "Ust. Ahmad Fauzi",
    "shalat_dzuhur": "11:49",
    "imam_dzuhur": "Ust. Ahmad Fauzi",
    "shalat_ashar": "15:11",
    "imam_ashar": "Ust. Ahmad Fauzi",
    "shalat_maghrib": "17:45",
    "imam_maghrib": "Ust. Ahmad Fauzi",
    "shalat_isya": "19:01",
    "imam_isya": "Ust. Ahmad Fauzi",
    "jumat_waktu": "12:00",
    "jumat_imam": "Ust. Ahmad Fauzi",
    "jumat_khotib": "Ust. Muhammad Iqbal",
    "jumat_muadzin": "Bpk. Dedi Kurniawan",
    "profil_nama": "Masjid Nurul Hasanah",
    "profil_deskripsi": "Masjid Nurul Hasanah berdiri sebagai pusat ibadah dan kegiatan sosial masyarakat sekitar. Kami berkomitmen mengelola amanah umat secara transparan dan akuntabel melalui sistem informasi ini.",
    "profil_gambar": "",
}


def get_jadwal_pengaturan(conn):
    keys = tuple(PENGATURAN_JADWAL_DEFAULT)
    placeholders = ",".join("?" for _ in keys)
    rows = conn.execute(
        f"SELECT kunci, nilai FROM pengaturan WHERE kunci IN ({placeholders})", keys
    ).fetchall()
    values = PENGATURAN_JADWAL_DEFAULT.copy()
    values.update({row["kunci"]: row["nilai"] for row in rows})
    profile_images = []
    if values["profil_gambar"]:
        try:
            decoded_images = json.loads(values["profil_gambar"])
            profile_images = decoded_images if isinstance(decoded_images, list) else [values["profil_gambar"]]
        except (TypeError, json.JSONDecodeError):
            profile_images = [values["profil_gambar"]]

    return {
        "waktu_shalat": {
            "Imsyak": values["shalat_imsyak"],
            "Subuh": values["shalat_subuh"],
            "Dzuhur": values["shalat_dzuhur"],
            "Ashar": values["shalat_ashar"],
            "Maghrib": values["shalat_maghrib"],
            "Isya": values["shalat_isya"],
        },
        "imam_shalat": {
            "Imsyak": values["imam_imsyak"],
            "Subuh": values["imam_subuh"],
            "Dzuhur": values["imam_dzuhur"],
            "Ashar": values["imam_ashar"],
            "Maghrib": values["imam_maghrib"],
            "Isya": values["imam_isya"],
        },
        "jadwal_jumat": {
            "waktu": values["jumat_waktu"],
            "imam": values["jumat_imam"],
            "khotib": values["jumat_khotib"],
            "muadzin": values["jumat_muadzin"],
        },
        "profil": {
            "nama": values["profil_nama"],
            "deskripsi": values["profil_deskripsi"],
            "gambar": profile_images[0] if profile_images else "",
            "gambar_list": profile_images,
        },
    }


def get_struktur_masjid(conn):
    row = conn.execute(
        "SELECT nilai FROM pengaturan WHERE kunci='struktur_masjid'"
    ).fetchone()
    if not row:
        return [anggota.copy() for anggota in STRUKTUR_MASJID_DEFAULT]

    try:
        struktur = json.loads(row["nilai"])
    except (TypeError, json.JSONDecodeError):
        return [anggota.copy() for anggota in STRUKTUR_MASJID_DEFAULT]

    if not isinstance(struktur, list):
        return [anggota.copy() for anggota in STRUKTUR_MASJID_DEFAULT]
    anggota_list = []
    used_ids = set()
    for index, item in enumerate(struktur):
        if not isinstance(item, dict):
            continue
        jabatan = str(item.get("jabatan", "")).strip()
        if not jabatan:
            continue
        anggota_id = str(item.get("id", "")).strip() or f"anggota-{index + 1}"
        if anggota_id in used_ids:
            anggota_id = f"{anggota_id}-{index + 1}"
        used_ids.add(anggota_id)
        anggota_list.append({
            "id": anggota_id,
            "jabatan": jabatan,
            "nama": str(item.get("nama", "")).strip(),
            "atasan": str(item.get("atasan", "")).strip(),
        })

    anggota_by_id = {anggota["id"]: anggota for anggota in anggota_list}
    for anggota in anggota_list:
        if anggota["atasan"] not in anggota_by_id or anggota["atasan"] == anggota["id"]:
            anggota["atasan"] = ""

    for anggota in anggota_list:
        current = anggota
        visited = set()
        while current["atasan"]:
            if current["id"] in visited:
                anggota["atasan"] = ""
                break
            visited.add(current["id"])
            current = anggota_by_id.get(current["atasan"], {})
            if not current:
                break
    return anggota_list


def build_struktur_pohon(anggota_list):
    nodes = {
        anggota["id"]: {**anggota, "children": []}
        for anggota in anggota_list
    }
    roots = []
    for anggota in anggota_list:
        node = nodes[anggota["id"]]
        parent = nodes.get(anggota["atasan"])
        if parent:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def struktur_masjid_ada_siklus(anggota_list):
    parents = {anggota["id"]: anggota["atasan"] for anggota in anggota_list}
    for anggota_id in parents:
        visited = set()
        current = anggota_id
        while current:
            if current in visited:
                return True
            visited.add(current)
            current = parents.get(current, "")
    return False


def get_data_divisi_sarana(conn):
    row = conn.execute(
        "SELECT nilai FROM pengaturan WHERE kunci='data_divisi_sarana'"
    ).fetchone()
    if not row:
        return {"sarana_pemeliharaan": [], "purnomo": []}

    try:
        data = json.loads(row["nilai"])
    except (TypeError, json.JSONDecodeError):
        return {"sarana_pemeliharaan": [], "purnomo": []}

    result = {}
    for key in ("sarana_pemeliharaan", "purnomo"):
        entries = data.get(key, []) if isinstance(data, dict) else []
        result[key] = [
            {"kegiatan": str(item.get("kegiatan", "")).strip()}
            for item in entries
            if isinstance(item, dict) and str(item.get("kegiatan", "")).strip()
        ] if isinstance(entries, list) else []
    return result


# ---------- Helpers ----------

def rupiah(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 0
    return "Rp " + f"{value:,.0f}".replace(",", ".")


app.jinja_env.filters["rupiah"] = rupiah


def save_uploaded_image(file):
    if not file or not file.filename:
        return None
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename


def save_uploaded_images(files):
    return [filename for file in files if (filename := save_uploaded_image(file))]


@app.context_processor
def inject_now():
    conn = get_db()
    struktur_masjid = get_struktur_masjid(conn)
    conn.close()
    return {"now": datetime.now, "struktur_masjid": struktur_masjid}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def get_ringkasan_kas(conn, hanya_dipublikasikan=True):
    where = "WHERE dipublikasikan = 1" if hanya_dipublikasikan else ""
    total_masuk = conn.execute(
        f"SELECT COALESCE(SUM(jumlah),0) t FROM transaksi_kas {where}{' AND' if where else 'WHERE'} jenis='Pemasukan'"
    ).fetchone()["t"]
    total_keluar = conn.execute(
        f"SELECT COALESCE(SUM(jumlah),0) t FROM transaksi_kas {where}{' AND' if where else 'WHERE'} jenis='Pengeluaran'"
    ).fetchone()["t"]
    saldo = total_masuk - total_keluar
    return total_masuk, total_keluar, saldo


def get_chart_mingguan(conn, bulan, tahun, hanya_dipublikasikan=True):
    """Kelompokkan transaksi per rentang tanggal (mirip contoh: 1,5,10,15,20,25,31)."""
    checkpoints = [1, 5, 10, 15, 20, 25, 31]
    labels = [f"{c} {BULAN_ID[bulan][:3]}" for c in checkpoints]
    masuk = [0] * len(checkpoints)
    keluar = [0] * len(checkpoints)

    q = "SELECT tanggal, jenis, jumlah FROM transaksi_kas WHERE strftime('%m', tanggal)=? AND strftime('%Y', tanggal)=?"
    params = [f"{bulan:02d}", str(tahun)]
    if hanya_dipublikasikan:
        q += " AND dipublikasikan = 1"
    rows = conn.execute(q, params).fetchall()

    for r in rows:
        day = int(r["tanggal"].split("-")[2])
        # cari checkpoint terdekat (bucket ke checkpoint >= day, terakhir jika lebih besar dari semua)
        idx = len(checkpoints) - 1
        for i, c in enumerate(checkpoints):
            if day <= c:
                idx = i
                break
        if r["jenis"] == "Pemasukan":
            masuk[idx] += r["jumlah"]
        else:
            keluar[idx] += r["jumlah"]
    return labels, masuk, keluar


# ---------- Rute Publik ----------

@app.route("/")
def beranda():
    conn = get_db()
    kegiatan = conn.execute(
        "SELECT * FROM kegiatan WHERE status='Dipublikasikan' ORDER BY tanggal ASC LIMIT 2"
    ).fetchall()
    pengumuman = conn.execute(
        "SELECT * FROM pengumuman WHERE status='Dipublikasikan' ORDER BY tanggal DESC LIMIT 3"
    ).fetchall()
    jadwal = get_jadwal_pengaturan(conn)
    conn.close()
    return render_template(
        "index.html",
        kegiatan=kegiatan,
        pengumuman=pengumuman,
        waktu_shalat=jadwal["waktu_shalat"],
        imam_shalat=jadwal["imam_shalat"],
        jadwal_jumat=jadwal["jadwal_jumat"],
        profil=jadwal["profil"],
        today=datetime.now(),
    )


@app.route("/kegiatan")
def kegiatan_publik():
    kategori = request.args.get("kategori", "Semua")
    conn = get_db()
    if kategori and kategori != "Semua":
        rows = conn.execute(
            "SELECT * FROM kegiatan WHERE status='Dipublikasikan' AND kategori=? ORDER BY tanggal ASC",
            (kategori,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM kegiatan WHERE status='Dipublikasikan' ORDER BY tanggal ASC"
        ).fetchall()
    conn.close()
    return render_template("kegiatan.html", kegiatan=rows, kategori_aktif=kategori, halaman="Kegiatan")


@app.route("/struktur-masjid")
def struktur_masjid_publik():
    conn = get_db()
    struktur_pohon = build_struktur_pohon(get_struktur_masjid(conn))
    conn.close()
    return render_template("struktur_masjid.html", struktur_pohon=struktur_pohon)


@app.route("/sarana-pemeliharaan")
def sarana_pemeliharaan_publik():
    conn = get_db()
    data_divisi = get_data_divisi_sarana(conn)
    conn.close()
    return render_template("sarana_pemeliharaan.html", data_divisi=data_divisi)


@app.route("/kajian")
def kajian_publik():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM kajian WHERE status='Dipublikasikan' ORDER BY tanggal DESC"
    ).fetchall()
    conn.close()
    return render_template("kajian.html", kajian=rows)


@app.route("/berita")
def berita_publik():
    conn = get_db()
    berita = conn.execute("SELECT * FROM berita WHERE status='Dipublikasikan' ORDER BY tanggal DESC").fetchall()
    conn.close()
    return render_template("berita.html", berita=berita)


@app.route("/pengumuman")
def pengumuman_publik():
    conn = get_db()
    pengumuman = conn.execute(
        "SELECT * FROM pengumuman WHERE status='Dipublikasikan' ORDER BY tanggal DESC"
    ).fetchall()
    conn.close()
    return render_template("pengumuman.html", pengumuman=pengumuman)


@app.route("/laporan-kas")
def laporan_kas_publik():
    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    conn = get_db()
    total_masuk, total_keluar, saldo = get_ringkasan_kas(conn, hanya_dipublikasikan=True)
    labels, masuk, keluar = get_chart_mingguan(conn, bulan, tahun, hanya_dipublikasikan=True)

    rincian = conn.execute(
        """SELECT kategori, SUM(jumlah) total FROM transaksi_kas
           WHERE dipublikasikan=1 AND jenis='Pemasukan'
           AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?
           GROUP BY kategori ORDER BY total DESC""",
        (f"{bulan:02d}", str(tahun)),
    ).fetchall()
    total_pemasukan_bulan = sum(r["total"] for r in rincian)
    conn.close()
    return render_template(
        "laporan_kas.html",
        saldo=saldo, total_masuk=total_masuk, total_keluar=total_keluar,
        labels=labels, masuk=masuk, keluar=keluar, rincian=rincian,
        total_pemasukan_bulan=total_pemasukan_bulan,
        bulan=bulan, tahun=tahun, nama_bulan=BULAN_ID[bulan],
    )


# ---------- Auth ----------

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        admin = conn.execute("SELECT * FROM admin WHERE email=?", (email,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_nama"] = admin["nama"]
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        flash("Email atau password salah.", "error")
    return render_template("login.html")


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Admin: Dashboard ----------

@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def dashboard():
    conn = get_db()
    total_jamaah = conn.execute("SELECT COUNT(*) c FROM jamaah").fetchone()["c"]
    kegiatan_mendatang = conn.execute(
        "SELECT COUNT(*) c FROM kegiatan WHERE date(tanggal) >= date('now')"
    ).fetchone()["c"]

    now = datetime.now()
    bulan, tahun = now.month, now.year
    pemasukan_bulan = conn.execute(
        "SELECT COALESCE(SUM(jumlah),0) t FROM transaksi_kas WHERE jenis='Pemasukan' AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?",
        (f"{bulan:02d}", str(tahun)),
    ).fetchone()["t"]
    pengeluaran_bulan = conn.execute(
        "SELECT COALESCE(SUM(jumlah),0) t FROM transaksi_kas WHERE jenis='Pengeluaran' AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?",
        (f"{bulan:02d}", str(tahun)),
    ).fetchone()["t"]
    _, _, saldo = get_ringkasan_kas(conn, hanya_dipublikasikan=False)

    labels, masuk, keluar = get_chart_mingguan(conn, bulan, tahun, hanya_dipublikasikan=False)

    transaksi_terbaru = conn.execute(
        "SELECT * FROM transaksi_kas ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_jamaah=total_jamaah, kegiatan_mendatang=kegiatan_mendatang,
        pemasukan_bulan=pemasukan_bulan, pengeluaran_bulan=pengeluaran_bulan,
        saldo=saldo, labels=labels, masuk=masuk, keluar=keluar,
        transaksi_terbaru=transaksi_terbaru, today=now,
    )


# ---------- Admin: Pengaturan Jadwal ----------

@app.route("/admin/pengaturan", methods=["GET", "POST"])
@login_required
def pengaturan_admin():
    if request.method == "POST":
        fields = {
            key: request.form.get(key, "").strip()
            for key in PENGATURAN_JADWAL_DEFAULT
        }
        schedule_keys = [key for key in PENGATURAN_JADWAL_DEFAULT if not key.startswith("profil_")]
        if all(fields[key] for key in schedule_keys):
            conn = get_db()
            conn.executemany(
                "INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?) "
                "ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai",
                [(key, fields[key]) for key in schedule_keys],
            )
            conn.commit()
            conn.close()
            flash("Jadwal shalat berhasil diperbarui.", "success")
            return redirect(url_for("pengaturan_admin"))
        flash("Semua jadwal dan nama petugas wajib diisi.", "error")

    conn = get_db()
    jadwal = get_jadwal_pengaturan(conn)
    conn.close()
    return render_template("admin/pengaturan.html", jadwal=jadwal)


@app.route("/admin/struktur-masjid", methods=["GET", "POST"])
@login_required
def struktur_masjid_admin():
    if request.method == "POST":
        id_list = request.form.getlist("struktur_id[]")
        jabatan_list = request.form.getlist("struktur_jabatan[]")
        nama_list = request.form.getlist("struktur_nama[]")
        atasan_list = request.form.getlist("struktur_atasan[]")
        struktur = [
            {"id": anggota_id.strip() or f"anggota-{index + 1}",
             "jabatan": jabatan.strip(), "nama": nama.strip(), "atasan": atasan.strip()}
            for index, (anggota_id, jabatan, nama, atasan) in enumerate(
                zip(id_list, jabatan_list, nama_list, atasan_list)
            )
            if jabatan.strip()
        ]
        valid_ids = {anggota["id"] for anggota in struktur}
        for anggota in struktur:
            if anggota["atasan"] not in valid_ids or anggota["atasan"] == anggota["id"]:
                anggota["atasan"] = ""
        if struktur_masjid_ada_siklus(struktur):
            flash("Susunan atasan tidak boleh membentuk lingkaran.", "error")
            return render_template(
                "admin/struktur_masjid.html", struktur_pengurus=struktur
            ), 400

        conn = get_db()
        conn.execute(
            "INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?) "
            "ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai",
            ("struktur_masjid", json.dumps(struktur, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        flash("Struktur masjid berhasil diperbarui.", "success")
        return redirect(url_for("struktur_masjid_admin"))

    conn = get_db()
    struktur_pengurus = get_struktur_masjid(conn)
    conn.close()
    return render_template(
        "admin/struktur_masjid.html", struktur_pengurus=struktur_pengurus
    )


@app.route("/admin/sarana-pemeliharaan", methods=["GET", "POST"])
@login_required
def sarana_pemeliharaan_admin():
    if request.method == "POST":
        def read_divisi(prefix):
            activities = request.form.getlist(f"{prefix}_kegiatan[]")
            return [
                {"kegiatan": kegiatan.strip()}
                for kegiatan in activities
                if kegiatan.strip()
            ]

        data = {
            "sarana_pemeliharaan": read_divisi("sarana"),
            "purnomo": read_divisi("purnomo"),
        }
        conn = get_db()
        conn.execute(
            "INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?) "
            "ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai",
            ("data_divisi_sarana", json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        flash("Data divisi sarana dan pemeliharaan berhasil disimpan.", "success")
        return redirect(url_for("sarana_pemeliharaan_admin"))

    conn = get_db()
    data_divisi = get_data_divisi_sarana(conn)
    conn.close()
    return render_template("admin/sarana_pemeliharaan.html", data_divisi=data_divisi)


@app.route("/admin/profil", methods=["GET", "POST"])
@login_required
def profil_admin():
    if request.method == "POST":
        nama = request.form.get("profil_nama", "").strip()
        deskripsi = request.form.get("profil_deskripsi", "").strip()
        if nama and deskripsi:
            image_filenames = save_uploaded_images(request.files.getlist("profil_gambar"))
            conn = get_db()
            current_image = conn.execute(
                "SELECT nilai FROM pengaturan WHERE kunci='profil_gambar'"
            ).fetchone()
            image_value = json.dumps(image_filenames) if image_filenames else (current_image["nilai"] if current_image else "")
            conn.executemany(
                "INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?) "
                "ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai",
                [("profil_nama", nama), ("profil_deskripsi", deskripsi),
                 ("profil_gambar", image_value)],
            )
            conn.commit()
            conn.close()
            flash("Profil masjid berhasil diperbarui.", "success")
            return redirect(url_for("profil_admin"))
        flash("Nama masjid dan deskripsi wajib diisi.", "error")

    conn = get_db()
    profil = get_jadwal_pengaturan(conn)["profil"]
    conn.close()
    return render_template("admin/profil.html", profil=profil)


# ---------- Admin: Kajian & Berita ----------

@app.route("/admin/kajian-berita")
@login_required
def kajian_berita_admin():
    tab = request.args.get("tab", "kajian")
    conn = get_db()
    kajian = conn.execute("SELECT * FROM kajian ORDER BY tanggal DESC, id DESC").fetchall()
    berita = conn.execute("SELECT * FROM berita ORDER BY tanggal DESC, id DESC").fetchall()
    conn.close()
    return render_template("admin/kajian_berita.html", tab=tab, kajian=kajian, berita=berita)


@app.route("/admin/kajian/tambah", methods=["POST"])
@login_required
def kajian_tambah():
    f = request.form
    image_filename = save_uploaded_image(request.files.get("gambar"))
    conn = get_db()
    conn.execute(
        "INSERT INTO kajian (judul, tema, isi, tanggal, penulis, image_filename, status) VALUES (?,?,?,?,?,?,?)",
        (f.get("judul", "").strip(), f.get("tema", "").strip(), f.get("isi", "").strip(),
         f.get("tanggal"), f.get("penulis", "").strip(), image_filename, f.get("status", "Draft")),
    )
    conn.commit()
    conn.close()
    flash("Materi kajian berhasil ditambahkan.", "success")
    return redirect(url_for("kajian_berita_admin", tab="kajian"))


@app.route("/admin/kajian/<int:kid>/status", methods=["POST"])
@login_required
def kajian_toggle_status(kid):
    conn = get_db()
    row = conn.execute("SELECT status FROM kajian WHERE id=?", (kid,)).fetchone()
    if row:
        status = "Draft" if row["status"] == "Dipublikasikan" else "Dipublikasikan"
        conn.execute("UPDATE kajian SET status=? WHERE id=?", (status, kid))
        conn.commit()
    conn.close()
    return redirect(url_for("kajian_berita_admin", tab="kajian"))


@app.route("/admin/kajian/<int:kid>/hapus", methods=["POST"])
@login_required
def kajian_hapus(kid):
    conn = get_db()
    conn.execute("DELETE FROM kajian WHERE id=?", (kid,))
    conn.commit()
    conn.close()
    flash("Materi kajian berhasil dihapus.", "success")
    return redirect(url_for("kajian_berita_admin", tab="kajian"))


@app.route("/admin/berita/tambah", methods=["POST"])
@login_required
def berita_tambah():
    f = request.form
    image_filename = save_uploaded_image(request.files.get("gambar"))
    conn = get_db()
    conn.execute(
        "INSERT INTO berita (judul, isi, tanggal, penulis, image_filename, status) VALUES (?,?,?,?,?,?)",
        (f.get("judul", "").strip(), f.get("isi", "").strip(), f.get("tanggal"),
         f.get("penulis", "").strip(), image_filename, f.get("status", "Draft")),
    )
    conn.commit()
    conn.close()
    flash("Berita berhasil ditambahkan.", "success")
    return redirect(url_for("kajian_berita_admin", tab="berita"))


@app.route("/admin/berita/<int:bid>/status", methods=["POST"])
@login_required
def berita_toggle_status(bid):
    conn = get_db()
    row = conn.execute("SELECT status FROM berita WHERE id=?", (bid,)).fetchone()
    if row:
        status = "Draft" if row["status"] == "Dipublikasikan" else "Dipublikasikan"
        conn.execute("UPDATE berita SET status=? WHERE id=?", (status, bid))
        conn.commit()
    conn.close()
    return redirect(url_for("kajian_berita_admin", tab="berita"))


@app.route("/admin/berita/<int:bid>/hapus", methods=["POST"])
@login_required
def berita_hapus(bid):
    conn = get_db()
    conn.execute("DELETE FROM berita WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    flash("Berita berhasil dihapus.", "success")
    return redirect(url_for("kajian_berita_admin", tab="berita"))


# ---------- Admin: Data Jamaah ----------

@app.route("/admin/jamaah")
@login_required
def jamaah_list():
    q = request.args.get("q", "").strip()
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 20
    conn = get_db()
    if q:
        like = f"%{q}%"
        total = conn.execute(
            "SELECT COUNT(*) c FROM jamaah WHERE nama LIKE ? OR no_telepon LIKE ? OR alamat LIKE ?",
            (like, like, like),
        ).fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM jamaah WHERE nama LIKE ? OR no_telepon LIKE ? OR alamat LIKE ? ORDER BY id LIMIT ? OFFSET ?",
            (like, like, like, per_page, (page - 1) * per_page),
        ).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) c FROM jamaah").fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM jamaah ORDER BY id LIMIT ? OFFSET ?", (per_page, (page - 1) * per_page)
        ).fetchall()
    conn.close()
    total_pages = max((total + per_page - 1) // per_page, 1)
    return render_template(
        "admin/jamaah.html", jamaah=rows, q=q, page=page, total_pages=total_pages,
        total=total, per_page=per_page,
    )


@app.route("/admin/jamaah/tambah", methods=["POST"])
@login_required
def jamaah_tambah():
    nama = request.form.get("nama", "").strip()
    jk = request.form.get("jenis_kelamin")
    telp = request.form.get("no_telepon", "").strip()
    alamat = request.form.get("alamat", "").strip()
    tgl = request.form.get("tanggal_bergabung") or datetime.now().strftime("%Y-%m-%d")
    if nama and jk:
        conn = get_db()
        conn.execute(
            "INSERT INTO jamaah (nama, jenis_kelamin, no_telepon, alamat, tanggal_bergabung) VALUES (?,?,?,?,?)",
            (nama, jk, telp, alamat, tgl),
        )
        conn.commit()
        conn.close()
        flash("Data jamaah berhasil ditambahkan.", "success")
    else:
        flash("Nama dan jenis kelamin wajib diisi.", "error")
    return redirect(url_for("jamaah_list"))


@app.route("/admin/jamaah/<int:jid>/edit", methods=["POST"])
@login_required
def jamaah_edit(jid):
    nama = request.form.get("nama", "").strip()
    jk = request.form.get("jenis_kelamin")
    telp = request.form.get("no_telepon", "").strip()
    alamat = request.form.get("alamat", "").strip()
    conn = get_db()
    conn.execute(
        "UPDATE jamaah SET nama=?, jenis_kelamin=?, no_telepon=?, alamat=? WHERE id=?",
        (nama, jk, telp, alamat, jid),
    )
    conn.commit()
    conn.close()
    flash("Data jamaah berhasil diperbarui.", "success")
    return redirect(url_for("jamaah_list"))


@app.route("/admin/jamaah/<int:jid>/hapus", methods=["POST"])
@login_required
def jamaah_hapus(jid):
    conn = get_db()
    conn.execute("DELETE FROM jamaah WHERE id=?", (jid,))
    conn.commit()
    conn.close()
    flash("Data jamaah berhasil dihapus.", "success")
    return redirect(url_for("jamaah_list"))


# ---------- Admin: Kegiatan & Pengumuman ----------

@app.route("/admin/kegiatan-pengumuman")
@login_required
def kegiatan_admin():
    tab = request.args.get("tab", "kegiatan")
    conn = get_db()
    kegiatan = conn.execute("SELECT * FROM kegiatan ORDER BY tanggal DESC").fetchall()
    pengumuman = conn.execute("SELECT * FROM pengumuman ORDER BY tanggal DESC").fetchall()
    conn.close()
    return render_template("admin/kegiatan.html", kegiatan=kegiatan, pengumuman=pengumuman, tab=tab)


@app.route("/admin/kegiatan/tambah", methods=["POST"])
@login_required
def kegiatan_tambah():
    f = request.form
    image_filename = save_uploaded_image(request.files.get("gambar"))
    conn = get_db()
    conn.execute(
          """INSERT INTO kegiatan (judul, tanggal, waktu_mulai, waktu_selesai, lokasi, kategori, deskripsi, image_filename, ustadz, status)
              VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (f.get("judul"), f.get("tanggal"), f.get("waktu_mulai"), f.get("waktu_selesai"),
            f.get("lokasi"), f.get("kategori"), f.get("deskripsi"), image_filename,
            f.get("ustadz", "").strip(), f.get("status", "Draft")),
    )
    conn.commit()
    conn.close()
    flash("Kegiatan berhasil ditambahkan.", "success")
    return redirect(url_for("kegiatan_admin", tab="kegiatan"))


@app.route("/admin/kegiatan/<int:kid>/edit", methods=["POST"])
@login_required
def kegiatan_edit(kid):
    f = request.form
    image_filename = save_uploaded_image(request.files.get("gambar"))
    conn = get_db()
    current = conn.execute("SELECT image_filename FROM kegiatan WHERE id=?", (kid,)).fetchone()
    if not current:
        conn.close()
        flash("Kegiatan tidak ditemukan.", "error")
        return redirect(url_for("kegiatan_admin", tab="kegiatan"))
    image_value = image_filename or current["image_filename"]
    conn.execute(
        """UPDATE kegiatan SET judul=?, tanggal=?, waktu_mulai=?, waktu_selesai=?, lokasi=?,
           kategori=?, deskripsi=?, image_filename=?, ustadz=?, status=? WHERE id=?""",
        (f.get("judul"), f.get("tanggal"), f.get("waktu_mulai"), f.get("waktu_selesai"),
         f.get("lokasi"), f.get("kategori"), f.get("deskripsi"), image_value,
         f.get("ustadz", "").strip(), f.get("status", "Draft"), kid),
    )
    conn.commit()
    conn.close()
    flash("Kegiatan berhasil diperbarui.", "success")
    return redirect(url_for("kegiatan_admin", tab="kegiatan"))


@app.route("/admin/kegiatan/<int:kid>/status", methods=["POST"])
@login_required
def kegiatan_toggle_status(kid):
    conn = get_db()
    row = conn.execute("SELECT status FROM kegiatan WHERE id=?", (kid,)).fetchone()
    if row:
        baru = "Draft" if row["status"] == "Dipublikasikan" else "Dipublikasikan"
        conn.execute("UPDATE kegiatan SET status=? WHERE id=?", (baru, kid))
        conn.commit()
    conn.close()
    return redirect(url_for("kegiatan_admin", tab="kegiatan"))


@app.route("/admin/kegiatan/<int:kid>/hapus", methods=["POST"])
@login_required
def kegiatan_hapus(kid):
    conn = get_db()
    conn.execute("DELETE FROM kegiatan WHERE id=?", (kid,))
    conn.commit()
    conn.close()
    flash("Kegiatan berhasil dihapus.", "success")
    return redirect(url_for("kegiatan_admin", tab="kegiatan"))


@app.route("/admin/pengumuman/tambah", methods=["POST"])
@login_required
def pengumuman_tambah():
    f = request.form
    conn = get_db()
    conn.execute(
        "INSERT INTO pengumuman (judul, isi, tanggal, status) VALUES (?,?,?,?)",
        (f.get("judul"), f.get("isi"), f.get("tanggal") or datetime.now().strftime("%Y-%m-%d"),
         f.get("status", "Draft")),
    )
    conn.commit()
    conn.close()
    flash("Pengumuman berhasil ditambahkan.", "success")
    return redirect(url_for("kegiatan_admin", tab="pengumuman"))


@app.route("/admin/pengumuman/<int:pid>/edit", methods=["POST"])
@login_required
def pengumuman_edit(pid):
    f = request.form
    conn = get_db()
    conn.execute(
        "UPDATE pengumuman SET judul=?, isi=?, tanggal=?, status=? WHERE id=?",
        (f.get("judul", "").strip(), f.get("isi", "").strip(), f.get("tanggal"),
         f.get("status", "Draft"), pid),
    )
    conn.commit()
    conn.close()
    flash("Pengumuman berhasil diperbarui.", "success")
    return redirect(url_for("kegiatan_admin", tab="pengumuman"))


@app.route("/admin/pengumuman/<int:pid>/hapus", methods=["POST"])
@login_required
def pengumuman_hapus(pid):
    conn = get_db()
    conn.execute("DELETE FROM pengumuman WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Pengumuman berhasil dihapus.", "success")
    return redirect(url_for("kegiatan_admin", tab="pengumuman"))


# ---------- Admin: Kas Masjid ----------

@app.route("/admin/kas")
@login_required
def kas_admin():
    conn = get_db()
    riwayat = conn.execute("SELECT * FROM transaksi_kas ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    return render_template("admin/kas.html", riwayat=riwayat, today=datetime.now())


@app.route("/admin/kas/tambah", methods=["POST"])
@login_required
def kas_tambah():
    f = request.form
    bukti_filename = None
    file = request.files.get("bukti")
    if file and file.filename:
        bukti_filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], bukti_filename))

    conn = get_db()
    conn.execute(
        """INSERT INTO transaksi_kas (tanggal, jenis, kategori, jumlah, metode, deskripsi, bukti_filename, dipublikasikan)
           VALUES (?,?,?,?,?,?,?,0)""",
        (f.get("tanggal"), f.get("jenis"), f.get("kategori"), int(f.get("jumlah") or 0),
         f.get("metode"), f.get("deskripsi"), bukti_filename),
    )
    conn.commit()
    conn.close()
    flash("Transaksi kas berhasil disimpan.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/kas/<int:tid>/hapus", methods=["POST"])
@login_required
def kas_hapus(tid):
    conn = get_db()
    conn.execute("DELETE FROM transaksi_kas WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    flash("Transaksi berhasil dihapus.", "success")
    return redirect(url_for("kas_admin"))


# ---------- Admin: Laporan Kas ----------

@app.route("/admin/laporan")
@login_required
def laporan_admin():
    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    conn = get_db()

    def total_by(jenis, publik_only):
        q = "SELECT COALESCE(SUM(jumlah),0) t FROM transaksi_kas WHERE jenis=? AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?"
        params = [jenis, f"{bulan:02d}", str(tahun)]
        if publik_only:
            q += " AND dipublikasikan=1"
        return conn.execute(q, params).fetchone()["t"]

    pemasukan_bulan = total_by("Pemasukan", False)
    pengeluaran_bulan = total_by("Pengeluaran", False)
    saldo_awal = 0
    saldo_akhir = saldo_awal + pemasukan_bulan - pengeluaran_bulan

    rincian_masuk = conn.execute(
        """SELECT kategori, SUM(jumlah) total FROM transaksi_kas
           WHERE jenis='Pemasukan' AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?
           GROUP BY kategori ORDER BY total DESC""",
        (f"{bulan:02d}", str(tahun)),
    ).fetchall()
    rincian_keluar = conn.execute(
        """SELECT kategori, SUM(jumlah) total FROM transaksi_kas
           WHERE jenis='Pengeluaran' AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?
           GROUP BY kategori ORDER BY total DESC""",
        (f"{bulan:02d}", str(tahun)),
    ).fetchall()

    sudah_publikasi = conn.execute(
        "SELECT COUNT(*) c FROM transaksi_kas WHERE strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=? AND dipublikasikan=1",
        (f"{bulan:02d}", str(tahun)),
    ).fetchone()["c"] > 0

    pengaturan = conn.execute(
        "SELECT nilai FROM pengaturan WHERE kunci='laporan_terpublikasi'"
    ).fetchone()
    terakhir_publikasi = pengaturan["nilai"] if pengaturan else "-"
    conn.close()

    return render_template(
        "admin/laporan.html",
        bulan=bulan, tahun=tahun, nama_bulan=BULAN_ID[bulan],
        saldo_awal=saldo_awal, saldo_akhir=saldo_akhir,
        pemasukan_bulan=pemasukan_bulan, pengeluaran_bulan=pengeluaran_bulan,
        rincian_masuk=rincian_masuk, rincian_keluar=rincian_keluar,
        sudah_publikasi=sudah_publikasi, terakhir_publikasi=terakhir_publikasi,
        bulan_list=list(enumerate(BULAN_ID)),
    )


@app.route("/admin/laporan/pdf")
@login_required
def laporan_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        flash("Fitur PDF membutuhkan instalasi reportlab. Jalankan: pip install -r requirements.txt", "error")
        return redirect(url_for("laporan_admin"))

    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    conn = get_db()
    transaksi = conn.execute(
        """SELECT tanggal, jenis, kategori, jumlah, metode, deskripsi
           FROM transaksi_kas WHERE strftime('%m', tanggal)=? AND strftime('%Y', tanggal)=?
           ORDER BY tanggal ASC, id ASC""",
        (f"{bulan:02d}", str(tahun)),
    ).fetchall()
    conn.close()

    def rupiah_pdf(value):
        return "Rp " + f"{value:,.0f}".replace(",", ".")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Laporan Keuangan Masjid Nurul Hasanah", styles["Title"]),
        Paragraph(f"Periode {BULAN_ID[bulan]} {tahun}", styles["Normal"]),
        Spacer(1, 8 * mm),
    ]
    masuk = sum(row["jumlah"] for row in transaksi if row["jenis"] == "Pemasukan")
    keluar = sum(row["jumlah"] for row in transaksi if row["jenis"] == "Pengeluaran")
    story.append(Table([
        ["Total Pemasukan", "Total Pengeluaran", "Selisih"],
        [rupiah_pdf(masuk), rupiah_pdf(keluar), rupiah_pdf(masuk - keluar)],
    ], colWidths=[58 * mm] * 3, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#154A36")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#E7DFC8")),
        ("PADDING", (0, 0), (-1, -1), 7),
    ])))
    story.append(Spacer(1, 8 * mm))
    data = [["Tanggal", "Jenis", "Kategori", "Jumlah", "Metode", "Keterangan"]]
    for row in transaksi:
        data.append([row["tanggal"], row["jenis"], row["kategori"], rupiah_pdf(row["jumlah"]),
                     row["metode"] or "-", row["deskripsi"] or "-"])
    if len(data) == 1:
        data.append(["-", "-", "Tidak ada transaksi", "Rp 0", "-", "-"])
    story.append(Table(data, repeatRows=1, colWidths=[22 * mm, 25 * mm, 31 * mm, 27 * mm, 22 * mm, 53 * mm],
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#154A36")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#E7DFC8")),
                           ("FONTSIZE", (0, 0), (-1, -1), 7),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("PADDING", (0, 0), (-1, -1), 5),
                       ])))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"laporan-keuangan-{tahun}-{bulan:02d}.pdf")


@app.route("/admin/laporan/publikasikan", methods=["POST"])
@login_required
def laporan_publikasikan():
    bulan = int(request.form.get("bulan"))
    tahun = int(request.form.get("tahun"))
    conn = get_db()
    conn.execute(
        "UPDATE transaksi_kas SET dipublikasikan=1 WHERE strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?",
        (f"{bulan:02d}", str(tahun)),
    )
    conn.execute(
        "UPDATE pengaturan SET nilai=? WHERE kunci='laporan_terpublikasi'",
        (datetime.now().strftime("%Y-%m-%d %H:%M"),),
    )
    conn.commit()
    conn.close()
    flash(f"Laporan kas {BULAN_ID[bulan]} {tahun} berhasil dipublikasikan untuk jamaah.", "success")
    return redirect(url_for("laporan_admin", bulan=bulan, tahun=tahun))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
