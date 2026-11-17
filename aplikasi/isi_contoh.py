"""
============================================================
isi_contoh.py -- Mengisi 11 transaksi contoh Oktober 2026
============================================================
Jalankan setelah buat_database.py:

    python isi_contoh.py

File ini memakai fungsi yang SAMA dengan aplikasi web.
Jadi kalau hasilnya benar, halaman web juga benar.

Angka akhir harus sama dengan dokumen rancangan:
    penjualan Rp3.765.000, HPP Rp2.208.000, laba Rp282.000.
"""

import hitung

OLEH = "Pak Hadi"


def barang_id(kode):
    return hitung.ambil_satu("SELECT id FROM barang WHERE kode = ?", (kode,))["id"]


def pelanggan_id(kode):
    return hitung.ambil_satu("SELECT id FROM pelanggan WHERE kode = ?", (kode,))["id"]


print("Mengisi transaksi contoh...")

# 1. 01 Okt - setoran modal tambahan
hitung.simpan_penerimaan(
    "2026-10-01", hitung.id_akun("1101"), hitung.id_akun("3101"),
    2000000, "Setoran modal tambahan anggota", OLEH,
)

# 2. 02 Okt - beli 100 ekor bibit Kohiku 10 cm @ Rp10.000
hitung.simpan_pembelian(
    "2026-10-02", 1, hitung.id_akun("1101"), "Beli bibit Kohiku 10 cm",
    [{"barang_id": barang_id("KOI-10"), "qty": 100, "harga": 10000}], OLEH,
)

# 3. 03 Okt - beli pakan 100 kg @ Rp11.000
hitung.simpan_pembelian(
    "2026-10-03", 2, hitung.id_akun("1102"), "Beli pakan 100 kg",
    [{"barang_id": barang_id("PKN-01"), "qty": 100, "harga": 11000}], OLEH,
)

# 4. 06 Okt - beli 2 serok @ Rp50.000
hitung.simpan_pengeluaran(
    "2026-10-06", hitung.id_akun("6104"), hitung.id_akun("1101"),
    100000, "Beli 2 serok @Rp50.000", OLEH,
)

# 5. 07 Okt - jual 3 koi 30 cm @75.000 + 2 koi 20 cm @40.000
hitung.simpan_penjualan(
    "2026-10-07", pelanggan_id("C-01"), hitung.id_akun("1101"),
    "Pembeli umum, ambil sendiri", 0,
    [
        {"barang_id": barang_id("KOI-30"), "qty": 3, "harga": 75000},
        {"barang_id": barang_id("KOI-20"), "qty": 2, "harga": 40000},
    ],
    OLEH,
)

# 6. 08 Okt - garam grosok 10 kg @ Rp4.000
hitung.simpan_pengeluaran(
    "2026-10-08", hitung.id_akun("6103"), hitung.id_akun("1101"),
    40000, "Beli garam grosok 10 kg @Rp4.000", OLEH,
)

# 7. 10 Okt - retribusi 3 kolam x Rp125.000
hitung.simpan_pengeluaran(
    "2026-10-10", hitung.id_akun("6102"), hitung.id_akun("1101"),
    375000, "Retribusi 3 kolam x Rp125.000", OLEH,
)

# 8. 14 Okt - Pak Darto: 100 koi 10 cm @15.000 + 50 koi 15 cm @22.500
hitung.simpan_penjualan(
    "2026-10-14", pelanggan_id("C-02"), hitung.id_akun("1102"),
    "Pak Darto (pengepul), harga borongan", 0,
    [
        {"barang_id": barang_id("KOI-10"), "qty": 100, "harga": 15000},
        {"barang_id": barang_id("KOI-15"), "qty": 50, "harga": 22500},
    ],
    OLEH,
)

# 9. 20 Okt - pembeli online luar kota, ongkir Rp15.000
hitung.simpan_penjualan(
    "2026-10-20", pelanggan_id("C-03"), hitung.id_akun("1102"),
    "Pembeli online luar kota, ongkir Rp15.000", 15000,
    [
        {"barang_id": barang_id("KOI-30"), "qty": 1, "harga": 90000},
        {"barang_id": barang_id("KOI-20"), "qty": 1, "harga": 45000},
    ],
    OLEH,
)

