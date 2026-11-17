"""
============================================================
app.py -- Isi aplikasi SiKoi (versi web.py)
============================================================

File inilah yang kamu tulis dan ubah. Isinya hanya dua hal:

    1. Alamat halaman   ->  @aplikasi.halaman("/penjualan")
    2. Isi halaman      ->  fungsi Python biasa

Semua hitungan pembukuan ada di hitung.py (tidak perlu diubah).
Semua tampilan ada di templates/*.html (tidak perlu diubah).

Cara menjalankan:
    python3 buat_database.py      (sekali saja)
    python3 isi_contoh.py         (sekali saja)
    python3 app.py

Lalu buka http://127.0.0.1:8000
"""

from datetime import date

import hitung
from web import Web, alihkan, render, tampilkan

aplikasi = Web()

# ------------------------------------------------------------
# Nomor akun yang sering dipakai, dikumpulkan di satu tempat
# supaya mudah dicari kalau perlu diubah.
# ------------------------------------------------------------
AKUN_KAS = "1101"
AKUN_BANK = "1102"
AKUN_MODAL = "3101"
AKUN_HPP = "5101"
AKUN_PENJUALAN = "4101"
AKUN_ONGKIR = "4102"
AKUN_PERSEDIAAN_KOI = "1301"
AKUN_PERSEDIAAN_PAKAN = "1302"
AKUN_BEBAN_PAKAN = "6101"
AKUN_BEBAN_PENYUSUTAN = "6106"
AKUN_BEBAN_IKAN_MATI = "6107"
AKUN_AKUM_PENYUSUTAN = "1502"


def halaman(req, template, judul, menu, **data):
    """
    Pembungkus kecil supaya tidak perlu menulis nama & jabatan
    di setiap halaman. dasar.html memakainya untuk menu dan header.
    """
    data.setdefault("pesan", None)
    data.setdefault("jenis_pesan", "sukses")

    return tampilkan(
        template,
        judul=judul,
        menu=menu,
        nama=req.sesi.get("nama", ""),
        jabatan=req.sesi.get("jabatan", ""),
        **data,
    )


# ============================================================
# 1. MASUK DAN KELUAR
# ============================================================
@aplikasi.halaman("/login", metode=("GET", "POST"), login=False)
def login(req):
    error = None

    if req.method == "POST":
        pengguna = hitung.ambil_satu(
            "SELECT * FROM pengguna WHERE nama = ? AND jabatan = ? AND pin = ?",
            (req.get("nama").strip(), req.get("jabatan"), req.get("pin").strip()),
        )

        if pengguna:
            req.sesi["nama"] = pengguna["nama"]
            req.sesi["jabatan"] = pengguna["jabatan"]
            return alihkan("/")

        error = "Nama, jabatan, atau PIN tidak cocok."

    daftar = hitung.ambil_semua("SELECT nama, jabatan FROM pengguna ORDER BY id")

    # layout=False karena halaman login punya tampilan sendiri,
    # tanpa menu di atas.
    return {
        "jenis": "html",
        "teks": render("login.html", layout=False, error=error, daftar=daftar),
    }


@aplikasi.halaman("/keluar", login=False)
def keluar(req):
    req.sesi.clear()
    return alihkan("/login")


