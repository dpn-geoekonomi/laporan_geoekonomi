#!/usr/bin/env python3
"""
Susun edisi harian Sinyal lewat Anthropic Messages API, lalu tulis ke repo.

Dijalankan oleh .github/workflows/edisi-harian.yml setiap hari kerja.
Tidak memerlukan laptop, token git, maupun sesi Claude yang hidup.

Alur:
  1. Baca prompts/edisi.md dan edisi terakhir sebagai rujukan gaya.
  2. Panggil API dengan tool web_search aktif; model meriset sendiri.
  3. Pisahkan blok markdown dan JSON dari jawaban.
  4. Validasi keduanya, termasuk memarse markdown dengan parser build.py.
  5. Tulis editions/<tanggal>.md dan data/<tanggal>.json.

Keluar dengan kode selain 0 bila gagal, agar workflow berhenti dan tidak
sempat melakukan commit atas edisi yang rusak.

Variabel lingkungan:
  ANTHROPIC_API_KEY  wajib
  MODEL_EDISI        opsional, default claude-sonnet-5
  PAKSA              "true" untuk menimpa edisi yang sudah ada
  MAKS_PENCARIAN     opsional, default 15

Pakai:
  python3 scripts/susun_edisi.py
  python3 scripts/susun_edisi.py --validasi editions/2026-09-03.md
"""

import datetime
import json
import os
import pathlib
import re
import sys
import time

SCRIPTS = pathlib.Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import build  # noqa: E402  — parser markdown yang sama dengan pembangun situs

WIB = datetime.timezone(datetime.timedelta(hours=7))

MD_MULAI, MD_SELESAI = "===EDISI_MD_MULAI===", "===EDISI_MD_SELESAI==="
JSON_MULAI, JSON_SELESAI = "===DATA_JSON_MULAI===", "===DATA_JSON_SELESAI==="

MIN_TEMA = 4
MIN_INDIKATOR = 4
MIN_PANTAU = 4
MIN_SUMBER = 4

# Penanda bahwa model mengisi lubang data alih-alih menghapus barisnya.
ISIAN_KOSONG = re.compile(
    r"^\s*(n/?a|tidak tersedia|belum tersedia|tbd|todo|-{1,3}|\?+|xxx+)\s*$",
    re.IGNORECASE,
)


class Gagal(Exception):
    """Kegagalan yang harus menghentikan workflow tanpa commit."""


# --------------------------------------------------------------------------
# Pengambilan blok
# --------------------------------------------------------------------------

def ambil_blok(teks: str, mulai: str, selesai: str, nama: str) -> str:
    i = teks.find(mulai)
    j = teks.find(selesai)
    if i == -1 or j == -1 or j < i:
        raise Gagal(f"Blok {nama} tidak ditemukan dalam jawaban model.")
    return teks[i + len(mulai):j].strip()


# --------------------------------------------------------------------------
# Validasi
# --------------------------------------------------------------------------

