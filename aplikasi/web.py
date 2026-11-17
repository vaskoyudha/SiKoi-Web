"""
============================================================
web.py -- Kerangka web mini untuk SiKoi
============================================================

File ini HANYA berisi "jembatan" antara browser dan kode Python-mu.
Isinya cuma lima hal:

    1. Permintaan  -- data yang datang dari browser (form, alamat, sesi)
    2. Web         -- daftar alamat halaman, lalu menjalankan server
    3. render()    -- mengisi template HTML dengan data Python
    4. tampilkan() -- jawaban: kirim halaman HTML
    5. alihkan()   -- jawaban: pindah ke halaman lain

File ini TIDAK perlu kamu ubah untuk membuat aplikasi.
Yang kamu tulis hanya app.py (logika halaman) dan file .html di templates/.

Baca sekali sampai paham, lalu simpan. Anggap ini "mesin" yang sudah jadi.
"""

import http.cookies
import re
import secrets
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ------------------------------------------------------------
# Lokasi folder. __file__ adalah file web.py ini sendiri,
# jadi aplikasi tetap jalan walau dijalankan dari folder lain.
# ------------------------------------------------------------
FOLDER_INI = Path(__file__).resolve().parent
FOLDER_TEMPLATE = FOLDER_INI / "templates"
FOLDER_STATIS = FOLDER_INI / "static"


# ============================================================
# BAGIAN 1 -- Membaca template
# ============================================================
#
# Template adalah file .html biasa, ditambah tiga tanda:
#
#   {{ nama }}          -> diganti isi variabel nama
#   {% if ... %}        -> tampilkan bagian ini hanya kalau syaratnya benar
#   {% for ... %}       -> ulangi bagian ini untuk setiap isi daftar
#
# Contoh:
#
#   <p>Halo {{ pengguna }}</p>
#   {% for b in daftar %}
#       <li>{{ b.nama }}: {{ b.stok }}</li>
#   {% endfor %}
#
# Itu saja. Tidak ada bahasa baru yang harus dipelajari -- isi {{ }}
# dan {% %} adalah Python biasa.

# Pola untuk memotong template menjadi potongan-potongan kecil.
# re.S artinya titik (.) juga cocok dengan baris baru.
POLA_TOKEN = re.compile(r"(\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\})", re.S)


def _potong(teks):
    """Memotong template jadi daftar ('teks'|'nilai'|'perintah', isi)."""
    hasil = []
    for bagian in POLA_TOKEN.split(teks):
        if not bagian:
            continue
        if bagian.startswith("{{"):
            isi = bagian[2:-2].strip()
            if isi.startswith("!"):
                # {{! ... }} artinya "jangan di-escape" (HTML sudah jadi)
                hasil.append(("nilai_mentah", isi[1:].strip()))
            else:
                hasil.append(("nilai", isi))
        elif bagian.startswith("{%"):
            hasil.append(("perintah", bagian[2:-2].strip()))
        elif bagian.startswith("{#"):
            continue                                  # komentar, dibuang
        else:
            hasil.append(("teks", bagian))
    return hasil


def _susun(token, posisi=0, berhenti=()):
    """
    Menyusun potongan tadi menjadi pohon.

    Fungsi ini memanggil dirinya sendiri (rekursif) supaya {% if %}
    dan {% for %} bisa berisi apa saja, termasuk {% if %} lagi.
    """
    simpul = []

    while posisi < len(token):
        jenis, isi = token[posisi]

        if jenis == "teks":
            simpul.append(("teks", isi))
            posisi += 1

        elif jenis in ("nilai", "nilai_mentah"):
            simpul.append((jenis, isi))
            posisi += 1

        else:                                          # perintah {% ... %}
            kata = isi.split(None, 1)

            if kata[0] in berhenti:
                return simpul, posisi                  # biar pemanggil yang urus

            if kata[0] == "if":
                badan, posisi = _susun(token, posisi + 1, ("else", "endif"))
                lain = []
                if token[posisi][1].split()[0] == "else":
                    lain, posisi = _susun(token, posisi + 1, ("endif",))
                simpul.append(("jika", kata[1], badan, lain))
                posisi += 1                            # lewati {% endif %}

            elif kata[0] == "for":
                cocok = re.match(r"for\s+(\w+)\s+in\s+(.+)", isi, re.S)
                if not cocok:
                    raise ValueError(f"Penulisan for salah: {{% {isi} %}}")
                badan, posisi = _susun(token, posisi + 1, ("endfor",))
                simpul.append(("ulang", cocok.group(1), cocok.group(2), badan))
                posisi += 1                            # lewati {% endfor %}

            else:
                raise ValueError(
                    f"Perintah tidak dikenal: {{% {isi} %}}. "
                    "Yang tersedia hanya: if, else, endif, for, endfor."
                )

    return simpul, posisi