# ============================================================
# 2. DASHBOARD
# ============================================================
@aplikasi.halaman("/", owner=True)
def dashboard(req):
    persediaan, total_nilai = hitung.nilai_persediaan()
    laba = hitung.laba_rugi()

    jumlah_ekor = sum(b["stok"] for b in persediaan if b["satuan"] == "ekor")

    # Kas dan bank diambil dari neraca saldo.
    kas_bank = 0
    for akun in hitung.neraca_saldo():
        if akun["no_akun"] in (AKUN_KAS, AKUN_BANK):
            kas_bank += akun["debit"] - akun["kredit"]

    # Peringatan stok menipis.
    peringatan = [
        f"Stok {b['nama']} tinggal {b['stok']} {b['satuan']} "
        f"(batas minimum {b['stok_minimum']})."
        for b in persediaan
        if b["stok"] <= b["stok_minimum"]
    ]

    hari_ini = date.today().day
    if hari_ini <= 10:
        peringatan.append(
            "Retribusi kolam jatuh tempo tanggal 10. "
            "3 kolam x Rp125.000 = Rp375.000."
        )
    if hari_ini >= 25:
        peringatan.append("Akhir bulan: waktunya stok opname dan jurnal penyesuaian.")

    return halaman(
        req, "dashboard.html", "Dashboard", "dashboard",
        persediaan=persediaan,
        total_nilai=total_nilai,
        laba=laba,
        jumlah_ekor=jumlah_ekor,
        kas_bank=kas_bank,
        peringatan=peringatan,
    )


# ============================================================
# 3. PENJUALAN
# ============================================================
def hitung_ongkir(cara_kirim, zona, berat):
    """Aturan ongkir dari tabel 4.5 dokumen rancangan."""
    if cara_kirim == "ambil":
        return 0
    if berat > 3:
        return 0                       # di atas 3 kg: gratis ongkir

    tarif = {"dekat": 5000, "sedang": 10000, "jauh": 15000}
    return tarif.get(zona, 0)


@aplikasi.halaman("/penjualan", metode=("GET", "POST"))
def penjualan(req):
    pesan = None
    jenis_pesan = "sukses"

    if req.method == "POST":
        daftar_baris = []
        total_berat = 0.0

        for barang in hitung.ambil_semua("SELECT * FROM barang WHERE satuan = 'ekor'"):
            qty = req.angka(f"qty_{barang['id']}")
            harga = req.angka(f"harga_{barang['id']}")

            if qty <= 0:
                continue

            # Ikan dijual per ekor dengan harga kesepakatan, jadi harga
            # TIDAK boleh terisi otomatis. Kalau kosong, tolak.
            if harga <= 0:
                pesan = (f"Isi harga deal untuk {barang['nama']}. "
                         "Ikan dijual per ekor, harganya kesepakatan "
                         "dengan pembeli.")
                jenis_pesan = "error"
                daftar_baris = []
                break

            stok = hitung.stok_sekarang(barang["id"])
            if qty > stok:
                pesan = f"Stok {barang['nama']} tinggal {stok} ekor."
                jenis_pesan = "error"
                daftar_baris = []
                break

            daftar_baris.append({"barang_id": barang["id"], "qty": qty, "harga": harga})
            total_berat += qty * barang["berat"]

        if jenis_pesan == "error":
            pass                       # pesan sudah diisi di atas
        elif not daftar_baris:
            pesan = "Isi jumlah ikan yang dijual terlebih dahulu."
            jenis_pesan = "error"
        else:
            ongkir = hitung_ongkir(
                req.get("cara_kirim", "ambil"), req.get("zona", "dekat"), total_berat
            )
            no_bukti = hitung.simpan_penjualan(
                req.get("tanggal"),
                req.angka("pelanggan_id"),
                req.angka("akun_kas_id"),
                req.get("keterangan", "").strip(),
                ongkir,
                daftar_baris,
                req.sesi.get("nama", ""),
            )
            pesan = f"Penjualan {no_bukti} tersimpan. Ongkir Rp{ongkir:,}.".replace(",", ".")

    # Daftar ikan + stok terhitung, untuk ditampilkan di tabel.
    ikan = [
        dict(b, stok=hitung.stok_sekarang(b["id"]))
        for b in hitung.ambil_semua(
            "SELECT * FROM barang WHERE satuan = 'ekor' ORDER BY kode")
    ]

    return halaman(
        req, "penjualan.html", "Penjualan", "penjualan",
        ikan=ikan,
        pelanggan=hitung.ambil_semua("SELECT * FROM pelanggan ORDER BY kode"),
        pesan=pesan,
        jenis_pesan=jenis_pesan,
        akun_kas=hitung.id_akun(AKUN_KAS),
        akun_bank=hitung.id_akun(AKUN_BANK),
        hari_ini=date.today().isoformat(),
    )