def validasi_markdown(md: str, iso: str) -> dict:
    """Parse dengan parser produksi lalu periksa kelengkapannya."""
    if not md.startswith("---"):
        raise Gagal("Edisi tidak diawali frontmatter.")

    try:
        doc = build.parse_edition(iso, md)
    except Exception as e:
        raise Gagal(f"Markdown gagal diparse build.py: {e}") from e

    meta = doc["meta"]
    for kunci in ("jam_edisi", "data_terakhir"):
        if not meta.get(kunci):
            raise Gagal(f"Frontmatter kehilangan '{kunci}'.")

    if len(doc["sinyal"]) < 200:
        raise Gagal(
            f"Sinyal Utama terlalu pendek ({len(doc['sinyal'])} karakter); "
            "diminta 3–5 kalimat."
        )

    if len(doc["indikator"]) < MIN_INDIKATOR:
        raise Gagal(
            f"Hanya {len(doc['indikator'])} indikator, minimal {MIN_INDIKATOR}."
        )
    for t in doc["indikator"]:
        if not t["nilai"]:
            raise Gagal(f"Indikator '{t['label']}' tidak punya nilai.")

    # Arah yang salah tulis, mis. "(naik)", tidak dikenali parser dan diam-diam
    # jatuh ke "flat" sehingga warnanya keliru di halaman. Periksa teks mentahnya.
    blok = re.search(r"^##\s+Indikator\s*$(.*?)(?=^##\s|\Z)", md, re.S | re.M | re.I)
    if blok:
        for baris in blok.group(1).splitlines():
            baris = baris.strip()
            if not baris.startswith("- "):
                continue
            akhiran = re.search(r"\(([^()]*)\)\s*$", baris)
            if akhiran and akhiran.group(1).strip().lower() not in ("up", "down", "flat"):
                raise Gagal(
                    f"Arah indikator tidak sah pada baris: {baris!r}. "
                    "Gunakan (up), (down), atau (flat)."
                )

    if len(doc["brief"]) < MIN_TEMA:
        raise Gagal(
            f"Hanya {len(doc['brief'])} bagian tema, minimal {MIN_TEMA}."
        )
    for s in doc["brief"]:
        if not s["src"]:
            raise Gagal(f"Bagian '{s['judul']}' tidak punya baris _Sumber: ..._")
        if not s["paragraphs"]:
            raise Gagal(
                f"Bagian '{s['judul']}' hanya berisi daftar fakta tanpa paragraf."
            )
        for k, v in s["facts"]:
            if ISIAN_KOSONG.match(v):
                raise Gagal(
                    f"Bagian '{s['judul']}' memuat isian kosong pada '{k}': {v!r}. "
                    "Baris tanpa data harus dihapus, bukan diisi penanda."
                )

    if len(doc["watch"]) < MIN_PANTAU:
        raise Gagal(
            f"Hanya {len(doc['watch'])} butir pantau, minimal {MIN_PANTAU}."
        )

    if len(doc["sumber"]) < MIN_SUMBER:
        raise Gagal(
            f"Hanya {len(doc['sumber'])} sumber, minimal {MIN_SUMBER}."
        )
    for u in doc["sumber"]:
        if not u["url"].startswith("http"):
            raise Gagal(f"Sumber '{u['judul']}' bukan URL sah: {u['url']}")

    return doc


def hanya_prosa(md: str) -> str:
    """
    Sisakan paragraf pembacaan saja.

    Bagian Indikator, Yang Perlu Dipantau, dan Sumber memakai tanda pisah
    sebagai pemisah wajib format, begitu pula baris _Sumber: ... — tanggal_
    dan daftar fakta. Menghitungnya sebagai gaya penulisan akan membuat
    peringatan selalu menyala dan akhirnya diabaikan.
    """
    teks = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)
    for judul in ("Indikator", "Yang Perlu Dipantau", "Sumber"):
        teks = re.sub(
            rf"^##\s+{judul}\s*$.*?(?=^##\s|\Z)", "", teks, flags=re.S | re.M | re.I
        )
    baris = [
        b for b in teks.splitlines()
        if not b.strip().startswith(("_", "- ", "#"))
    ]
    return "\n".join(baris)


def periksa_gaya(md: str) -> list:
    """Hitung tik gaya yang dibatasi prompt. Peringatan, bukan penggagal."""
    prosa = hanya_prosa(md)
    catatan = []

    tanda_pisah = len(re.findall(r"\s—\s", prosa))
    if tanda_pisah > 2:
        catatan.append(f"tanda pisah dalam prosa {tanda_pisah} kali (batas 2)")

    antitesis = len(re.findall(r"\bbukan\b[^.]{0,80}\bmelainkan\b", prosa, re.I))
    antitesis += len(re.findall(r",\s*bukan\s+\w+", prosa, re.I))
    if antitesis > 1:
        catatan.append(f"konstruksi antitesis {antitesis} kali (batas 1)")

    aforisme = len(re.findall(r"\b(?:di atas kertas|sudah lelah|apa adanya saja)\b",
                              prosa, re.I))
    if aforisme:
        catatan.append(f"frasa bergaya aforisme terdeteksi {aforisme} kali")

    return catatan


def validasi_json(mentah: str, iso: str) -> dict:
    try:
        data = json.loads(mentah)
    except json.JSONDecodeError as e:
        raise Gagal(f"JSON tidak sah: {e}") from e

    if data.get("tanggal") != iso:
        raise Gagal(
            f"Field 'tanggal' berisi {data.get('tanggal')!r}, seharusnya {iso!r}."
        )

    for tema in ("makro", "pasar", "komoditas", "perdagangan"):
        blok = data.get(tema)
        if not isinstance(blok, dict) or not blok:
            raise Gagal(f"JSON kehilangan objek '{tema}' atau objeknya kosong.")
        angka = [v for v in blok.values() if isinstance(v, (int, float))]
        if not angka:
            raise Gagal(
                f"Objek '{tema}' tidak memuat satu pun nilai numerik; "
                "angka harus berupa number, bukan string berformat."
            )

    if len(data.get("sumber") or []) < MIN_SUMBER:
        raise Gagal(f"JSON memuat kurang dari {MIN_SUMBER} sumber.")

    return data


