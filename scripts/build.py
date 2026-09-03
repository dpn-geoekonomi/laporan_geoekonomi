#!/usr/bin/env python3
"""
Bangun situs Sinyal dari edisi markdown.

Masukan : editions/<YYYY-MM-DD>.md   (frontmatter + bagian ## markdown, lihat README)
Keluaran: editions/<YYYY-MM-DD>.html (halaman jadi, mandiri)
          index.html                 (salinan edisi terbaru)
          arsip.html                 (daftar seluruh edisi)
          data/index.json            (manifest edisi untuk arsip)

Pustaka standar saja — tidak ada dependensi pip.
Pakai: python3 scripts/build.py
"""

import html
import json
import pathlib
import re
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "editions"
DATA = ROOT / "data"

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
         "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
LINK_RE = re.compile(r"\[(.+?)\]\((https?://[^\s)]+)\)")
DIRECTION_RE = re.compile(r"\((up|down|flat)\)\s*$")
WATCH_RE = re.compile(r"^\*\*\[(.+?)\]\*\*\s*(.+?)\s*—\s*(.+)$")


def tanggal_id(iso: str) -> str:
    d = datetime.date.fromisoformat(iso)
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"


def inline(text: str) -> str:
    """Format ringan dalam teks: **tebal** dan [tautan](url). Input sudah di-escape."""
    text = html.escape(text.strip(), quote=False)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = LINK_RE.sub(r'<a href="\2">\1</a>', text)
    return text


def parse_frontmatter(text: str):
    m = FRONT_RE.match(text)
    meta = {}
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"')
    return meta, text[m.end():]


def split_sections(body: str):
    """['Judul', 'isi', 'Judul2', 'isi2', ...] -> [(judul, isi), ...]"""
    parts = HEADING_RE.split(body)
    out = []
    it = iter(parts[1:])
    for judul in it:
        isi = next(it, "").strip("\n")
        out.append((judul.strip(), isi))
    return out


def norm(s: str) -> str:
    return s.strip().lower()


def parse_indikator(content: str):
    tiles = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        item = line[2:].strip()
        arah = "flat"
        m = DIRECTION_RE.search(item)
        if m:
            arah = m.group(1)
            item = item[:m.start()].strip()
        if ":" not in item:
            continue
        label, sisa = item.split(":", 1)
        if "—" in sisa:
            nilai, ket = sisa.split("—", 1)
        else:
            nilai, ket = sisa, ""
        tiles.append({"label": label.strip(), "nilai": nilai.strip(),
                      "ket": ket.strip(), "arah": arah})
    return tiles


def parse_brief(content: str):
    """Bagian tema: baris _Sumber: ..._ opsional, lalu paragraf dan/atau daftar fakta."""
    lines = content.split("\n")
    src = None
    if lines and lines[0].strip().startswith("_") and lines[0].strip().endswith("_"):
        src = lines[0].strip().strip("_")
        lines = lines[1:]
    rest = "\n".join(lines).strip("\n")
    blocks = re.split(r"\n\s*\n", rest)

    paragraphs, facts = [], []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        blines = [l.strip() for l in block.splitlines() if l.strip()]
        if all(l.startswith("- ") and ":" in l for l in blines):
            for l in blines:
                k, v = l[2:].split(":", 1)
                facts.append((k.strip(), v.strip()))
        else:
            paragraphs.append(" ".join(blines))
    return src, paragraphs, facts


def parse_watchlist(content: str):
    items = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        m = WATCH_RE.match(line[2:].strip())
        if not m:
            continue
        tag, judul, desk = m.groups()
        items.append({"tag": tag, "judul": judul, "desk": desk,
                      "hot": norm(tag) == "berlangsung"})
    return items


def parse_sumber(content: str):
    items = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        m = LINK_RE.match(line[2:].strip())
        if m:
            items.append({"judul": m.group(1), "url": m.group(2)})
    return items


