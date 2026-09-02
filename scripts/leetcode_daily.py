#!/usr/bin/env python3
"""Pick 5 LeetCode problems (2 Easy / 2 Medium / 1 Hard) and post them to
Discord as cards, once a day.

Uses LeetCode's public GraphQL endpoint (no login/API key needed). Picks are
seeded by today's date, so re-running the script the same day gives the same
5 problems, while each new day gives a different set.
"""
import os
import random
import time
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

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

DIFFICULTY_COLORS = {"EASY": 0x2ECC71, "MEDIUM": 0xF39C12, "HARD": 0xE74C3C}
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


def build_problem_embed(problem):
    difficulty = problem["difficulty"]
    tags = ", ".join(t["name"] for t in problem["topicTags"][:4])
    ac_rate = problem["acRate"]

    lines = []
    if tags:
        lines.append(f"🏷️ {tags}")
    lines.append(f"📈 Tỉ lệ AC: {ac_rate * 100:.1f}%")

    return {
        "title": f"{problem['questionFrontendId']}. {problem['title']}",
        "url": f"https://leetcode.com/problems/{problem['titleSlug']}/",
        "color": DIFFICULTY_COLORS.get(difficulty, 0x95A5A6),
        "author": {
            "name": f"LeetCode • {DIFFICULTY_LABEL_VI.get(difficulty, difficulty)}",
            "icon_url": favicon_url("leetcode.com"),
        },
        "description": "\n".join(lines),
    }


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

    today = datetime.now(TZ).strftime("%d/%m/%Y")
    plan_text = " + ".join(f"{count} {DIFFICULTY_LABEL_VI[d]}" for d, count in DIFFICULTY_PLAN)
    banner = {
        "title": f"🧩 5 bài LeetCode hôm nay — {today}",
        "description": plan_text,
        "color": 0x2C3E50,
    }

    embeds = [banner] + [build_problem_embed(p) for p in problems]
    post_message(webhook_url, {"embeds": embeds}, thread_id=thread_id)
    print("Posted LeetCode picks to Discord.")


if __name__ == "__main__":
    main()