# --------------------------------------------------------------------------
# Pemanggilan API
# --------------------------------------------------------------------------

def rujukan_gaya() -> str:
    """Edisi terakhir, dipakai model sebagai contoh format dan nada."""
    lama = sorted((ROOT / "editions").glob("*.md"), reverse=True)
    if not lama:
        return ""
    return (
        "\n\n---\n\n## Bagian E — Edisi sebelumnya sebagai rujukan format\n\n"
        "Berikut edisi terakhir yang terbit. Tiru strukturnya dan pertahankan "
        "konsistensi nada, tetapi jangan menyalin isinya; angka dan analisis "
        "harus berasal dari riset hari ini.\n\n```markdown\n"
        + lama[0].read_text(encoding="utf-8").strip()
        + "\n```\n"
    )


def susun(iso: str, label: str) -> str:
    try:
        import anthropic
    except ImportError as e:
        raise Gagal("Paket 'anthropic' belum terpasang (pip install anthropic).") from e

    kunci = os.environ.get("ANTHROPIC_API_KEY")
    if not kunci:
        raise Gagal("ANTHROPIC_API_KEY tidak diset.")

    model = os.environ.get("MODEL_EDISI", "claude-sonnet-5").strip()
    effort = os.environ.get("EFFORT", "").strip().lower()
    maks_cari = int(os.environ.get("MAKS_PENCARIAN", "12"))
    maks_token = int(os.environ.get("MAKS_TOKEN", "32000"))

    prompt = (ROOT / "prompts" / "edisi.md").read_text(encoding="utf-8")
    prompt = prompt.replace("{TANGGAL_ISO}", iso).replace("{TANGGAL_LABEL}", label)
    prompt += rujukan_gaya()

    klien = anthropic.Anthropic(api_key=kunci)

    # Prefiks statis (instruksi + edisi rujukan) di-cache, sehingga tiap putaran
    # pencarian membacanya dengan tarif cache, bukan tarif input penuh.
    isi = [{
        "type": "text",
        "text": prompt,
        "cache_control": {"type": "ephemeral"},
    }]

    argumen = {
        "model": model,
        "max_tokens": maks_token,
        "messages": [{"role": "user", "content": isi}],
        "tools": [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": maks_cari,
            "user_location": {"type": "approximate", "country": "ID"},
        }],
    }
    if effort:
        argumen["output_config"] = {"effort": effort}

    galat_terakhir = None
    for percobaan in range(1, 4):
        try:
            jejak = f"{model}" + (f" effort={effort}" if effort else "")
            print(f"Memanggil {jejak} (percobaan {percobaan}/3)...", flush=True)
            # Wajib streaming: permintaan dengan max_tokens besar ditambah
            # belasan putaran pencarian bisa melampaui sepuluh menit, dan SDK
            # menolak permintaan non-streaming selama itu sebelum dikirim.
            with klien.messages.stream(**argumen) as aliran:
                resp = aliran.get_final_message()
            teks = "".join(
                b.text for b in resp.content if getattr(b, "type", "") == "text"
            )
            cari = sum(
                1 for b in resp.content
                if getattr(b, "type", "") == "server_tool_use"
            )
            lapor_biaya(model, resp.usage, cari)
            if MD_MULAI in teks and JSON_MULAI in teks:
                return teks
            galat_terakhir = "jawaban tidak memuat penanda blok yang diminta"
            print(f"  gagal: {galat_terakhir}", flush=True)
        except Exception as e:  # jaringan, rate limit, overload
            galat_terakhir = str(e)
            print(f"  galat: {galat_terakhir}", flush=True)
        if percobaan < 3:
            time.sleep(20 * percobaan)

    raise Gagal(f"Tiga percobaan gagal. Terakhir: {galat_terakhir}")


