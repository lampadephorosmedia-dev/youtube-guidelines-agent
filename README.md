# YouTube Guidelines Agent (Master PDF/DOCX)

Dieser Repo-Agent crawlt öffentliche YouTube/Google-Support-Policy-Seiten (Start-URL) und baut daraus:
- `dist/master.md`
- `dist/master.docx`
- `dist/master.pdf`

Er respektiert robots.txt und nutzt Rate-Limits.

## Start-URL
Standard: YouTube Community Guidelines
https://support.google.com/youtube/answer/9288567?hl=en

Du kannst die Start-URL als Workflow-Input oder per ENV setzen.

## Lokal laufen lassen
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/crawl.py --start "https://support.google.com/youtube/answer/9288567?hl=en" --out data/pages.json
python src/build.py --in data/pages.json --outdir dist