# ------------------------------------------------------------
# Kotak: pembungkus supaya di template bisa ditulis b.nama
# (lebih enak dibaca daripada b['nama'])
# ------------------------------------------------------------
class Kotak:
    """Membuat isi dict bisa diakses dengan titik: b.nama."""

    def __init__(self, data):
        self.__dict__.update(data)

    def __getitem__(self, kunci):
        return self.__dict__[kunci]

    def get(self, kunci, bawaan=None):
        return self.__dict__.get(kunci, bawaan)

    def __repr__(self):
        return f"Kotak({self.__dict__})"


def _bungkus(nilai):
    """Mengubah dict jadi Kotak, dan isi daftar ikut dibungkus."""
    if isinstance(nilai, dict):
        return Kotak({k: _bungkus(v) for k, v in nilai.items()})
    if isinstance(nilai, (list, tuple)):
        return [_bungkus(v) for v in nilai]
    if hasattr(nilai, "keys") and not isinstance(nilai, Kotak):
        # sqlite3.Row termasuk di sini
        try:
            return Kotak({k: _bungkus(nilai[k]) for k in nilai.keys()})
        except Exception:
            return nilai
    return nilai


# ------------------------------------------------------------
# Fungsi bantu yang selalu tersedia di dalam template
# ------------------------------------------------------------
def angka(nilai):
    """2975000 -> '2.975.000'"""
    return f"{int(nilai or 0):,}".replace(",", ".")


def rupiah(nilai):
    """2975000 -> 'Rp2.975.000'"""
    return "Rp" + angka(nilai)


def akun(nilai):
    """Gaya akuntansi: negatif dalam kurung. -378000 -> '(378.000)'"""
    nilai = int(nilai or 0)
    if nilai < 0:
        return f"({angka(abs(nilai))})"
    return angka(nilai)


def rupiah_akun(nilai):
    """-378000 -> '(Rp378.000)'"""
    nilai = int(nilai or 0)
    if nilai < 0:
        return f"(Rp{angka(abs(nilai))})"
    return "Rp" + angka(nilai)


def desimal(nilai):
    """1.5 -> '1,50' (koma, seperti kebiasaan Indonesia)"""
    return f"{float(nilai or 0):.2f}".replace(".", ",")


def tanggal(teks):
    """'2026-10-07' -> '07 Okt 2026'"""
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
             "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    try:
        tahun, nomor_bulan, hari = str(teks).split("-")
        return f"{int(hari):02d} {bulan[int(nomor_bulan) - 1]} {tahun}"
    except Exception:
        return str(teks)


BANTU = {
    "angka": angka,
    "rupiah": rupiah,
    "akun": akun,
    "rupiah_akun": rupiah_akun,
    "desimal": desimal,
    "tanggal": tanggal,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "sorted": sorted,
    "enumerate": enumerate,
    "range": range,
    "zip": zip,
    "any": any,
    "all": all,
    "list": list,
    "dict": dict,
    "True": True,
    "False": False,
    "None": None,
}


def _hitung_nilai(ekspresi, konteks):
    """Menjalankan isi {{ ... }} sebagai Python biasa."""
    return eval(ekspresi, {"__builtins__": {}}, {**BANTU, **konteks})


def _jalankan(simpul, konteks):
    """Menelusuri pohon template dan menyambung hasilnya jadi teks HTML."""
    hasil = []

    for jenis, *sisa in simpul:
        if jenis == "teks":
            hasil.append(sisa[0])

        elif jenis == "nilai":
            nilai = _hitung_nilai(sisa[0], konteks)
            hasil.append(escape("" if nilai is None else str(nilai)))

        elif jenis == "nilai_mentah":
            nilai = _hitung_nilai(sisa[0], konteks)
            hasil.append("" if nilai is None else str(nilai))

        elif jenis == "jika":
            syarat, badan, lain = sisa
            if _hitung_nilai(syarat, konteks):
                hasil.append(_jalankan(badan, konteks))
            else:
                hasil.append(_jalankan(lain, konteks))

        elif jenis == "ulang":
            nama_var, ekspresi, badan = sisa
            for isi in _hitung_nilai(ekspresi, konteks):
                hasil.append(_jalankan(badan, {**konteks, nama_var: _bungkus(isi)}))

    return "".join(hasil)


def _baca_template(nama):
    berkas = FOLDER_TEMPLATE / nama
    if not berkas.exists():
        raise FileNotFoundError(
            f"Template '{nama}' tidak ada di folder {FOLDER_TEMPLATE}"
        )
    return berkas.read_text(encoding="utf-8")