# Tarif per juta token: (input, output, cache read, cache write 5 menit).
# Sumber: platform.claude.com/docs/en/about-claude/pricing
HARGA = {
    "claude-fable-5-1":  (10.0, 50.0, 0.25, 12.50),
    "claude-mythos-5-1": (10.0, 50.0, 0.25, 12.50),
    "claude-opus-5":     (5.0,  25.0, 0.50, 6.25),
    "claude-opus-4-8":   (5.0,  25.0, 0.50, 6.25),
    "claude-sonnet-5":   (2.0,  10.0, 0.20, 2.50),
    "claude-sonnet-4-6": (3.0,  15.0, 0.30, 3.75),
    "claude-haiku-4-5":  (1.0,   5.0, 0.10, 1.25),
}
BIAYA_PENCARIAN = 0.01  # US$10 per 1.000 pencarian


def lapor_biaya(model: str, usage, jumlah_cari: int) -> None:
    """
    Cetak pemakaian dan biaya nyata satu edisi.

    Estimasi sebelum menjalankan selalu meleset karena jumlah putaran
    pencarian tidak diketahui di muka. Angka di sini yang sahih.
    """
    masuk = getattr(usage, "input_tokens", 0) or 0
    keluar = getattr(usage, "output_tokens", 0) or 0
    baca_cache = getattr(usage, "cache_read_input_tokens", 0) or 0
    tulis_cache = getattr(usage, "cache_creation_input_tokens", 0) or 0

    ringkas = (
        f"Pemakaian: {jumlah_cari} pencarian, "
        f"{masuk:,} token masuk, {keluar:,} token keluar"
    )
    if baca_cache or tulis_cache:
        ringkas += f", {baca_cache:,} baca cache, {tulis_cache:,} tulis cache"
    print(ringkas.replace(",", "."), flush=True)

    tarif = HARGA.get(model.strip())
    if not tarif:
        print(f"  (tarif {model} tidak dikenal, biaya tidak dihitung)", flush=True)
        return

    h_masuk, h_keluar, h_baca, h_tulis = tarif
    biaya = (
        masuk / 1e6 * h_masuk
        + keluar / 1e6 * h_keluar
        + baca_cache / 1e6 * h_baca
        + tulis_cache / 1e6 * h_tulis
        + jumlah_cari * BIAYA_PENCARIAN
    )
    print(
        f"  Biaya edisi ini: US${biaya:.3f} "
        f"(≈ US${biaya * 22:.2f} untuk 22 hari kerja)",
        flush=True,
    )


# --------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "--validasi":
        berkas = pathlib.Path(sys.argv[2])
        doc = validasi_markdown(berkas.read_text(encoding="utf-8"), berkas.stem)
        print(
            f"Sah: {len(doc['indikator'])} indikator, {len(doc['brief'])} tema, "
            f"{len(doc['watch'])} butir pantau, {len(doc['sumber'])} sumber."
        )
        for c in periksa_gaya(berkas.read_text(encoding="utf-8")):
            print(f"Catatan gaya: {c}")
        return 0

    hari_ini = datetime.datetime.now(WIB).date()
    iso = hari_ini.isoformat()
    label = build.tanggal_id(iso)

    berkas_md = ROOT / "editions" / f"{iso}.md"
    berkas_json = ROOT / "data" / f"{iso}.json"
    paksa = os.environ.get("PAKSA", "").lower() in ("true", "1", "yes")

    if berkas_md.exists() and not paksa:
        print(f"Edisi {label} sudah ada. Lewati. (Set PAKSA=true untuk menimpa.)")
        return 0

    print(f"Menyusun edisi {label}...", flush=True)
    jawaban = susun(iso, label)

    md = ambil_blok(jawaban, MD_MULAI, MD_SELESAI, "markdown")
    data_mentah = ambil_blok(jawaban, JSON_MULAI, JSON_SELESAI, "JSON")

    doc = validasi_markdown(md, iso)
    data = validasi_json(data_mentah, iso)

    berkas_md.write_text(md.rstrip() + "\n", encoding="utf-8")
    berkas_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"Ditulis {berkas_md.relative_to(ROOT)} dan "
        f"{berkas_json.relative_to(ROOT)}: "
        f"{len(doc['indikator'])} indikator, {len(doc['brief'])} tema, "
        f"{len(doc['watch'])} butir pantau, {len(doc['sumber'])} sumber."
    )
    for c in periksa_gaya(md):
        print(f"Catatan gaya: {c}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Gagal as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        sys.exit(1)