def parse_edition(iso: str, text: str):
    meta, body = parse_frontmatter(text)
    sections = split_sections(body)

    doc = {"iso": iso, "meta": meta, "sinyal": "", "indikator": [],
           "brief": [], "watch": [], "sumber": []}

    for judul, isi in sections:
        key = norm(judul)
        if key == "sinyal utama":
            doc["sinyal"] = inline(" ".join(l.strip() for l in isi.splitlines() if l.strip()))
        elif key == "indikator":
            doc["indikator"] = parse_indikator(isi)
        elif key == "yang perlu dipantau":
            doc["watch"] = parse_watchlist(isi)
        elif key == "sumber":
            doc["sumber"] = parse_sumber(isi)
        else:
            src, paragraphs, facts = parse_brief(isi)
            doc["brief"].append({"judul": judul, "src": src, "paragraphs": paragraphs,
                                  "facts": facts})
    return doc


def render_tiles(indikator):
    dirs = {"up": "up", "down": "down", "flat": "flat"}
    out = []
    for t in indikator:
        cls = dirs.get(t["arah"], "flat")
        out.append(f"""    <div class="tile">
      <span class="k">{html.escape(t['label'])}</span>
      <span class="v">{html.escape(t['nilai'])}</span>
      <span class="d {cls}">{html.escape(t['ket'])}</span>
    </div>""")
    return "\n".join(out)


def render_brief(sections):
    out = []
    for s in sections:
        src_html = f'<span class="src">{html.escape(s["src"])}</span>' if s["src"] else ""
        paras = "\n      ".join(f'<p class="read">{inline(p)}</p>' for p in s["paragraphs"])
        facts_html = ""
        if s["facts"]:
            rows = "\n        ".join(
                f"<dt>{inline(k)}</dt><dd>{inline(v)}</dd>" for k, v in s["facts"])
            facts_html = f'<dl class="facts">\n        {rows}\n      </dl>'
        out.append(f"""    <section class="brief">
      <div class="head">
        <h2>{html.escape(s['judul'])}</h2>
        {src_html}
      </div>
      {paras}
      {facts_html}
    </section>""")
    return "\n".join(out)


def render_watch(items):
    out = []
    for w in items:
        cls = "when hot" if w["hot"] else "when"
        out.append(f"""      <article>
        <span class="{cls}">{html.escape(w['tag'])}</span>
        <h3>{inline(w['judul'])}</h3>
        <p>{inline(w['desk'])}</p>
      </article>""")
    return "\n".join(out)


def render_sumber(items):
    return "\n".join(
        f'      <li><a href="{html.escape(u["url"])}">{inline(u["judul"])}</a></li>'
        for u in items)


PAGE_TEMPLATE = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{deskripsi}">
<meta property="og:title" content="Sinyal Ekonomi Indonesia — {tanggal_label}">
<meta property="og:description" content="{deskripsi}">
<meta property="og:type" content="article">
<title>Sinyal Ekonomi Indonesia</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
{css}
</style>
</head>
<body>
<div class="wrap">

  <nav class="site-nav">
    <a href="{nav_prefix}index.html">Edisi terbaru</a>
    <a href="{nav_prefix}arsip.html">Arsip</a>
  </nav>

  <header class="masthead">
    <div class="brand">
      <h1>Sinyal</h1>
      <span class="sub">Intelijen Ekonomi Indonesia</span>
    </div>
    <div class="edition">
      <b>{tanggal_label}</b><br>
      Edisi pagi · {jam_edisi}<br>
      Data terakhir: {data_terakhir}<br>
      {stamp}
    </div>
  </header>

  <div class="lede">
    <span class="eyebrow">Sinyal utama</span>
    <p>{sinyal}</p>
  </div>

  <div class="strip">
{tiles}
  </div>

  <div class="grid">
{brief}
  </div>

  <section class="watch">
    <h2>Yang perlu dipantau</h2>
    <span class="src">Urut berdasarkan kedekatan waktu, bukan bobot dampak</span>
    <div class="watchlist">
{watch}
    </div>
  </section>

  <section class="sources">
    <h2>Sumber</h2>
    <ol>
{sumber}
    </ol>
    <p class="disclaimer">Ringkasan disusun dari laporan publik yang tersedia pada {tanggal_label} dan dapat berubah seiring rilis data baru. Angka pasar bersifat indikatif dan bukan kutipan resmi bursa. Bukan nasihat investasi.</p>
  </section>