# ============================================================
# 4. PEMBELIAN
# ============================================================
@aplikasi.halaman("/pembelian", metode=("GET", "POST"))
def pembelian(req):
    pesan = None
    jenis_pesan = "sukses"

    if req.method == "POST":
        daftar_baris = []

        for barang in hitung.ambil_semua("SELECT * FROM barang ORDER BY kode"):
            qty = req.angka(f"qty_{barang['id']}")
            harga = req.angka(f"harga_{barang['id']}")

            if qty <= 0 or harga <= 0:
                continue

            daftar_baris.append({"barang_id": barang["id"], "qty": qty, "harga": harga})

        if not daftar_baris:
            pesan = "Isi jumlah dan harga barang yang dibeli."
            jenis_pesan = "error"
        else:
            no_bukti = hitung.simpan_pembelian(
                req.get("tanggal"),
                req.angka("pemasok_id"),
                req.angka("akun_kas_id"),
                req.get("keterangan", "").strip(),
                daftar_baris,
                req.sesi.get("nama", ""),
            )
            pesan = f"Pembelian {no_bukti} tersimpan. Stok dan HPP sudah diperbarui."

    barang = [
        dict(b, stok=hitung.stok_sekarang(b["id"]))
        for b in hitung.ambil_semua("SELECT * FROM barang ORDER BY kode")
    ]

    return halaman(
        req, "pembelian.html", "Pembelian", "pembelian",
        barang=barang,
        pemasok=hitung.ambil_semua("SELECT * FROM pemasok ORDER BY kode"),
        pesan=pesan,
        jenis_pesan=jenis_pesan,
        akun_kas=hitung.id_akun(AKUN_KAS),
        akun_bank=hitung.id_akun(AKUN_BANK),
        hari_ini=date.today().isoformat(),
    )


# ============================================================
# 5. KAS KELUAR DAN MASUK
# ============================================================
@aplikasi.halaman("/kas", metode=("GET", "POST"), owner=True)
def kas(req):
    pesan = None
    jenis_pesan = "sukses"

    if req.method == "POST":
        jumlah = req.angka("jumlah")

        if jumlah <= 0:
            pesan = "Jumlah harus lebih dari nol."
            jenis_pesan = "error"
        elif req.get("jenis") == "masuk":
            no_bukti = hitung.simpan_penerimaan(
                req.get("tanggal"), req.angka("akun_kas_id"),
                hitung.id_akun(AKUN_MODAL), jumlah,
                req.get("keterangan", "").strip(), req.sesi.get("nama", ""),
            )
            pesan = f"Penerimaan kas {no_bukti} tersimpan."
        else:
            no_bukti = hitung.simpan_pengeluaran(
                req.get("tanggal"), req.angka("akun_beban_id"),
                req.angka("akun_kas_id"), jumlah,
                req.get("keterangan", "").strip(), req.sesi.get("nama", ""),
            )
            pesan = f"Pengeluaran kas {no_bukti} tersimpan."

    catatan = hitung.ambil_semua(
        """SELECT t.*,
                  (SELECT COALESCE(SUM(j.debit), 0) FROM jurnal j
                    WHERE j.no_bukti = t.no_bukti AND j.akun_id = t.akun_kas_id) AS debit_kas,
                  (SELECT COALESCE(SUM(j.kredit), 0) FROM jurnal j
                    WHERE j.no_bukti = t.no_bukti AND j.akun_id = t.akun_kas_id) AS kredit_kas
             FROM transaksi t
            WHERE t.jenis IN ('pengeluaran_kas', 'penerimaan_kas')
            ORDER BY t.tanggal DESC, t.id DESC
            LIMIT 20"""
    )

    return halaman(
        req, "kas.html", "Kas Keluar dan Masuk", "kas",
        akun_beban=hitung.ambil_semua(
            "SELECT * FROM akun WHERE kelompok = 'Beban' ORDER BY no_akun"),
        catatan=catatan,
        pesan=pesan,
        jenis_pesan=jenis_pesan,
        akun_kas=hitung.id_akun(AKUN_KAS),
        akun_bank=hitung.id_akun(AKUN_BANK),
        hari_ini=date.today().isoformat(),
    )


