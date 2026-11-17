"""
============================================================
hitung.py -- Semua aturan pembukuan, dalam bahasa Python
============================================================
File ini tidak berisi tampilan (HTML). Isinya hanya hitungan:
stok, jurnal, HPP rata-rata, dan laporan.

Kalau kamu membandingkan dengan versi PHP, isinya sama persis.
Bedanya hanya bahasa pemrogramannya.
"""

import sqlite3

# Nama file database. Satu file, isinya semua tabel.
NAMA_DATABASE = "sikoi.db"


# ------------------------------------------------------------
# 1. Menyambung ke database
# ------------------------------------------------------------
def sambung():
    """Membuka koneksi ke SQLite dan mengembalikannya."""
    # row_factory membuat hasil query bisa diakses seperti kamus:
    # baris["nama"], bukan baris[1]
    koneksi = sqlite3.connect(NAMA_DATABASE)
    koneksi.row_factory = sqlite3.Row
    return koneksi


def ambil_semua(sql, parameter=()):
    """Mengambil banyak baris. Hasilnya list."""
    koneksi = sambung()
    try:
        return koneksi.execute(sql, parameter).fetchall()
    finally:
        koneksi.close()          # selalu tutup, walaupun terjadi error


def ambil_satu(sql, parameter=()):
    """Mengambil satu baris. Hasilnya sqlite3.Row atau None."""
    koneksi = sambung()
    try:
        return koneksi.execute(sql, parameter).fetchone()
    finally:
        koneksi.close()


def jalankan(sql, parameter=()):
    """Menjalankan INSERT / UPDATE / DELETE. Mengembalikan id baris baru."""
    koneksi = sambung()
    try:
        kursor = koneksi.execute(sql, parameter)
        koneksi.commit()         # simpan perubahan secara permanen
        return kursor.lastrowid
    finally:
        koneksi.close()


# ------------------------------------------------------------
# 2. Mencari id akun dari nomor akun
# ------------------------------------------------------------
def id_akun(no_akun):
    akun = ambil_satu("SELECT id FROM akun WHERE no_akun = ?", (no_akun,))
    if akun is None:
        raise ValueError(f"Akun {no_akun} tidak ditemukan. Jalankan buat_database.py dulu.")
    return akun["id"]


# ------------------------------------------------------------
# 3. Stok sekarang (dihitung, bukan disimpan)
# ------------------------------------------------------------
def stok_sekarang(barang_id):
    """
    Rumus: stok awal + masuk - keluar - hilang.
    Dihitung ulang dari transaksi supaya tidak pernah "bohong".
    """
    barang = ambil_satu("SELECT * FROM barang WHERE id = ?", (barang_id,))
    if barang is None:
        return 0

    masuk = ambil_satu(
        """SELECT COALESCE(SUM(tb.qty), 0) AS jumlah
           FROM transaksi_baris tb
           JOIN transaksi t ON t.id = tb.transaksi_id
           WHERE tb.barang_id = ? AND t.jenis = 'pembelian'""",
        (barang_id,),
    )["jumlah"]

    keluar = ambil_satu(
        """SELECT COALESCE(SUM(tb.qty), 0) AS jumlah
           FROM transaksi_baris tb
           JOIN transaksi t ON t.id = tb.transaksi_id
           WHERE tb.barang_id = ? AND t.jenis = 'penjualan'""",
        (barang_id,),
    )["jumlah"]

    hilang = ambil_satu(
        "SELECT COALESCE(SUM(qty_hilang), 0) AS jumlah FROM opname WHERE barang_id = ?",
        (barang_id,),
    )["jumlah"]

    return barang["stok_awal"] + masuk - keluar - hilang