def render(nama, /, layout=True, **data):
    """
    Mengisi template dengan data, lalu (kalau layout=True)
    memasangnya ke dalam templates/dasar.html.

    Dengan cara ini kamu TIDAK perlu menulis header dan menu di setiap
    halaman. Cukup tulis isi halamannya saja.
    """
    data = {k: _bungkus(v) for k, v in data.items()}

    isi = _jalankan(_susun(_potong(_baca_template(nama)))[0], data)

    if not layout:
        return isi

    data.setdefault("menu", "")
    data.setdefault("pesan", None)
    data.setdefault("jenis_pesan", "sukses")
    data["isi_halaman"] = isi

    return _jalankan(_susun(_potong(_baca_template("dasar.html")))[0], data)


# ============================================================
# BAGIAN 2 -- Permintaan dari browser
# ============================================================
class Permintaan:
    """
    Semua yang datang dari browser, dibungkus jadi satu objek.

    Di app.py kamu akan memakai:
        req.method      "GET" atau "POST"
        req.form        isi formulir, contoh req.form["tanggal"]
        req.get(...)    sama, tapi aman kalau kosong
        req.sesi        data login yang tersimpan
    """

    def __init__(self, method, path, form, query, sesi):
        self.method = method
        self.path = path
        self.form = form
        self.query = query
        self.sesi = sesi

    def get(self, nama, bawaan=""):
        """Ambil isi formulir tanpa error kalau tidak ada."""
        return self.form.get(nama, bawaan)

    def angka(self, nama, bawaan=0):
        """Ambil isi formulir sebagai bilangan bulat."""
        try:
            return int(self.form.get(nama, bawaan) or bawaan)
        except (TypeError, ValueError):
            return bawaan


# ============================================================
# BAGIAN 3 -- Jawaban ke browser
# ============================================================
def tampilkan(nama_template, /, **data):
    """Kirim halaman HTML."""
    return {"jenis": "html", "teks": render(nama_template, **data)}


def alihkan(tujuan):
    """Suruh browser pindah ke alamat lain."""
    return {"jenis": "alih", "tujuan": tujuan}


# ============================================================
# BAGIAN 4 -- Web: daftar halaman + server
# ============================================================
class Web:
    """
    Cara pakai:

        aplikasi = Web()

        @aplikasi.halaman("/")
        def beranda(req):
            return tampilkan("beranda.html", nama="Dunia")

        aplikasi.jalankan()

    Aturan @halaman:
        login=False  -> halaman boleh dibuka tanpa login (contoh: /login)
        owner=True   -> hanya untuk Owner; karyawan dialihkan
    """

    def __init__(self):
        self.daftar = {}          # (metode, alamat) -> (fungsi, login, owner)
        self.sesi = {}            # id_sesi -> {"nama": ..., "jabatan": ...}

    def halaman(self, alamat, metode=("GET",), login=True, owner=False):
        """Mendaftarkan satu alamat halaman."""

        def daftarkan(fungsi):
            for m in metode:
                self.daftar[(m, alamat)] = (fungsi, login, owner)
            return fungsi

        return daftarkan

    # --------------------------------------------------------
    def _cari(self, metode, path):
        """Mencari fungsi yang cocok dengan alamat yang diminta."""
        if (metode, path) in self.daftar:
            return self.daftar[(metode, path)]

        # Kalau alamat ini ada untuk metode lain, katakan dengan jelas.
        for (m, alamat) in self.daftar:
            if alamat == path:
                return "metode_salah"

        return None

    # --------------------------------------------------------
    def jalankan(self, port=8000, host="127.0.0.1"):
        """Menyalakan server. Ctrl+C untuk berhenti."""
        penangan = _buat_penangan(self)
        server = ThreadingHTTPServer((host, port), penangan)

        print(f"SiKoi berjalan di http://{host}:{port}")
        print("Tekan Ctrl+C untuk berhenti.")
        print()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer dihentikan.")
            server.server_close()