</div>
</body>
</html>
"""

CSS = """
:root{
  --bg:#EEF3F2; --surface:#FFFFFF; --surface-2:#E4ECEB; --ink:#0F1F1E; --ink-2:#3A4E4C;
  --muted:#657876; --line:#CEDCDA; --line-strong:#A9BFBC; --primary:#0D5B57;
  --primary-soft:#D6E7E5; --accent:#9A6A12; --up:#1B6E46; --down:#A33526; --flat:#657876;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0A1514; --surface:#11201E; --surface-2:#172A28; --ink:#E7EFED; --ink-2:#BCCECB;
    --muted:#8CA19E; --line:#223735; --line-strong:#33504D; --primary:#54C0B3;
    --primary-soft:#12312E; --accent:#D9A441; --up:#4CB784; --down:#E0705E; --flat:#8CA19E;
  }
}
:root[data-theme="dark"]{
  --bg:#0A1514; --surface:#11201E; --surface-2:#172A28; --ink:#E7EFED; --ink-2:#BCCECB;
  --muted:#8CA19E; --line:#223735; --line-strong:#33504D; --primary:#54C0B3;
  --primary-soft:#12312E; --accent:#D9A441; --up:#4CB784; --down:#E0705E; --flat:#8CA19E;
}
*{box-sizing:border-box}
html{color-scheme:light dark}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"IBM Plex Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
img{max-width:100%}
.wrap{max-width:1060px;margin:0 auto;padding:0 22px 72px}

.site-nav{padding:14px 0 0;display:flex;gap:18px;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:.68rem;letter-spacing:.14em;text-transform:uppercase}
.site-nav a{color:var(--muted);text-decoration:none;border-bottom:1px solid transparent}
.site-nav a:hover{color:var(--primary);border-bottom-color:var(--primary)}

.masthead{border-bottom:2px solid var(--ink);padding:20px 0 14px;display:flex;flex-wrap:wrap;
  align-items:flex-end;justify-content:space-between;gap:14px 28px}
.brand{display:flex;flex-direction:column;gap:2px}
.brand h1{font-family:"Fraunces", Georgia, "Times New Roman", serif;font-optical-sizing:auto;
  font-weight:700;font-size:clamp(2.5rem,7vw,4rem);line-height:.94;letter-spacing:-.02em;
  margin:0;text-wrap:balance}
.brand .sub{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.7rem;
  letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.edition{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.72rem;line-height:1.7;
  text-align:right;color:var(--ink-2)}
.edition b{color:var(--ink);font-weight:600}
.edition .stamp{display:inline-block;margin-top:6px;padding:2px 8px;border:1px solid var(--line-strong);
  border-radius:2px;color:var(--muted);letter-spacing:.1em;text-transform:uppercase;font-size:.62rem}

.lede{padding:26px 0 30px;border-bottom:1px solid var(--line);display:grid;
  grid-template-columns:minmax(0,1fr);gap:14px}
.lede .eyebrow{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.68rem;
  letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
.lede p{margin:0;font-family:"Fraunces", Georgia, serif;font-optical-sizing:auto;font-weight:400;
  font-size:clamp(1.12rem,2.3vw,1.4rem);line-height:1.5;max-width:62ch;text-wrap:pretty}
.lede p strong{font-weight:600;color:var(--primary)}

.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);margin:28px 0 40px}
.tile{background:var(--surface);padding:14px 16px 16px;display:flex;flex-direction:column;gap:3px}
.tile .k{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.63rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--muted)}
.tile .v{font-family:"IBM Plex Mono", ui-monospace, monospace;font-variant-numeric:tabular-nums;
  font-weight:600;font-size:1.32rem;letter-spacing:-.02em;line-height:1.2}