# ============================================================
# 6. PENYESUAIAN AKHIR BULAN
# ============================================================
@aplikasi.halaman("/penyesuaian", metode=("GET", "POST"), owner=True)
def penyesuaian(req):
    pesan = None
    jenis_pesan = "sukses"

    if req.method == "POST":
        tanggal = req.get("tanggal")
        bulan = tanggal[:7]                     # contoh "2026-10"

        if req.get("jenis") == "pakan":
            kg = req.angka("kg")
            pakan = hitung.ambil_satu("SELECT * FROM barang WHERE kode = 'PKN-01'")
            stok = hitung.stok_sekarang(pakan["id"])

            sudah = hitung.ambil_satu(
                "SELECT COUNT(*) AS n FROM jurnal WHERE no_bukti = ?",
                (f"AJP-PKN-{bulan}",),
            )["n"]

            if sudah > 0:
                pesan = f"Pemakaian pakan bulan {bulan} sudah dicatat."
                jenis_pesan = "error"
            elif kg <= 0:
                pesan = "Isi jumlah pakan yang dipakai."
                jenis_pesan = "error"
            elif kg > stok:
                pesan = f"Stok pakan hanya {stok} kg."
                jenis_pesan = "error"
            else:
                nilai = kg * pakan["hpp"]

                hitung.jalankan(
                    """INSERT INTO opname (tanggal, barang_id, qty_hilang, jenis, keterangan)
                       VALUES (?, ?, ?, 'pakai', ?)""",
                    (tanggal, pakan["id"], kg, f"Pemakaian pakan {kg} kg"),
                )

                hitung.simpan_jurnal(tanggal, f"AJP-PKN-{bulan}",
                                     hitung.id_akun(AKUN_BEBAN_PAKAN),
                                     nilai, 0, f"Pemakaian pakan {kg} kg")
                hitung.simpan_jurnal(tanggal, f"AJP-PKN-{bulan}",
                                     hitung.id_akun(AKUN_PERSEDIAAN_PAKAN),
                                     0, nilai, f"Pemakaian pakan {kg} kg")

                pesan = f"Pemakaian pakan {kg} kg tercatat, nilai Rp{nilai:,}.".replace(",", ".")

        elif req.get("jenis") == "penyusutan":
            nilai = req.angka("nilai")

            sudah = hitung.ambil_satu(
                "SELECT COUNT(*) AS n FROM jurnal WHERE no_bukti = ?",
                (f"AJP-PNY-{bulan}",),
            )["n"]

            if sudah > 0:
                pesan = f"Penyusutan bulan {bulan} sudah dicatat."
                jenis_pesan = "error"
            elif nilai <= 0:
                pesan = "Isi nilai penyusutan."
                jenis_pesan = "error"
            else:
                hitung.simpan_jurnal(tanggal, f"AJP-PNY-{bulan}",
                                     hitung.id_akun(AKUN_BEBAN_PENYUSUTAN),
                                     nilai, 0, "Penyusutan peralatan bulan ini")
                hitung.simpan_jurnal(tanggal, f"AJP-PNY-{bulan}",
                                     hitung.id_akun(AKUN_AKUM_PENYUSUTAN),
                                     0, nilai, "Penyusutan peralatan bulan ini")
                pesan = f"Penyusutan Rp{nilai:,} tercatat.".replace(",", ".")

    pakan = hitung.ambil_satu("SELECT * FROM barang WHERE kode = 'PKN-01'")

    return halaman(
        req, "penyesuaian.html", "Penyesuaian Akhir Bulan", "penyesuaian",
        stok_pakan=hitung.stok_sekarang(pakan["id"]) if pakan else 0,
        hpp_pakan=pakan["hpp"] if pakan else 0,
        pesan=pesan,
        jenis_pesan=jenis_pesan,
        akhir_bulan=date.today().replace(day=28).isoformat(),
    )