# 10. 20 Okt - bayar ekspedisi Rp15.000
hitung.simpan_pengeluaran(
    "2026-10-20", hitung.id_akun("6105"), hitung.id_akun("1101"),
    15000, "Bayar ekspedisi pengiriman PJ-003", OLEH,
)

# 11. 25 Okt - Kafe Taman Asri: 10 koi 30 cm @70.000
hitung.simpan_penjualan(
    "2026-10-25", pelanggan_id("C-04"), hitung.id_akun("1101"),
    "Kafe Taman Asri, ambil sendiri", 0,
    [{"barang_id": barang_id("KOI-30"), "qty": 10, "harga": 70000}],
    OLEH,
)

# ------------------------------------------------------------
# Penyesuaian akhir bulan
# ------------------------------------------------------------

# AJP-01 pemakaian pakan 60 kg x Rp11.000
hitung.jalankan(
    """INSERT INTO opname (tanggal, barang_id, qty_hilang, jenis, keterangan)
       VALUES (?, ?, ?, 'pakai', ?)""",
    ("2026-10-31", barang_id("PKN-01"), 60, "Pemakaian pakan Oktober"),
)
hitung.simpan_jurnal("2026-10-31", "AJP-01", hitung.id_akun("6101"),
                     660000, 0, "Pemakaian pakan 60 kg")
hitung.simpan_jurnal("2026-10-31", "AJP-01", hitung.id_akun("1302"),
                     0, 660000, "Pemakaian pakan 60 kg")

# AJP-02 penyusutan
hitung.simpan_jurnal("2026-10-31", "AJP-02", hitung.id_akun("6106"),
                     50000, 0, "Penyusutan peralatan Oktober")
hitung.simpan_jurnal("2026-10-31", "AJP-02", hitung.id_akun("1502"),
                     0, 50000, "Penyusutan peralatan Oktober")

# AJP-03 ikan mati 5 ekor x Rp10.000
hitung.jalankan(
    """INSERT INTO opname (tanggal, barang_id, qty_hilang, jenis, keterangan)
       VALUES (?, ?, ?, 'mati', ?)""",
    ("2026-10-31", barang_id("KOI-10"), 5, "Ikan mati Oktober"),
)
hitung.simpan_jurnal("2026-10-31", "AJP-03", hitung.id_akun("6107"),
                     50000, 0, "Ikan mati 5 ekor 10 cm")
hitung.simpan_jurnal("2026-10-31", "AJP-03", hitung.id_akun("1301"),
                     0, 50000, "Ikan mati 5 ekor 10 cm")


# ------------------------------------------------------------
# Cetak hasil
# ------------------------------------------------------------
def angka(nilai):
    return f"{nilai:,}".replace(",", ".")


laba = hitung.laba_rugi()

print("\n=== HASIL ===")
print("Penjualan koi      :", angka(laba["penjualan_koi"]))
print("Pendapatan ongkir  :", angka(laba["pendapatan_ongkir"]))
print("HPP                :", angka(laba["hpp"]))
print("Laba kotor         :", angka(laba["laba_kotor"]))
print("Total beban        :", angka(laba["beban"]))
print("Laba bersih        :", angka(laba["laba_bersih"]))

persediaan, total_nilai = hitung.nilai_persediaan()
total_ekor = 0

print("\n=== STOK AKHIR ===")
for b in persediaan:
    print(f"{b['kode']:<8} {b['nama']:<20} {b['stok']} {b['satuan']}")
    if b["satuan"] == "ekor":
        total_ekor += b["stok"]

print("Total ekor         :", total_ekor)
print("Nilai persediaan   :", angka(total_nilai))

print("\n=== NERACA SALDO ===")
total_debit = 0
total_kredit = 0

for akun in hitung.neraca_saldo():
    if akun["debit"] == 0 and akun["kredit"] == 0:
        continue
    print(f"{akun['no_akun']:<6} {akun['nama']:<34} "
          f"{angka(akun['debit']):>12} {angka(akun['kredit']):>12}")
    total_debit += akun["debit"]
    total_kredit += akun["kredit"]

print("-" * 68)
print(f"{'TOTAL':<41} {angka(total_debit):>12} {angka(total_kredit):>12}")
print("SEIMBANG" if total_debit == total_kredit else "TIDAK SEIMBANG")