import argparse
import json
import time
import re
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

DEFAULT_ALLOWED_HOSTS = {
    "support.google.com",
    "www.youtube.com",
    "youtube.com",
}

USER_AGENT = "Mozilla/5.0 (compatible; GuidelinesAgent/1.0; +https://github.com/)"


def normalize_url(u: str) -> str:
    u, _frag = urldefrag(u)
    return u.strip()


def same_host(url: str, allowed_hosts: set[str]) -> bool:
    host = urlparse(url).netloc.lower()
    return host in allowed_hosts


def is_probably_policy_page(url: str) -> bool:
    # Keep it conservative: only support.google.com/youtube... plus how-things-work policies page if desired.
    p = urlparse(url)
    host = p.netloc.lower()
    path = p.path.lower()

    if host == "support.google.com":
        # keep youtube help center content
        return path.startswith("/youtube/")
    if host in {"www.youtube.com", "youtube.com"}:
        # optional: creators policy hub pages
        return "/creators/" in path or "/howyoutubeworks/" in path
    return False


def get_robots_parser(session: requests.Session, base_url: str) -> RobotFileParser:
    p = urlparse(base_url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        r = session.get(robots_url, timeout=20, headers={"User-Agent": USER_AGENT})
        rp.parse(r.text.splitlines())
    except Exception:
        # If robots can't be fetched, behave safely: disallow everything except the start URL host fetch attempt.
        rp = RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /"])
    return rp


def extract_main_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")

    # Title
    title = soup.title.get_text(strip=True) if soup.title else ""

    # Try common content containers for Google Support pages
    candidates = []
    for sel in [
        "article",
        "main",
        '[role="main"]',
        ".article-content",
        ".cc",  # sometimes used
    ]:
        candidates.extend(soup.select(sel))

    # Pick the biggest by text length
    if candidates:
        best = max(candidates, key=lambda el: len(el.get_text(" ", strip=True)))
        text = best.get_text("\n", strip=True)
    else:
        text = soup.get_text("\n", strip=True)

    # Clean excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title, text


def extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("javascript:") or href.startswith("#"):
            continue
        absu = urljoin(base_url, href)
        absu = normalize_url(absu)
        links.append(absu)
    return links


def crawl(start_url: str, out_path: str, max_pages: int, delay_s: float, allowed_hosts: set[str]):
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    rp = get_robots_parser(session, start_url)

    seen = set()
    queue = [normalize_url(start_url)]
    pages = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        if not same_host(url, allowed_hosts):
            continue
        if not is_probably_policy_page(url):
            continue

        # robots check
        if not rp.can_fetch(USER_AGENT, url):
            continue

        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
                continue
            html = resp.text
        except Exception:
            continue

        title, text = extract_main_text(html)
        pages.append({
            "url": url,
            "title": title,
            "text": text,
        })

        # enqueue links
        for link in extract_links(url, html):
            if link not in seen:
                queue.append(link)

        time.sleep(delay_s)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "start_url": start_url,
            "fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pages": pages,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="Start URL (e.g. Community Guidelines page)")
    ap.add_argument("--out", default="data/pages.json", help="Output JSON path")
    ap.add_argument("--max-pages", type=int, default=60, help="Max pages to fetch")
    ap.add_argument("--delay", type=float, default=1.2, help="Delay seconds between requests")
    ap.add_argument("--hosts", default="support.google.com,www.youtube.com,youtube.com", help="Comma-separated allowed hosts")
    args = ap.parse_args()

    hosts = {h.strip().lower() for h in args.hosts.split(",") if h.strip()}
    crawl(args.start, args.out, args.max_pages, args.delay, hosts)