.tile .d{font-size:.74rem;color:var(--muted);font-variant-numeric:tabular-nums}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--flat)}

.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:34px 40px;
  align-items:start}
section.brief{display:flex;flex-direction:column;gap:14px}
.head{display:flex;flex-direction:column;gap:4px;border-top:2px solid var(--primary);padding-top:10px}
.head h2{font-family:"Fraunces", Georgia, serif;font-optical-sizing:auto;font-weight:600;
  font-size:1.3rem;letter-spacing:-.01em;margin:0}
.head .src{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.64rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted)}
.read{margin:0;font-size:.95rem;color:var(--ink-2);max-width:60ch}
.read strong{color:var(--ink);font-weight:600}

dl.facts{margin:0;display:grid;grid-template-columns:1fr auto;gap:0;border-top:1px solid var(--line)}
dl.facts dt,dl.facts dd{margin:0;padding:7px 0;border-bottom:1px solid var(--line);font-size:.85rem}
dl.facts dt{color:var(--muted);padding-right:16px}
dl.facts dd{font-family:"IBM Plex Mono", ui-monospace, monospace;font-variant-numeric:tabular-nums;
  font-weight:500;text-align:right;color:var(--ink);white-space:nowrap}

.watch{margin-top:46px;border-top:2px solid var(--ink);padding-top:22px}
.watch h2{font-family:"Fraunces", Georgia, serif;font-weight:600;font-size:1.45rem;margin:0 0 4px;
  letter-spacing:-.01em}
.watch .src{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.64rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);display:block;margin-bottom:18px}
.watchlist{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line)}
.watchlist article{background:var(--surface);padding:14px 16px;display:flex;flex-direction:column;gap:6px}
.watchlist h3{margin:0;font-size:.94rem;font-weight:600;line-height:1.35}
.watchlist p{margin:0;font-size:.83rem;color:var(--ink-2)}
.when{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.61rem;letter-spacing:.12em;
  text-transform:uppercase;color:var(--primary)}
.when.hot{color:var(--down)}

.sources{margin-top:44px;border-top:1px solid var(--line);padding-top:18px}
.sources h2{font-family:"IBM Plex Mono", ui-monospace, monospace;font-size:.68rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 0 10px}
.sources ol{margin:0;padding-left:1.2em;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
  gap:4px 24px;font-size:.8rem}
.sources li{color:var(--muted)}
.sources a{color:var(--primary);text-decoration:none;border-bottom:1px solid var(--primary-soft)}
.sources a:hover{border-bottom-color:var(--primary)}
a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.disclaimer{margin-top:22px;font-size:.75rem;color:var(--muted);max-width:70ch;
  font-family:"IBM Plex Mono", ui-monospace, monospace;line-height:1.65}

