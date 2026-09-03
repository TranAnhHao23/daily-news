#!/usr/bin/env python3
"""Pick 5 LeetCode problems (2 Easy / 2 Medium / 1 Hard), publish them as a
GitHub Pages HTML page, and post a single short Discord message linking to it.

Uses LeetCode's public GraphQL endpoint (no login/API key needed). Picks are
seeded by today's date, so re-running the script the same day gives the same
5 problems, while each new day gives a different set.
"""
import html
import os
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from pages_publish import publish_page, render_page

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
LEETCODE_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://leetcode.com/problemset/",
}

QUESTION_LIST_QUERY = """
query problemsetQuestionListV2($filters: QuestionFilterInput, $limit: Int, $skip: Int, $categorySlug: String) {
  problemsetQuestionListV2(filters: $filters, limit: $limit, skip: $skip, categorySlug: $categorySlug) {
    questions {
      questionFrontendId
      titleSlug
      title
      difficulty
      paidOnly
      acRate
      topicTags { name }
    }
    totalLength
  }
}
"""

# (difficulty, how many to pick today)
DIFFICULTY_PLAN = [("EASY", 2), ("MEDIUM", 2), ("HARD", 1)]

DIFFICULTY_COLORS = {"EASY": "#2ECC71", "MEDIUM": "#F39C12", "HARD": "#E74C3C"}
DIFFICULTY_LABEL_VI = {"EASY": "Dễ", "MEDIUM": "Trung bình", "HARD": "Khó"}

# Fetch this many candidates per difficulty (before filtering out paid-only
# problems) so there's enough of a pool to sample from.
BATCH_SIZE = 40


def today_seed():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def fetch_batch(difficulty, skip, limit):
    payload = {
        "query": QUESTION_LIST_QUERY,
        "variables": {
            "categorySlug": "",
            "skip": skip,
            "limit": limit,
            "filters": {
                "filterCombineType": "ALL",
                "difficultyFilter": {"difficulties": [difficulty], "operator": "IS"},
            },
        },
    }
    resp = requests.post(LEETCODE_GRAPHQL_URL, headers=LEETCODE_HEADERS, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"LeetCode API error {resp.status_code}: {resp.text}")
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"LeetCode API returned errors: {data['errors']}")
    return data["data"]["problemsetQuestionListV2"]


def pick_problems_for_difficulty(difficulty, count, rng):
    probe = fetch_batch(difficulty, skip=0, limit=1)
    total = probe["totalLength"]

    max_skip = max(total - BATCH_SIZE, 0)
    skip = rng.randint(0, max_skip) if max_skip > 0 else 0

    batch = fetch_batch(difficulty, skip=skip, limit=BATCH_SIZE)["questions"]
    candidates = [q for q in batch if not q["paidOnly"]]

    if len(candidates) < count:
        # Fallback: pull from the very start of the list if the random
        # window happened to be paid-only heavy.
        batch = fetch_batch(difficulty, skip=0, limit=BATCH_SIZE * 2)["questions"]
        candidates = [q for q in batch if not q["paidOnly"]]

    return rng.sample(candidates, min(count, len(candidates)))


def pick_daily_problems():
    rng = random.Random(today_seed())
    problems = []
    for difficulty, count in DIFFICULTY_PLAN:
        problems.extend(pick_problems_for_difficulty(difficulty, count, rng))
    return problems


def favicon_url(domain):
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def render_problem_card(problem):
    difficulty = problem["difficulty"]
    color = DIFFICULTY_COLORS.get(difficulty, "#95A5A6")
    tags = ", ".join(t["name"] for t in problem["topicTags"][:4])
    ac_rate = problem["acRate"] * 100
    url = f"https://leetcode.com/problems/{problem['titleSlug']}/"
    title = f"{problem['questionFrontendId']}. {problem['title']}"
    label = DIFFICULTY_LABEL_VI.get(difficulty, difficulty)

    return f"""<div class="card" style="border-left:4px solid {color}">
<span class="badge" style="background:{color}">{html.escape(label)}</span>
<a class="title-link" href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(title)}</a>
<div class="meta">
  <img class="favicon" src="{html.escape(favicon_url('leetcode.com'))}" alt="">
  <span>🏷️ {html.escape(tags)} · 📈 AC {ac_rate:.1f}%</span>
</div>
</div>"""


def render_leetcode_page(problems, today):
    plan_text = " + ".join(f"{count} {DIFFICULTY_LABEL_VI[d]}" for d, count in DIFFICULTY_PLAN)
    header = f"""<div class="page-header">
<h1>🧩 5 bài LeetCode hôm nay — {today}</h1>
<p>{html.escape(plan_text)}</p>
</div>"""
    cards = "\n".join(render_problem_card(p) for p in problems)
    body = header + cards

    title = f"5 bài LeetCode — {today}"
    return render_page(title, plan_text, body)


def post_message(webhook_url, payload, thread_id=None):
    params = {"thread_id": thread_id} if thread_id else None
    resp = requests.post(webhook_url, params=params, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")
    time.sleep(0.5)


def main():
    webhook_url = os.environ["LEETCODE_DISCORD_WEBHOOK_URL"]
    thread_id = os.environ.get("LEETCODE_DISCORD_THREAD_ID") or None

    problems = pick_daily_problems()
    print(f"Picked {len(problems)} problems: {[p['title'] for p in problems]}")

    now = datetime.now(TZ)
    today = now.strftime("%d/%m/%Y")
    date_str = now.strftime("%Y-%m-%d")

    page_html = render_leetcode_page(problems, today)
    url = publish_page(
        f"leetcode/{date_str}.html",
        page_html,
        commit_message=f"LeetCode picks {date_str}",
    )
    time.sleep(15)  # give GitHub Pages a moment to deploy before Discord unfurls the link

    content = f"🧩 **5 bài LeetCode hôm nay — {today}**\n{url}"
    post_message(webhook_url, {"content": content}, thread_id=thread_id)
    print(f"Posted LeetCode link to Discord: {url}")


if __name__ == "__main__":
    main()