# ============================================================
# 7. JURNAL DAN NERACA SALDO
# ============================================================
@aplikasi.halaman("/jurnal", metode=("GET", "POST"), owner=True)
def jurnal(req):
    pesan = None
    jenis_pesan = "sukses"

    if req.method == "POST":
        barang_id = req.angka("barang_id")
        qty_hilang = req.angka("qty_hilang")
        keterangan = req.get("keterangan", "Ikan mati").strip()
        stok = hitung.stok_sekarang(barang_id)

        if qty_hilang <= 0:
            pesan = "Jumlah ikan mati harus lebih dari nol."
            jenis_pesan = "error"
        elif qty_hilang > stok:
            pesan = f"Jumlah melebihi stok yang ada ({stok} ekor)."
            jenis_pesan = "error"
        else:
            barang = hitung.ambil_satu("SELECT * FROM barang WHERE id = ?", (barang_id,))
            nilai = qty_hilang * barang["hpp"]

            hitung.jalankan(
                """INSERT INTO opname (tanggal, barang_id, qty_hilang, jenis, keterangan)
                   VALUES (?, ?, ?, 'mati', ?)""",
                (req.get("tanggal"), barang_id, qty_hilang, keterangan),
            )

            jumlah_opname = hitung.ambil_satu("SELECT COUNT(*) AS n FROM opname")["n"]
            no_bukti = f"AJP-{jumlah_opname:03d}"

            hitung.simpan_jurnal(req.get("tanggal"), no_bukti,
                                 hitung.id_akun(AKUN_BEBAN_IKAN_MATI),
                                 nilai, 0, f"{keterangan} ({qty_hilang} ekor)")
            hitung.simpan_jurnal(req.get("tanggal"), no_bukti,
                                 hitung.id_akun(AKUN_PERSEDIAAN_KOI),
                                 0, nilai, f"{keterangan} ({qty_hilang} ekor)")

            pesan = (f"Opname tersimpan: {qty_hilang} ekor, nilai "
                     f"Rp{nilai:,} (jurnal {no_bukti}).").replace(",", ".")

    ns = hitung.neraca_saldo()

    jurnal_terakhir = hitung.ambil_semua(
        """SELECT j.*, a.no_akun, a.nama AS nama_akun
           FROM jurnal j
           JOIN akun a ON a.id = j.akun_id
           ORDER BY j.tanggal DESC, j.id DESC
           LIMIT 40"""
    )

    ikan = [
        dict(b, stok=hitung.stok_sekarang(b["id"]))
        for b in hitung.ambil_semua(
            "SELECT * FROM barang WHERE satuan = 'ekor' ORDER BY kode")
    ]

    return halaman(
        req, "jurnal.html", "Jurnal dan Neraca Saldo", "jurnal",
        ns=[a for a in ns if a["debit"] or a["kredit"]],
        total_debit=sum(a["debit"] for a in ns),
        total_kredit=sum(a["kredit"] for a in ns),
        jurnal=jurnal_terakhir,
        ikan=ikan,
        pesan=pesan,
        jenis_pesan=jenis_pesan,
        hari_ini=date.today().isoformat(),
    )


