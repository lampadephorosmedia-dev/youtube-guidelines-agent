import argparse
import json
import os
import re
import subprocess
import time

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s)
    return s[:80] if s else "section"

def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr}")
    return r.stdout

def build_md(data: dict) -> str:
    pages = data.get("pages", [])
    fetched_at = data.get("fetched_at_utc", "")
    start_url = data.get("start_url", "")

    # Deduplicate by URL, keep order
    seen = set()
    uniq = []
    for p in pages:
        u = p.get("url", "")
        if u and u not in seen:
            seen.add(u)
            uniq.append(p)

    lines = []
    lines.append("# YouTube Creator Policy Guidelines – Master Snapshot")
    lines.append("")
    lines.append(f"Build-Datum (UTC): **{fetched_at}**")
    lines.append(f"Start-URL: {start_url}")
    lines.append("")
    lines.append("## Inhaltsverzeichnis")
    lines.append("")

    toc = []
    for p in uniq:
        title = (p.get("title") or "Untitled").strip()
        anchor = slugify(title)
        toc.append(f"- [{title}](#{anchor})")

    lines.extend(toc)
    lines.append("")
    lines.append("---")
    lines.append("")

    for p in uniq:
        title = (p.get("title") or "Untitled").strip()
        url = p.get("url", "").strip()
        text = (p.get("text") or "").strip()

        anchor = slugify(title)
        lines.append(f"## {title}")
        lines.append(f"_Quelle_: {url}")
        lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)

def main(inp: str, outdir: str):
    os.makedirs(outdir, exist_ok=True)
    with open(inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    md = build_md(data)
    md_path = os.path.join(outdir, "master.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    # Export DOCX + PDF (pandoc must be installed; PDF needs LaTeX)
    docx_path = os.path.join(outdir, "master.docx")
    pdf_path = os.path.join(outdir, "master.pdf")

    run(["pandoc", md_path, "-o", docx_path])

    # For PDF:
    run(["pandoc", md_path, "-o", pdf_path, "--pdf-engine=xelatex"])

    print(f"Wrote: {md_path}\nWrote: {docx_path}\nWrote: {pdf_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input JSON from crawler")
    ap.add_argument("--outdir", default="dist", help="Output directory")
    args = ap.parse_args()
    main(args.inp, args.outdir)
