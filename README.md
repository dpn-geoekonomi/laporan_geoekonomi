# Sinyal — Intelijen Ekonomi Indonesia

Briefing ekonomi Indonesia harian: makro & moneter, pasar & kurs, komoditas & energi, perdagangan & geopolitik. Terbit tiap hari kerja pukul 07.00 WIB, disusun oleh Claude (Cowork) dan diterbitkan ke GitHub Pages.

Setiap edisi bukan rekap angka, melainkan pembacaan atas **ketegangan antar data** — kontradiksi yang tidak terlihat kalau tiap indikator dibaca sendiri-sendiri.

## Alur

```
Claude Cowork                         GitHub
──────────────                        ──────
Input berita (riset web)     →
Resume intelijen ekonomi     →
                                       editions/YYYY-MM-DD.md   (commit)
                                       scripts/build.py          (Actions)
                                       Publish → GitHub Pages
```

Sumber kebenaran setiap edisi adalah **satu file markdown per hari**. GitHub Actions membangunnya jadi halaman bergaya setiap kali di-push — tidak ada HTML hasil generate yang ikut ter-commit.

## Struktur

```
editions/YYYY-MM-DD.md         Sumber edisi (ditulis manusia atau Claude)   ← di-commit
data/YYYY-MM-DD.json           Data numerik mentah, untuk seri waktu        ← di-commit
scripts/build.py               Pembangun situs (stdlib Python saja)        ← di-commit
.github/workflows/pages.yml    Build + terbit ke Pages tiap push           ← di-commit

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
