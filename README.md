# Sinyal — Intelijen Ekonomi Indonesia

Briefing ekonomi Indonesia harian: makro & moneter, pasar & kurs, komoditas & energi, perdagangan & geopolitik. Terbit tiap hari kerja pukul 07.00 WIB, disusun oleh Claude (Cowork) dan diterbitkan ke GitHub Pages.

Setiap edisi bukan rekap angka, melainkan pembacaan atas **ketegangan antar data** — kontradiksi yang tidak terlihat kalau tiap indikator dibaca sendiri-sendiri.

## Alur

Edisi disusun sepenuhnya di dalam GitHub Actions, tanpa memerlukan komputer siapa pun dalam keadaan menyala.

```
GitHub Actions (07.00 WIB, Sen–Jum)
───────────────────────────────────
scripts/susun_edisi.py
  → riset web lewat Messages API (tool web_search)
  → tulis editions/YYYY-MM-DD.md + data/YYYY-MM-DD.json
  → validasi; gagal berarti tidak ada commit
  → commit dengan GITHUB_TOKEN bawaan
scripts/build.py
  → bangun halaman
  → terbitkan ke GitHub Pages
```

Sumber kebenaran setiap edisi adalah **satu file markdown per hari**. Halaman HTML dibangun ulang tiap kali, tidak ikut di-commit.

Menulis edisi secara manual tetap bisa: tambahkan `editions/YYYY-MM-DD.md` lalu push, dan `pages.yml` akan membangun serta menerbitkannya.

## Penyiapan otomasi

Sekali saja, di Settings repo:

1. **Secrets and variables → Actions → New repository secret**
   Nama `ANTHROPIC_API_KEY`, isi kunci API dari [console Anthropic](https://console.anthropic.com/settings/keys).
2. **Pages → Build and deployment → Source**: GitHub Actions.

Opsional, pada tab **Variables**:

| Variable | Default | Keterangan |
|---|---|---|
| `MODEL_EDISI` | `claude-sonnet-5` | Ganti ke `claude-opus-5` untuk analisis lebih dalam dengan biaya lebih tinggi |
| `MAKS_PENCARIAN` | `15` | Batas pencarian web per edisi |

Perkiraan biaya per edisi dengan Sonnet 5: sekitar US$0,35 (pencarian US$10 per 1.000, token input ~60–100 ribu, output ~8 ribu). Untuk 22 hari kerja, sekitar US$7–10 per bulan. Biaya ini terpisah dari langganan Claude.

Menjalankan di luar jadwal: tab **Actions → Edisi harian → Run workflow**. Centang `paksa` untuk menimpa edisi hari itu bila sudah ada.

Run terjadwal pukul 07.00 selalu menyusun ulang, sehingga edisi hasil uji coba manual pada hari yang sama akan tertimpa oleh edisi pagi yang datanya lebih baru. Menulis edisi dengan tangan untuk hari yang sedang berjalan karena itu perlu disertai penonaktifan sementara workflow `Edisi harian`, agar tidak ditimpa keesokan paginya.

## Validasi

Skrip menolak melakukan commit bila edisi tidak lolos pemeriksaan: frontmatter lengkap, minimal 4 indikator dengan arah `up`/`down`/`flat` yang sah, minimal 4 bagian tema yang masing-masing punya baris sumber dan paragraf pembacaan, minimal 4 butir pantau, minimal 4 tautan sumber, tidak ada isian kosong seperti `n/a` pada tabel fakta, tidak ada kalimat berbahasa Inggris yang tersalin mentah ke dalam prosa, serta JSON yang berisi nilai numerik sungguhan, bukan string berformat.

Memeriksa satu berkas secara manual:

```bash
python3 scripts/susun_edisi.py --validasi editions/2026-09-03.md
```

Perintah itu juga mencatat mutu yang tidak sampai menggagalkan penerbitan: tik gaya yang dibatasi `prompts/edisi.md` (tanda pisah dalam prosa, konstruksi antitesis, frasa bergaya aforisme), kalimat yang nyaris kembar, dan sumber dari penerbit di luar daftar yang disetujui. Pada run terjadwal, catatan ini beserta biaya nyata edisi muncul di halaman ringkasan run Actions, sehingga terbaca tanpa membuka log.

## Struktur

```
editions/YYYY-MM-DD.md              Sumber edisi                           ← di-commit
data/YYYY-MM-DD.json                Data numerik untuk seri waktu          ← di-commit
prompts/edisi.md                    Instruksi bahasa dan format edisi      ← di-commit
scripts/susun_edisi.py              Penyusun edisi lewat Anthropic API     ← di-commit
scripts/build.py                    Pembangun situs (stdlib Python saja)   ← di-commit
.github/workflows/edisi-harian.yml  Susun, bangun, terbitkan (terjadwal)   ← di-commit
.github/workflows/pages.yml         Bangun dan terbitkan saat push manual  ← di-commit

index.html                     Edisi terbaru                                ← hasil build
arsip.html                     Daftar seluruh edisi                         ← hasil build
editions/YYYY-MM-DD.html       Halaman jadi per edisi                       ← hasil build
data/index.json                Manifest edisi untuk arsip                   ← hasil build
```

## Format edisi (`editions/YYYY-MM-DD.md`)

```markdown
---
jam_edisi: 07.00 WIB
data_terakhir: 2–3 Sep 2026
label_khusus: Edisi perdana        # opsional, hapus baris ini kalau tidak ada
---

## Sinyal Utama

Satu paragraf. **Tebal** dan [tautan](https://...) didukung.

## Indikator

- Label: Nilai — keterangan (arah)
```

Enam baris untuk strip indikator. `arah` salah satu dari `up`, `down`, `flat` (opsional, default `flat`).

```markdown
## Nama Bagian Tema

_Sumber: penerbit — tanggal rilis_

Paragraf pembacaan. Boleh lebih dari satu, pisahkan dengan baris kosong.

- Label fakta: Nilai
- Label fakta lain: Nilai
```

Judul bagian tema bebas (bukan kata kunci tetap) — semua judul selain empat yang dikenali (`Sinyal Utama`, `Indikator`, `Yang Perlu Dipantau`, `Sumber`) otomatis dirender sebagai kartu tema di grid. Baris `_Sumber: ..._` di awal bagian opsional. Daftar `- Label: Nilai` dirender sebagai tabel fakta.

```markdown
## Yang Perlu Dipantau

- **[Tag]** Judul — Deskripsi
```

`Tag` bebas (mis. `Berlangsung`, `RDG September`, `Belum terjadwal`). Tag persis `Berlangsung` diberi penanda mendesak.

```markdown
## Sumber

- [Judul sumber](https://...)
```

## Membangun ulang

```bash
python3 scripts/build.py
```

Membaca semua `editions/*.md`, menghasilkan halaman mandiri, `index.html`, `arsip.html`, dan `data/index.json`. Tanpa dependensi di luar pustaka standar Python — cepat, deterministik, tidak butuh `pip install` di Actions.

## Menambah edisi baru

1. Tulis `editions/YYYY-MM-DD.md` mengikuti format di atas
2. (Opsional) simpan angka numerik mentah di `data/YYYY-MM-DD.json` — untuk analisis seri waktu, terpisah dari teks tampilan
3. Commit dan push ke `main`

Workflow `pages.yml` menjalankan `build.py` lalu menerbitkan hasilnya ke GitHub Pages. Untuk memeriksa lokal sebelum push, jalankan `build.py` sendiri — keluarannya diabaikan git (`.gitignore`).

## Data

`data/*.json` adalah bagian paling awet dari repo ini: angka mentah tiap edisi dalam bentuk numerik (bukan string tampilan seperti "5,75%"), untuk dianalisis sebagai seri waktu.

```python
import json, pathlib
import pandas as pd

rows = [json.loads(p.read_text()) for p in sorted(pathlib.Path("data").glob("2*.json"))
        if p.name != "index.json"]
df = pd.json_normalize(rows).set_index("tanggal")
df[["makro.bi_rate_persen", "makro.inflasi_yoy_persen", "pasar.usd_idr"]]
```

## Sumber

Sumber primer didahulukan — [BPS](https://www.bps.go.id), [Bank Indonesia](https://www.bi.go.id), Kementerian Perdagangan — lalu media kredibel (ANTARA, CNBC Indonesia, Bisnis.com, Kontan, Kompas, Katadata). Setiap edisi mencantumkan tautan sumber di bagian bawah halaman, dan setiap bagian tema diberi stempel sumber beserta tanggal rilisnya.

Angka penting diverifikasi di minimal dua sumber bila memungkinkan. Data yang tidak ditemukan dihapus barisnya, tidak pernah diisi perkiraan.

## Penafian

Ringkasan disusun dari laporan publik yang tersedia pada tanggal terbit dan dapat berubah seiring rilis data baru. Angka pasar bersifat indikatif dan bukan kutipan resmi bursa. **Bukan nasihat investasi.**
