"""
============================================================
buat_database.py -- Membuat database + data awal
============================================================
Jalankan SEKALI dari terminal:

    python buat_database.py

Kalau dijalankan lagi, file sikoi.db dibuat ulang dari nol.
"""

import os
import sqlite3

NAMA_DATABASE = "sikoi.db"

# ------------------------------------------------------------
# LANGKAH 1: Hapus file lama (supaya bisa diulang dari nol)
# ------------------------------------------------------------
if os.path.exists(NAMA_DATABASE):
    os.remove(NAMA_DATABASE)
    print("Database lama dihapus.")

koneksi = sqlite3.connect(NAMA_DATABASE)
koneksi.row_factory = sqlite3.Row
koneksi.execute("PRAGMA foreign_keys = ON")

# ------------------------------------------------------------
# LANGKAH 2: Buat tabel
# ------------------------------------------------------------
koneksi.executescript("""
CREATE TABLE pengguna (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nama    TEXT NOT NULL,
    jabatan TEXT NOT NULL,            -- 'Owner' atau 'Karyawan'
    pin     TEXT NOT NULL
);

CREATE TABLE akun (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    no_akun      TEXT NOT NULL,
    nama         TEXT NOT NULL,
    kelompok     TEXT NOT NULL,
    saldo_normal TEXT NOT NULL        -- 'Debit' atau 'Kredit'
);

CREATE TABLE pemasok (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    kode  TEXT NOT NULL,
    nama  TEXT NOT NULL,
    jenis TEXT NOT NULL
);

CREATE TABLE pelanggan (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    kode  TEXT NOT NULL,
    nama  TEXT NOT NULL,
    jenis TEXT NOT NULL
);

CREATE TABLE barang (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    kode               TEXT NOT NULL,
    nama               TEXT NOT NULL,
    satuan             TEXT NOT NULL,
    stok_awal          INTEGER NOT NULL,
    hpp                INTEGER NOT NULL,      -- HPP rata-rata saat ini
    harga_jual         INTEGER NOT NULL,
    stok_minimum       INTEGER NOT NULL,
    berat              REAL NOT NULL,          -- kg per satuan
    akun_persediaan_id INTEGER NOT NULL
);

CREATE TABLE transaksi (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal      TEXT NOT NULL,                -- YYYY-MM-DD
    no_bukti     TEXT NOT NULL,
    jenis        TEXT NOT NULL,
    pelanggan_id INTEGER,
    pemasok_id   INTEGER,
    keterangan   TEXT,
    akun_kas_id  INTEGER,
    ongkir       INTEGER DEFAULT 0,
    dibuat_oleh  TEXT
);

CREATE TABLE transaksi_baris (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    transaksi_id INTEGER NOT NULL,
    barang_id    INTEGER NOT NULL,
    qty          INTEGER NOT NULL,
    harga_satuan INTEGER NOT NULL,
    hpp_satuan   INTEGER NOT NULL
);

CREATE TABLE opname (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal    TEXT NOT NULL,
    barang_id  INTEGER NOT NULL,
    qty_hilang INTEGER NOT NULL,
    jenis      TEXT NOT NULL DEFAULT 'mati',   -- 'mati' atau 'pakai'
    keterangan TEXT
);

CREATE TABLE jurnal (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal    TEXT NOT NULL,
    no_bukti   TEXT NOT NULL,
    akun_id    INTEGER NOT NULL,
    debit      INTEGER NOT NULL DEFAULT 0,
    kredit     INTEGER NOT NULL DEFAULT 0,
    keterangan TEXT
);
""")

# ------------------------------------------------------------
# LANGKAH 3: Isi data awal
# ------------------------------------------------------------

# Pengguna
koneksi.executemany(
    "INSERT INTO pengguna (nama, jabatan, pin) VALUES (?, ?, ?)",
    [("Pak Hadi", "Owner", "1234"), ("Mas Tono", "Karyawan", "5678")],
)

# Daftar akun
daftar_akun = [
    ("1101", "Kas", "Aset Lancar", "Debit"),
    ("1102", "Bank", "Aset Lancar", "Debit"),
    ("1103", "Kas Kecil", "Aset Lancar", "Debit"),
    ("1201", "Piutang Usaha", "Aset Lancar", "Debit"),
    ("1301", "Persediaan Ikan Koi", "Aset Lancar", "Debit"),
    ("1302", "Persediaan Pakan", "Aset Lancar", "Debit"),
    ("1401", "Indukan Koi", "Aset Tetap", "Debit"),
    ("1501", "Peralatan Kolam", "Aset Tetap", "Debit"),
    ("1502", "Akumulasi Penyusutan Peralatan", "Aset Tetap", "Kredit"),
    ("2101", "Utang Usaha", "Kewajiban", "Kredit"),
    ("3101", "Modal Kelompok", "Ekuitas", "Kredit"),
    ("3102", "Prive/Penarikan Anggota", "Ekuitas", "Debit"),
    ("4101", "Penjualan Koi", "Pendapatan", "Kredit"),
    ("4102", "Pendapatan Ongkos Kirim", "Pendapatan", "Kredit"),
    ("5101", "Harga Pokok Penjualan (HPP)", "HPP", "Debit"),
    ("6101", "Beban Pakan", "Beban", "Debit"),
    ("6102", "Beban Retribusi Kolam", "Beban", "Debit"),
    ("6103", "Beban Garam dan Obat", "Beban", "Debit"),
    ("6104", "Beban Perlengkapan dan Perawatan", "Beban", "Debit"),
    ("6105", "Beban Ongkos Kirim", "Beban", "Debit"),
    ("6106", "Beban Penyusutan Peralatan", "Beban", "Debit"),
    ("6107", "Beban Kerugian Ikan Mati", "Beban", "Debit"),
]
koneksi.executemany(
    "INSERT INTO akun (no_akun, nama, kelompok, saldo_normal) VALUES (?, ?, ?, ?)",
    daftar_akun,
)

