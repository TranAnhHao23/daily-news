#!/usr/bin/env python3
"""Fetch news from RSS feeds, summarize with Claude, and post to Discord.

Time window: yesterday 00:00 to today 09:00, Asia/Ho_Chi_Minh time.
"""
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import feedparser
import requests
from dateutil import parser as dateutil_parser

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

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

MAX_ARTICLES_PER_SOURCE = 10
MAX_ARTICLES_PER_CATEGORY = 30
DISCORD_CHUNK_LIMIT = 1900


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
                        "summary": entry.get("summary", "").strip(),
                        "source": source_name,
                        "published": published,
                    }
                )

            source_articles.sort(key=lambda a: a["published"], reverse=True)
            # Cap per source so one prolific outlet can't crowd out the others.
            articles[category].extend(source_articles[:MAX_ARTICLES_PER_SOURCE])

    for category in articles:
        articles[category].sort(key=lambda a: a["published"], reverse=True)
        articles[category] = articles[category][:MAX_ARTICLES_PER_CATEGORY]

    return articles


def build_prompt(articles, window_start, window_end):
    lines = [
        "Bạn là biên tập viên tin tức. Dưới đây là danh sách bài báo thô theo từng chủ đề, "
        "trong khoảng thời gian từ "
        f"{window_start.strftime('%H:%M %d/%m/%Y')} đến {window_end.strftime('%H:%M %d/%m/%Y')}.",
        "",
        "Hãy viết một bản tin vắn tắt bằng tiếng Việt, định dạng Markdown phù hợp để gửi qua Discord, với yêu cầu:",
        "- Mỗi chủ đề là một mục có tiêu đề in đậm kèm emoji phù hợp.",
        "- Trong mỗi chủ đề, chọn lọc các tin quan trọng/đáng chú ý nhất (khoảng 4-6 tin), "
        "mỗi tin là 1 bullet gồm: tóm tắt 1 câu súc tích bằng tiếng Việt + link nguồn dạng markdown.",
        "- Bỏ qua tin trùng lặp nội dung, tin rác, quảng cáo.",
        "- Nếu một chủ đề không có tin nào, ghi 'Không có tin đáng chú ý.'",
        "- Không bịa thêm thông tin ngoài nội dung được cung cấp.",
        "- Không thêm lời mở đầu/kết luận thừa, chỉ xuất thẳng nội dung bản tin.",
        "",
    ]

    for category, items in articles.items():
        lines.append(f"## {category}")
        if not items:
            lines.append("(không có bài viết nào trong khoảng thời gian này)")
        for item in items:
            lines.append(f"- [{item['source']}] {item['title']} | {item['link']}")
            if item["summary"]:
                lines.append(f"  Mô tả gốc: {item['summary'][:300]}")
        lines.append("")

    return "\n".join(lines)


def summarize_with_gemini(prompt):
    api_key = os.environ["GEMINI_API_KEY"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2000},
    }
    resp = requests.post(
        GEMINI_URL,
        params={"key": api_key},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def chunk_message(text, limit=DISCORD_CHUNK_LIMIT):
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:]
    if text:
        chunks.append(text)
    return chunks


def post_to_discord(header, digest_text):
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    full_text = f"{header}\n\n{digest_text}"
    for chunk in chunk_message(full_text):
        resp = requests.post(webhook_url, json={"content": chunk})
        if resp.status_code >= 300:
            raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")


def main():
    window_start, window_end = get_window()
    articles = fetch_articles(window_start, window_end)

    total = sum(len(v) for v in articles.values())
    print(f"Fetched {total} articles between {window_start} and {window_end}")

    prompt = build_prompt(articles, window_start, window_end)
    digest_text = summarize_with_gemini(prompt)

    header = f"🗞️ **Bản tin sáng {window_end.strftime('%d/%m/%Y')}**"
    post_to_discord(header, digest_text)
    print("Posted digest to Discord.")


if __name__ == "__main__":
    main()