# ============================================================
# 8. LAPORAN KEUANGAN
# ============================================================
@aplikasi.halaman("/laporan", owner=True)
def laporan(req):
    laba = hitung.laba_rugi()
    ns = hitung.neraca_saldo()

    aset_lancar = []
    aset_tetap = []
    kewajiban = []
    modal_akun = 0

    for akun in ns:
        nilai = akun["debit"] - akun["kredit"]

        if akun["kelompok"] == "Aset Lancar":
            aset_lancar.append({"nama": akun["nama"], "nilai": nilai})
        elif akun["kelompok"] == "Aset Tetap":
            # Akumulasi penyusutan otomatis negatif karena debit - kredit.
            aset_tetap.append({"nama": akun["nama"], "nilai": nilai})
        elif akun["kelompok"] == "Kewajiban":
            kewajiban.append({"nama": akun["nama"], "nilai": -nilai})
        elif akun["kelompok"] == "Ekuitas" and akun["no_akun"] == AKUN_MODAL:
            modal_akun = akun["kredit"] - akun["debit"]

    total_aset_lancar = sum(a["nilai"] for a in aset_lancar)
    total_aset_tetap = sum(a["nilai"] for a in aset_tetap)
    total_aset = total_aset_lancar + total_aset_tetap
    total_kewajiban = sum(k["nilai"] for k in kewajiban)

    modal_awal = 14720000
    modal_akhir = modal_akun + laba["laba_bersih"]

    return halaman(
        req, "laporan.html", "Laporan Keuangan", "laporan",
        laba=laba,
        aset_lancar=aset_lancar,
        aset_tetap=aset_tetap,
        kewajiban=kewajiban,
        total_aset_lancar=total_aset_lancar,
        total_aset_tetap=total_aset_tetap,
        total_aset=total_aset,
        total_kewajiban=total_kewajiban,
        modal_awal=modal_awal,
        modal_tambahan=modal_akun - modal_awal,
        modal_akhir=modal_akhir,
        seimbang=round(total_aset) == round(total_kewajiban + modal_akhir),
    )


# ============================================================
# 9. DATA MASTER
# ============================================================
@aplikasi.halaman("/data", metode=("GET", "POST"), owner=True)
def data(req):
    if req.method == "POST":
        aksi = req.get("aksi")

        if aksi == "tambah_barang":
            hitung.jalankan(
                """INSERT INTO barang
                   (kode, nama, satuan, stok_awal, hpp, harga_jual,
                    stok_minimum, berat, akun_persediaan_id)
                   VALUES (?, ?, 'ekor', 0, ?, ?, ?, ?, ?)""",
                (
                    req.get("kode").strip(),
                    req.get("nama").strip(),
                    req.angka("hpp"),
                    req.angka("harga_jual"),
                    req.angka("stok_minimum"),
                    float(req.get("berat", 0) or 0),
                    hitung.id_akun(AKUN_PERSEDIAAN_KOI),
                ),
            )

        elif aksi == "tambah_pelanggan":
            jumlah = hitung.ambil_satu("SELECT COUNT(*) AS n FROM pelanggan")["n"]

            hitung.jalankan(
                "INSERT INTO pelanggan (kode, nama, jenis) VALUES (?, ?, ?)",
                (f"C-{jumlah + 1:02d}",
                 req.get("nama").strip(),
                 req.get("jenis", "Customer").strip()),
            )

        return alihkan("/data")

    barang = [
        dict(b, stok=hitung.stok_sekarang(b["id"]))
        for b in hitung.ambil_semua("SELECT * FROM barang ORDER BY kode")
    ]

    return halaman(
        req, "data.html", "Data Master", "data",
        barang=barang,
        pelanggan=hitung.ambil_semua("SELECT * FROM pelanggan ORDER BY kode"),
        pemasok=hitung.ambil_semua("SELECT * FROM pemasok ORDER BY kode"),
        akun=hitung.ambil_semua("SELECT * FROM akun ORDER BY no_akun"),
    )


# ============================================================
# 10. MENJALANKAN
# ============================================================
if __name__ == "__main__":
    import os

    aplikasi.jalankan(
        port=int(os.environ.get("PORT", "8000")),
        host=os.environ.get("HOST", "0.0.0.0"),
    )