# ------------------------------------------------------------
# 4. Menyimpan satu baris jurnal
# ------------------------------------------------------------
def simpan_jurnal(tanggal, no_bukti, akun_id, debit, kredit, keterangan):
    """Setiap transaksi memanggil ini 2 kali atau lebih: debit dan kredit."""
    jalankan(
        """INSERT INTO jurnal (tanggal, no_bukti, akun_id, debit, kredit, keterangan)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tanggal, no_bukti, akun_id, debit, kredit, keterangan),
    )


# ------------------------------------------------------------
# 5. Nomor bukti otomatis: PJ-001, PJ-002, ...
# ------------------------------------------------------------
def nomor_bukti(jenis):
    awalan = {
        "pembelian": "PB",
        "penjualan": "PJ",
        "penerimaan_kas": "PK",
        "pengeluaran_kas": "KK",
    }
    kode = awalan[jenis]

    jumlah = ambil_satu(
        "SELECT COUNT(*) AS n FROM transaksi WHERE no_bukti LIKE ?", (kode + "-%",)
    )["n"]

    return f"{kode}-{jumlah + 1:03d}"


# ------------------------------------------------------------
# 6. PEMBELIAN
# ------------------------------------------------------------
def simpan_pembelian(tanggal, pemasok_id, akun_kas_id, keterangan, daftar_baris, oleh):
    """
    daftar_baris = [{"barang_id": 1, "qty": 100, "harga": 10000}, ...]

    Jurnal: Debit Persediaan, Kredit Kas/Bank.
    HPP rata-rata dihitung ulang setelah stok bertambah.
    """
    no_bukti = nomor_bukti("pembelian")
    total = sum(b["qty"] * b["harga"] for b in daftar_baris)

    transaksi_id = jalankan(
        """INSERT INTO transaksi
           (tanggal, no_bukti, jenis, pemasok_id, keterangan, akun_kas_id, dibuat_oleh)
           VALUES (?, ?, 'pembelian', ?, ?, ?, ?)""",
        (tanggal, no_bukti, pemasok_id, keterangan, akun_kas_id, oleh),
    )

    for baris in daftar_baris:
        barang = ambil_satu("SELECT * FROM barang WHERE id = ?", (baris["barang_id"],))

        stok_lama = stok_sekarang(baris["barang_id"])
        nilai_lama = stok_lama * barang["hpp"]

        stok_baru = stok_lama + baris["qty"]
        nilai_baru = nilai_lama + (baris["qty"] * baris["harga"])

        # Rata-rata bergerak, dibulatkan ke rupiah penuh.
        hpp_baru = round(nilai_baru / stok_baru) if stok_baru > 0 else baris["harga"]

        jalankan(
            """INSERT INTO transaksi_baris
               (transaksi_id, barang_id, qty, harga_satuan, hpp_satuan)
               VALUES (?, ?, ?, ?, ?)""",
            (transaksi_id, baris["barang_id"], baris["qty"], baris["harga"], hpp_baru),
        )

        jalankan("UPDATE barang SET hpp = ? WHERE id = ?", (hpp_baru, baris["barang_id"]))

    # Jurnal persediaan (dikelompokkan per akun persediaan).
    per_akun = {}
    for baris in daftar_baris:
        barang = ambil_satu("SELECT * FROM barang WHERE id = ?", (baris["barang_id"],))
        akun = barang["akun_persediaan_id"]
        per_akun[akun] = per_akun.get(akun, 0) + baris["qty"] * baris["harga"]

    for akun_id, nilai in per_akun.items():
        simpan_jurnal(tanggal, no_bukti, akun_id, nilai, 0, f"Pembelian {no_bukti}")

    simpan_jurnal(tanggal, no_bukti, akun_kas_id, 0, total, f"Pembayaran {no_bukti}")

    return no_bukti


# ------------------------------------------------------------
# 7. PENJUALAN
# ------------------------------------------------------------
def simpan_penjualan(tanggal, pelanggan_id, akun_kas_id, keterangan, ongkir, daftar_baris, oleh):
    """
    Jurnal 1: Debit Kas/Bank, Kredit Penjualan Koi (+ Pendapatan Ongkir).
    Jurnal 2: Debit HPP, Kredit Persediaan Ikan Koi.

    Dua jurnal inilah yang membuat metode perpetual berbeda dari
    metode periodik: laba diketahui saat itu juga.
    """
    no_bukti = nomor_bukti("penjualan")

    total_jual = 0
    total_hpp = 0

    for baris in daftar_baris:
        barang = ambil_satu("SELECT * FROM barang WHERE id = ?", (baris["barang_id"],))
        total_jual += baris["qty"] * baris["harga"]
        total_hpp += baris["qty"] * barang["hpp"]

    transaksi_id = jalankan(
        """INSERT INTO transaksi
           (tanggal, no_bukti, jenis, pelanggan_id, keterangan, akun_kas_id, ongkir, dibuat_oleh)
           VALUES (?, ?, 'penjualan', ?, ?, ?, ?, ?)""",
        (tanggal, no_bukti, pelanggan_id, keterangan, akun_kas_id, ongkir, oleh),
    )

    for baris in daftar_baris:
        barang = ambil_satu("SELECT * FROM barang WHERE id = ?", (baris["barang_id"],))
        jalankan(
            """INSERT INTO transaksi_baris
               (transaksi_id, barang_id, qty, harga_satuan, hpp_satuan)
               VALUES (?, ?, ?, ?, ?)""",
            (transaksi_id, baris["barang_id"], baris["qty"], baris["harga"], barang["hpp"]),
        )

    # Jurnal 1: uang masuk
    simpan_jurnal(tanggal, no_bukti, akun_kas_id, total_jual + ongkir, 0,
                  f"Penerimaan {no_bukti}")
    simpan_jurnal(tanggal, no_bukti, id_akun("4101"), 0, total_jual,
                  f"Penjualan koi {no_bukti}")

    if ongkir > 0:
        simpan_jurnal(tanggal, no_bukti, id_akun("4102"), 0, ongkir,
                      f"Ongkir {no_bukti}")

    # Jurnal 2: HPP dan pengurangan persediaan
    if total_hpp > 0:
        simpan_jurnal(tanggal, no_bukti, id_akun("5101"), total_hpp, 0,
                      f"HPP {no_bukti}")
        simpan_jurnal(tanggal, no_bukti, id_akun("1301"), 0, total_hpp,
                      f"Pengurangan persediaan {no_bukti}")

    return no_bukti


# ------------------------------------------------------------
# 8. PENGELUARAN KAS (beban)
# ------------------------------------------------------------
def simpan_pengeluaran(tanggal, akun_beban_id, akun_kas_id, jumlah, keterangan, oleh):
    no_bukti = nomor_bukti("pengeluaran_kas")

    jalankan(
        """INSERT INTO transaksi
           (tanggal, no_bukti, jenis, keterangan, akun_kas_id, dibuat_oleh)
           VALUES (?, ?, 'pengeluaran_kas', ?, ?, ?)""",
        (tanggal, no_bukti, keterangan, akun_kas_id, oleh),
    )

    simpan_jurnal(tanggal, no_bukti, akun_beban_id, jumlah, 0, keterangan)
    simpan_jurnal(tanggal, no_bukti, akun_kas_id, 0, jumlah, keterangan)

    return no_bukti


# ------------------------------------------------------------
# 9. PENERIMAAN KAS (setoran modal)
# ------------------------------------------------------------
def simpan_penerimaan(tanggal, akun_kas_id, akun_lawan_id, jumlah, keterangan, oleh):
    no_bukti = nomor_bukti("penerimaan_kas")

    jalankan(
        """INSERT INTO transaksi
           (tanggal, no_bukti, jenis, keterangan, akun_kas_id, dibuat_oleh)
           VALUES (?, ?, 'penerimaan_kas', ?, ?, ?)""",
        (tanggal, no_bukti, keterangan, akun_kas_id, oleh),
    )

    simpan_jurnal(tanggal, no_bukti, akun_kas_id, jumlah, 0, keterangan)
    simpan_jurnal(tanggal, no_bukti, akun_lawan_id, 0, jumlah, keterangan)

    return no_bukti


# ------------------------------------------------------------
# 10. NERACA SALDO
# ------------------------------------------------------------
def neraca_saldo():
    """
    Saldo = total debit - total kredit, lalu disesuaikan dengan
    saldo normal akun. Hasilnya list of dict dengan kunci:
    no_akun, nama, kelompok, saldo_normal, debit, kredit.
    """
    hasil = ambil_semua(
        """SELECT a.id, a.no_akun, a.nama, a.kelompok, a.saldo_normal,
                  COALESCE(SUM(j.debit), 0) AS total_debit,
                  COALESCE(SUM(j.kredit), 0) AS total_kredit
           FROM akun a
           LEFT JOIN jurnal j ON j.akun_id = a.id
           GROUP BY a.id
           ORDER BY a.no_akun"""
    )

    daftar = []
    for baris in hasil:
        selisih = baris["total_debit"] - baris["total_kredit"]
        debit = 0
        kredit = 0

        if baris["saldo_normal"] == "Debit":
            if selisih >= 0:
                debit = selisih
            else:
                kredit = -selisih
        else:
            if selisih <= 0:
                kredit = -selisih
            else:
                debit = selisih

        daftar.append({
            "id": baris["id"],
            "no_akun": baris["no_akun"],
            "nama": baris["nama"],
            "kelompok": baris["kelompok"],
            "saldo_normal": baris["saldo_normal"],
            "debit": debit,
            "kredit": kredit,
        })

    return daftar


# ------------------------------------------------------------
# 11. NILAI PERSEDIAAN
# ------------------------------------------------------------
def nilai_persediaan():
    daftar = []
    total = 0

    for barang in ambil_semua("SELECT * FROM barang ORDER BY kode"):
        stok = stok_sekarang(barang["id"])
        nilai = stok * barang["hpp"]
        total += nilai

        daftar.append({
            "id": barang["id"],
            "kode": barang["kode"],
            "nama": barang["nama"],
            "satuan": barang["satuan"],
            "stok": stok,
            "hpp": barang["hpp"],
            "harga_jual": barang["harga_jual"],
            "stok_minimum": barang["stok_minimum"],
            "berat": barang["berat"],
            "nilai": nilai,
        })

    return daftar, total


# ------------------------------------------------------------
# 12. LABA RUGI
# ------------------------------------------------------------
def laba_rugi():
    pendapatan = 0
    penjualan_koi = 0
    pendapatan_ongkir = 0
    hpp = 0
    beban = 0
    rincian_beban = []

    for akun in neraca_saldo():
        if akun["kelompok"] == "Pendapatan":
            nilai = akun["kredit"] - akun["debit"]
            pendapatan += nilai

            if akun["no_akun"] == "4101":
                penjualan_koi = nilai
            else:
                pendapatan_ongkir = nilai

        elif akun["kelompok"] == "HPP":
            hpp += akun["debit"]

        elif akun["kelompok"] == "Beban":
            beban += akun["debit"]
            rincian_beban.append(akun)

    return {
        "pendapatan": pendapatan,
        "penjualan_koi": penjualan_koi,
        "pendapatan_ongkir": pendapatan_ongkir,
        "hpp": hpp,
        "laba_kotor": penjualan_koi - hpp,
        "beban": beban,
        "laba_bersih": pendapatan - hpp - beban,
        "rincian_beban": rincian_beban,
    }