# Pemasok
koneksi.executemany(
    "INSERT INTO pemasok (kode, nama, jenis) VALUES (?, ?, ?)",
    [
        ("S-01", "UD Bibit Koi Sumber Rejeki", "Supplier bibit/induk"),
        ("S-02", "Toko Pakan Ikan Makmur", "Supplier pakan"),
        ("S-03", "Toko Perikanan Tirta", "Supplier peralatan/garam"),
        ("S-04", "Dinas Perikanan Kota Semarang", "Retribusi kolam"),
    ],
)

# Pelanggan
koneksi.executemany(
    "INSERT INTO pelanggan (kode, nama, jenis) VALUES (?, ?, ?)",
    [
        ("C-01", "Pembeli Umum (penghobi)", "Customer"),
        ("C-02", "Pak Darto (pengepul)", "Customer borongan"),
        ("C-03", "Pembeli Online Luar Kota", "Customer"),
        ("C-04", "Kafe Taman Asri", "Customer"),
        ("C-05", "Pemesan Proyek/Bantuan", "Customer pesanan benih"),
    ],
)


def cari_id_akun(no_akun):
    """Mencari id akun dari nomornya, supaya tidak menulis angka ajaib."""
    baris = koneksi.execute(
        "SELECT id FROM akun WHERE no_akun = ?", (no_akun,)
    ).fetchone()
    return baris["id"]


akun_koi = cari_id_akun("1301")
akun_pakan = cari_id_akun("1302")

# Barang: (kode, nama, satuan, stok awal, hpp, harga jual, minimum, berat, akun)
daftar_barang = [
    ("KOI-10", "Koi Kohiku 10 cm", "ekor", 150, 10000, 15000, 100, 0.02, akun_koi),
    ("KOI-15", "Koi Kohiku 15 cm", "ekor", 100, 14000, 25000,  60, 0.05, akun_koi),
    ("KOI-20", "Koi Kohiku 20 cm", "ekor",  60, 20000, 40000,  30, 0.10, akun_koi),
    ("KOI-30", "Koi Kohiku 30 cm", "ekor",  40, 32000, 75000,  15, 0.40, akun_koi),
    ("PKN-01", "Pakan koi/nila",   "kg",    40, 11000,     0,  50, 0.00, akun_pakan),
]
koneksi.executemany(
    """INSERT INTO barang
       (kode, nama, satuan, stok_awal, hpp, harga_jual, stok_minimum, berat, akun_persediaan_id)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    daftar_barang,
)

# ------------------------------------------------------------
# LANGKAH 4: Jurnal saldo awal (1 Oktober 2026)
# ------------------------------------------------------------
# Total debit harus sama dengan total kredit: Rp15.320.000
saldo_awal = [
    ("2026-10-01", "SA-001", cari_id_akun("1101"), 1500000, 0, "Saldo awal kas"),
    ("2026-10-01", "SA-001", cari_id_akun("1102"), 3000000, 0, "Saldo awal bank"),
    ("2026-10-01", "SA-001", cari_id_akun("1301"), 5380000, 0, "Saldo awal persediaan ikan koi"),
    ("2026-10-01", "SA-001", cari_id_akun("1302"), 440000, 0, "Saldo awal persediaan pakan"),
    ("2026-10-01", "SA-001", cari_id_akun("1401"), 3200000, 0, "Saldo awal indukan koi (6 ekor)"),
    ("2026-10-01", "SA-001", cari_id_akun("1501"), 1800000, 0, "Saldo awal peralatan kolam"),
    ("2026-10-01", "SA-001", cari_id_akun("1502"), 0, 600000, "Akumulasi penyusutan peralatan"),
    ("2026-10-01", "SA-001", cari_id_akun("3101"), 0, 14720000, "Modal awal kelompok"),
]

koneksi.executemany(
    """INSERT INTO jurnal (tanggal, no_bukti, akun_id, debit, kredit, keterangan)
       VALUES (?, ?, ?, ?, ?, ?)""",
    saldo_awal,
)

koneksi.commit()

# ------------------------------------------------------------
# LANGKAH 5: Periksa hasilnya sendiri
# ------------------------------------------------------------
total_debit = koneksi.execute("SELECT SUM(debit) FROM jurnal").fetchone()[0]
total_kredit = koneksi.execute("SELECT SUM(kredit) FROM jurnal").fetchone()[0]

koneksi.close()

print("Database dibuat:", NAMA_DATABASE)
print(f"Total debit  : {total_debit:,}".replace(",", "."))
print(f"Total kredit : {total_kredit:,}".replace(",", "."))
print("SEIMBANG" if total_debit == total_kredit else "TIDAK SEIMBANG")