@media (max-width:520px){ .edition{text-align:left} }
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
"""


def render_page(doc: dict, nav_prefix: str) -> str:
    meta = doc["meta"]
    tanggal_label = tanggal_id(doc["iso"])
    stamp = f'<span class="stamp">{html.escape(meta["label_khusus"])}</span>' if meta.get("label_khusus") else ""
    deskripsi = (f"Briefing intelijen ekonomi Indonesia {tanggal_label} — makro & moneter, "
                 "pasar & kurs, komoditas & energi, perdagangan & geopolitik.")
    return PAGE_TEMPLATE.format(
        css=CSS.strip(),
        deskripsi=deskripsi,
        tanggal_label=tanggal_label,
        nav_prefix=nav_prefix,
        jam_edisi=html.escape(meta.get("jam_edisi", "")),
        data_terakhir=html.escape(meta.get("data_terakhir", "")),
        stamp=stamp,
        sinyal=doc["sinyal"],
        tiles=render_tiles(doc["indikator"]),
        brief=render_brief(doc["brief"]),
        watch=render_watch(doc["watch"]),
        sumber=render_sumber(doc["sumber"]),
    )


def bangun_arsip(docs: list) -> str:
    baris = []
    for doc in docs:
        chips = "".join(
            f'<span class="chip"><i>{html.escape(t["label"])}</i>{html.escape(t["nilai"])}</span>'
            for t in doc["indikator"][:4]
        )
        baris.append(f"""    <li>
      <a class="ed" href="editions/{doc['iso']}.html">
        <span class="tgl">{tanggal_id(doc['iso'])}</span>
        <span class="sig">{doc['sinyal']}</span>
        <span class="chips">{chips}</span>
      </a>
    </li>""")

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Arsip — Sinyal Ekonomi Indonesia</title>
<meta name="description" content="Seluruh edisi briefing intelijen ekonomi Indonesia.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
{CSS.strip()}
.ed{{display:grid;gap:6px;padding:20px 0;border-bottom:1px solid var(--line);text-decoration:none;color:inherit}}
.ed:hover .tgl{{color:var(--primary)}}
.ed:focus-visible{{outline:2px solid var(--accent);outline-offset:3px}}
.tgl{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink-2)}}
.sig{{font-family:"Fraunces",Georgia,serif;font-size:1.06rem;line-height:1.5;max-width:64ch;text-wrap:pretty}}
.sig strong{{color:var(--primary)}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}}
.chip{{display:inline-flex;gap:6px;align-items:baseline;background:var(--surface);border:1px solid var(--line);
  padding:3px 9px;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.73rem;font-variant-numeric:tabular-nums}}
.chip i{{font-style:normal;color:var(--muted);text-transform:uppercase;font-size:.62rem;letter-spacing:.1em}}
header.arsip{{border-bottom:2px solid var(--ink);padding:30px 0 14px;margin-bottom:6px}}
header.arsip h1{{font-family:"Fraunces",Georgia,serif;font-weight:700;font-size:clamp(2rem,5vw,2.9rem);
  margin:0;letter-spacing:-.02em;line-height:1}}
header.arsip p{{margin:8px 0 0;color:var(--muted);font-size:.9rem}}
ul{{list-style:none;margin:0;padding:0}}
</style>
</head>
<body>
<div class="wrap">
  <nav class="site-nav">
    <a href="index.html">Edisi terbaru</a>
    <a href="arsip.html">Arsip</a>
  </nav>
  <header class="arsip">
    <h1>Arsip</h1>
    <p>{len(docs)} edisi · Sinyal — Intelijen Ekonomi Indonesia</p>
  </header>
  <ul>
{chr(10).join(baris)}
  </ul>
  <p class="disclaimer">Angka pasar bersifat indikatif dan bukan kutipan resmi bursa. Bukan nasihat investasi.</p>
</div>
</body>
</html>
"""


def main() -> None:
    sumber_files = sorted(EDITIONS.glob("*.md"), reverse=True)
    if not sumber_files:
        raise SystemExit("Tidak ada file editions/*.md")

    docs = []
    for f in sumber_files:
        iso = f.stem
        doc = parse_edition(iso, f.read_text(encoding="utf-8"))
        docs.append(doc)
        (EDITIONS / f"{iso}.html").write_text(render_page(doc, "../"), encoding="utf-8")

    terbaru = docs[0]
    (ROOT / "index.html").write_text(render_page(terbaru, ""), encoding="utf-8")
    (ROOT / "arsip.html").write_text(bangun_arsip(docs), encoding="utf-8")

    manifest = [{"tanggal": d["iso"], "label": tanggal_id(d["iso"]),
                 "halaman": f"editions/{d['iso']}.html",
                 "sinyal": re.sub("<[^>]+>", "", d["sinyal"]),
                 "indikator": {t["label"]: t["nilai"] for t in d["indikator"]}}
                for d in docs]
    (DATA / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Dibangun {len(docs)} edisi. Terbaru: {tanggal_id(terbaru['iso'])}")


if __name__ == "__main__":
    main()
