#!/usr/bin/env python3
"""Fetch news from RSS feeds, publish them as a GitHub Pages HTML page,
and post a single short Discord message linking to it.

No AI/summarization involved — headlines, links, and thumbnails come
straight from each RSS feed, so there is nothing to truncate or hallucinate.

Time window: yesterday 00:00 to today 09:00, Asia/Ho_Chi_Minh time.
"""
import html
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
from dateutil import parser as dateutil_parser

from pages_publish import publish_page, render_page

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Some sites (e.g. CafeBiz) block requests without a browser-like User-Agent.
feedparser.USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

FEEDS = {
    "Tin tức Việt Nam": [
        ("VnExpress", "https://vnexpress.net/rss/tin-moi-nhat.rss"),
        ("Tuổi Trẻ", "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
        ("Dân Trí", "https://dantri.com.vn/rss/home.rss"),
        ("CafeBiz", "https://cafebiz.vn/rss/home.rss"),
    ],
    "Tin thế giới": [
        ("VnExpress Thế giới", "https://vnexpress.net/rss/the-gioi.rss"),
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ],
    "Công nghệ & AI": [
        ("VnExpress Số hóa", "https://vnexpress.net/rss/so-hoa.rss"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
    ],
}

CATEGORY_COLORS = {
    "Tin tức Việt Nam": "#DA251D",
    "Tin thế giới": "#2E86DE",
    "Công nghệ & AI": "#8E44AD",
}
CATEGORY_EMOJI = {
    "Tin tức Việt Nam": "🇻🇳",
    "Tin thế giới": "🌍",
    "Công nghệ & AI": "💻",
}
DEFAULT_COLOR = "#95A5A6"

MAX_ARTICLES_PER_SOURCE = 10  # raw candidate pool per source, before card selection
MAX_CARDS_PER_CATEGORY = 15  # how many cards to show per category on the page


def get_window():
    now = datetime.now(TZ)
    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    window_end = today_9am if now >= today_9am else now
    window_start = (window_end - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return window_start, window_end


def parse_entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime.fromtimestamp(time.mktime(val), tz=ZoneInfo("UTC")).astimezone(TZ)

    # Some feeds (Tuổi Trẻ, CafeBiz) use non-standard date strings that
    # feedparser can't parse into published_parsed. Fall back to dateutil.
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = dateutil_parser.parse(raw)
        except (ValueError, OverflowError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)

    return None


def clean_description(raw_html, max_len=200):
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text


def extract_image(entry):
    for thumb in entry.get("media_thumbnail", []) or []:
        if thumb.get("url"):
            return thumb["url"]

    for media in entry.get("media_content", []) or []:
        if media.get("url") and media.get("medium", "image") == "image":
            return media["url"]

    for enc in entry.get("enclosures", []) or []:
        if enc.get("type", "").startswith("image") and enc.get("href"):
            return enc["href"]

    raw = entry.get("summary", "") or ""
    match = re.search(r'<img[^>]+src="([^"]+)"', raw)
    if match:
        return match.group(1)

    return None


def fetch_articles(window_start, window_end):
    articles = {cat: [] for cat in FEEDS}
    seen_links = set()

    for category, sources in FEEDS.items():
        for source_name, url in sources:
            try:
                feed = feedparser.parse(url)
            except Exception as exc:
                print(f"[warn] failed to fetch {source_name}: {exc}", file=sys.stderr)
                continue

            source_articles = []
            for entry in feed.entries:
                link = entry.get("link")
                if not link or link in seen_links:
                    continue

                published = parse_entry_time(entry)
                if published is None or not (window_start <= published <= window_end):
                    continue

                seen_links.add(link)
                source_articles.append(
                    {
                        "title": entry.get("title", "").strip(),
                        "link": link,
                        "description": clean_description(entry.get("summary", "")),
                        "image": extract_image(entry),
                        "source": source_name,
                        "published": published,
                    }
                )

            source_articles.sort(key=lambda a: a["published"], reverse=True)
            # Cap per source so one prolific outlet can't crowd out the others.
            articles[category].extend(source_articles[:MAX_ARTICLES_PER_SOURCE])

    return articles


def select_cards(items, limit):
    """Round-robin across sources so every outlet gets fair representation."""
    by_source = {}
    for article in items:
        by_source.setdefault(article["source"], []).append(article)
    for bucket in by_source.values():
        bucket.sort(key=lambda a: a["published"], reverse=True)

    sources = list(by_source.keys())
    selected = []
    idx = 0
    while len(selected) < limit and any(by_source.values()):
        source = sources[idx % len(sources)]
        bucket = by_source[source]
        if bucket:
            selected.append(bucket.pop(0))
        idx += 1
    return selected


def favicon_url(link):
    domain = urlparse(link).netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def render_article_card(article, color):
    thumb = f'<img class="thumb" src="{html.escape(article["image"])}" alt="">' if article["image"] else ""
    desc = f'<div class="desc">{html.escape(article["description"])}</div>' if article["description"] else ""
    time_str = article["published"].strftime("%H:%M %d/%m")
    return f"""<div class="card" style="border-left:4px solid {color}">
{thumb}
<a class="title-link" href="{html.escape(article['link'])}" target="_blank" rel="noopener">{html.escape(article['title'])}</a>
<div class="meta">
  <img class="favicon" src="{html.escape(favicon_url(article['link']))}" alt="">
  <span>{html.escape(article['source'])} • {time_str}</span>
</div>
{desc}
</div>"""


def render_news_page(articles_by_category, window_start, window_end):
    sections = []
    for category, items in articles_by_category.items():
        color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
        emoji = CATEGORY_EMOJI.get(category, "")
        sections.append(f'<div class="section-title">{emoji} {html.escape(category)}</div>')
        if not items:
            sections.append('<p style="color:#888">Không có tin nào trong khung giờ này.</p>')
        else:
            sections.extend(render_article_card(a, color) for a in items)

    header = f"""<div class="page-header">
<h1>🗞️ Bản tin sáng {window_end.strftime('%d/%m/%Y')}</h1>
<p>Tổng hợp tin từ {window_start.strftime('%H:%M %d/%m')} đến {window_end.strftime('%H:%M %d/%m')}</p>
</div>"""

    body = header + "\n".join(sections)
    title = f"Bản tin sáng {window_end.strftime('%d/%m/%Y')}"
    total = sum(len(v) for v in articles_by_category.values())
    description = f"{total} tin nổi bật: Việt Nam, Thế giới, Công nghệ & AI"
    return render_page(title, description, body)


def post_message(webhook_url, payload, thread_id=None):
    params = {"thread_id": thread_id} if thread_id else None
    resp = requests.post(webhook_url, params=params, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")
    time.sleep(0.5)  # stay well under Discord's webhook rate limit


def main():
    window_start, window_end = get_window()
    articles = fetch_articles(window_start, window_end)
    selected = {cat: select_cards(items, MAX_CARDS_PER_CATEGORY) for cat, items in articles.items()}

    total = sum(len(v) for v in selected.values())
    print(f"Fetched {total} articles between {window_start} and {window_end}")

    page_html = render_news_page(selected, window_start, window_end)
    date_str = window_end.strftime("%Y-%m-%d")
    url = publish_page(
        f"news/{date_str}.html",
        page_html,
        commit_message=f"News digest {date_str}",
    )
    time.sleep(15)  # give GitHub Pages a moment to deploy before Discord unfurls the link

    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    # Optional: post into a specific existing thread instead of the channel
    # itself. Get the thread ID from Discord (right-click thread > Copy
    # Thread ID, Developer Mode must be enabled) and set it as this env var.
    thread_id = os.environ.get("DISCORD_THREAD_ID") or None

    content = f"🗞️ **Bản tin sáng {window_end.strftime('%d/%m/%Y')}**\n{url}"
    post_message(webhook_url, {"content": content}, thread_id=thread_id)

    print(f"Posted digest link to Discord: {url}")


if __name__ == "__main__":
    main()