def _buat_penangan(aplikasi):
    """Membuat kelas penghubung ke browser, memakai `aplikasi` di atas."""

    class Penangan(BaseHTTPRequestHandler):
        # Jangan cetak setiap permintaan ke layar; terlalu ramai untuk pemula.
        def log_message(self, format, *args):
            pass

        # ----------------------------------------------
        def do_GET(self):
            self._tangani("GET")

        def do_POST(self):
            self._tangani("POST")

        # ----------------------------------------------
        def _tangani(self, metode):
            alamat = urlparse(self.path)
            path = alamat.path
            query = {k: v[0] for k, v in parse_qs(alamat.query).items()}

            # --- berkas statis (style.css) ---
            if path.startswith("/static/"):
                return self._kirim_berkas(path.replace("/static/", "", 1))

            # --- formulir ---
            form = {}
            if metode == "POST":
                panjang = int(self.headers.get("Content-Length", 0) or 0)
                isi = self.rfile.read(panjang).decode("utf-8")
                form = {k: v[0] for k, v in parse_qs(isi).items()}

            # --- sesi (siapa yang sedang login) ---
            id_sesi = self._baca_cookie()
            if not id_sesi:
                id_sesi = secrets.token_hex(16)
            sesi = aplikasi.sesi.setdefault(id_sesi, {})

            req = Permintaan(metode, path, form, query, sesi)

            # --- cari halaman ---
            cocok = aplikasi._cari(metode, path)

            if cocok is None:
                return self._kirim_html(
                    404, _halaman_404(path), id_sesi
                )
            if cocok == "metode_salah":
                return self._kirim_html(
                    405,
                    _halaman_pesan(
                        "Metode tidak diizinkan",
                        f"Alamat {path} tidak menerima {metode}.",
                    ),
                    id_sesi,
                )

            fungsi, perlu_login, perlu_owner = cocok

            # --- periksa hak akses SEBELUM menjalankan halaman ---
            if perlu_login and "nama" not in req.sesi:
                return self._alihkan("/login", id_sesi)

            if perlu_owner and req.sesi.get("jabatan") != "Owner":
                return self._alihkan("/penjualan", id_sesi)

            # --- jalankan halaman ---
            try:
                jawaban = fungsi(req)
            except Exception as e:
                # Tampilkan kesalahan dengan rapi, bukan halaman putih.
                import traceback
                traceback.print_exc()
                return self._kirim_html(
                    500,
                    _halaman_pesan(
                        "Ada kesalahan di program",
                        f"{type(e).__name__}: {e}",
                        petunjuk="Lihat pesan lengkapnya di jendela terminal.",
                    ),
                    id_sesi,
                )

            # --- kirim jawabannya ---
            if jawaban["jenis"] == "alih":
                return self._alihkan(jawaban["tujuan"], id_sesi)

            self._kirim_html(200, jawaban["teks"], id_sesi)

        # ----------------------------------------------
        def _baca_cookie(self):
            mentah = self.headers.get("Cookie")
            if not mentah:
                return None
            kotak = http.cookies.SimpleCookie()
            try:
                kotak.load(mentah)
            except http.cookies.CookieError:
                return None
            if "sikoi_sesi" in kotak:
                return kotak["sikoi_sesi"].value
            return None

        def _kirim_html(self, kode, teks, id_sesi):
            isi = teks.encode("utf-8")
            self.send_response(kode)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(isi)))
            self.send_header(
                "Set-Cookie", f"sikoi_sesi={id_sesi}; Path=/; HttpOnly"
            )
            self.end_headers()
            self.wfile.write(isi)

        def _alihkan(self, tujuan, id_sesi):
            self.send_response(302)
            self.send_header("Location", tujuan)
            self.send_header(
                "Set-Cookie", f"sikoi_sesi={id_sesi}; Path=/; HttpOnly"
            )
            self.end_headers()

        def _kirim_berkas(self, nama):
            berkas = (FOLDER_STATIS / nama).resolve()
            if not str(berkas).startswith(str(FOLDER_STATIS)) or not berkas.exists():
                return self._kirim_html(404, _halaman_404(nama), "")
            isi = berkas.read_bytes()
            jenis = "text/css" if nama.endswith(".css") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", jenis)
            self.send_header("Content-Length", str(len(isi)))
            self.end_headers()
            self.wfile.write(isi)

    return Penangan


# ------------------------------------------------------------
# Halaman kesalahan sederhana (dipakai kalau ada yang salah)
# ------------------------------------------------------------
def _halaman_pesan(judul, pesan, petunjuk=""):
    tambahan = f"<p class='lemah'>{escape(petunjuk)}</p>" if petunjuk else ""
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="UTF-8">
<title>{escape(judul)}</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body><main class="isi">
<h1 class="judul-halaman">{escape(judul)}</h1>
<div class="pesan error">{escape(pesan)}</div>
{tambahan}
<p><a href="/">Kembali ke halaman utama</a></p>
</main></body></html>"""


def _halaman_404(path):
    return _halaman_pesan(
        "Halaman tidak ditemukan",
        f"Alamat {path} tidak ada di aplikasi ini.",
        "Periksa ejaan alamatnya, atau kembali ke halaman utama.",
    )
