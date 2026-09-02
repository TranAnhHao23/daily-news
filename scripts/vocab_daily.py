#!/usr/bin/env python3
"""Generate today's English vocabulary list (topic + level configurable
below) with Google Gemini, and post it to Discord as cards.

Topics rotate: one topic from VOCAB_TOPICS is picked per day (by day of
year), so re-running the script the same day gives the same topic.
"""
import json
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# --- Configuration: edit these to change what you learn ---------------
VOCAB_TOPICS = [
    "Giao tiếp hàng ngày",
    "IELTS/TOEIC học thuật",
]
VOCAB_LEVEL = "Intermediate (CEFR B1-B2)"
WORDS_PER_DAY = 8
# ------------------------------------------------------------------------

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

VOCAB_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "word": {"type": "STRING"},
            "pronunciation": {"type": "STRING"},
            "part_of_speech": {"type": "STRING"},
            "meaning_vi": {"type": "STRING"},
            "example_en": {"type": "STRING"},
            "example_vi": {"type": "STRING"},
        },
        "required": [
            "word",
            "pronunciation",
            "part_of_speech",
            "meaning_vi",
            "example_en",
            "example_vi",
        ],
    },
}


# Skip experimental/preview/non-text variants entirely — they're either
# unstable or return a different modality (image/tts) than we want.
EXCLUDE_KEYWORDS = ("preview", "exp", "image", "tts", "omni")


def _version_key(model_name):
    return tuple(int(n) for n in re.findall(r"\d+", model_name))


def rank_gemini_models(api_key):
    """Return usable flash models for this API key, best guess first.

    Model names/aliases get renamed and retired over time (and even a
    listed model can be flaky or deprecated for generateContent), so
    instead of hardcoding one, ask the API what's available and return a
    ranked list to try in order.
    """
    resp = requests.get(f"{GEMINI_API_BASE}/models", params={"key": api_key}, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Gemini ListModels error {resp.status_code}: {resp.text}")

    models = resp.json().get("models", [])
    names = [
        m["name"]
        for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
        and "flash" in m["name"].lower()
    ]
    clean = [n for n in names if not any(k in n.lower() for k in EXCLUDE_KEYWORDS)]
    if not clean:
        raise RuntimeError("No usable Gemini flash model found for this API key.")

    # Prefer concrete, numbered models (newest first) over "-latest"
    # aliases and lightweight "-lite" variants, which we keep as fallbacks.
    numbered = sorted(
        (n for n in clean if "lite" not in n.lower() and "latest" not in n.lower()),
        key=_version_key,
        reverse=True,
    )
    lite = sorted(
        (n for n in clean if "lite" in n.lower() and "latest" not in n.lower()),
        key=_version_key,
        reverse=True,
    )
    latest_aliases = sorted(n for n in clean if "latest" in n.lower())

    return numbered + lite + latest_aliases


def todays_topic():
    day_index = datetime.now(TZ).timetuple().tm_yday
    return VOCAB_TOPICS[day_index % len(VOCAB_TOPICS)]


def call_gemini(api_key, model_name, payload):
    """POST to one model, retrying transient (503/429) errors a few times."""
    max_attempts = 3
    for attempt in range(max_attempts):
        resp = requests.post(
            f"{GEMINI_API_BASE}/{model_name}:generateContent",
            params={"key": api_key},
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (503, 429) and attempt < max_attempts - 1:
            wait = 2 * (2**attempt)
            print(f"[warn] {model_name} returned {resp.status_code}, retrying in {wait}s...")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")


def generate_vocab_list(api_key, topic):
    prompt = (
        "Bạn là gia sư tiếng Anh cho người Việt. Hãy tạo danh sách "
        f"{WORDS_PER_DAY} từ vựng tiếng Anh chủ đề '{topic}', mức độ "
        f"{VOCAB_LEVEL}. Ưu tiên từ hữu ích, thực tế, đa dạng, tránh những "
        "từ quá cơ bản ai cũng đã biết. Với mỗi từ, cung cấp: từ tiếng Anh, "
        "phiên âm IPA, từ loại (viết tắt tiếng Anh: n., v., adj., adv., "
        "phrase...), nghĩa tiếng Việt ngắn gọn, một câu ví dụ tiếng Anh tự "
        "nhiên, và bản dịch câu ví dụ đó sang tiếng Việt."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            # Newer flash models spend a variable, often large, chunk of
            # this budget on hidden "thinking" tokens before writing the
            # visible answer, so keep this generous.
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseSchema": VOCAB_SCHEMA,
        },
    }

    candidates = rank_gemini_models(api_key)
    last_error = None
    for model_name in candidates:
        print(f"Trying Gemini model: {model_name}")
        try:
            data = call_gemini(api_key, model_name, payload)
        except RuntimeError as exc:
            last_error = exc
            print(f"[warn] {model_name} failed: {exc}")
            continue

        result_candidates = data.get("candidates") or []
        if not result_candidates:
            last_error = RuntimeError(f"Gemini returned no candidates: {data}")
            continue

        finish_reason = result_candidates[0].get("finishReason")
        if finish_reason == "MAX_TOKENS":
            print("[warn] Gemini response was truncated (finishReason=MAX_TOKENS).")

        parts = result_candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            last_error = RuntimeError(f"{model_name} returned empty text (finishReason={finish_reason})")
            continue

        print(f"Used Gemini model: {model_name}")
        return json.loads(text)

    raise RuntimeError(f"All Gemini flash models failed. Last error: {last_error}")


def build_word_embed(item, color):
    description = (
        f"**{item['part_of_speech']}** {item['pronunciation']} — {item['meaning_vi']}\n\n"
        f"*{item['example_en']}*\n{item['example_vi']}"
    )
    return {
        "title": item["word"],
        "color": color,
        "description": description,
    }


def post_message(webhook_url, payload, thread_id=None):
    params = {"thread_id": thread_id} if thread_id else None
    resp = requests.post(webhook_url, params=params, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")
    time.sleep(0.5)


def main():
    api_key = os.environ["GEMINI_API_KEY"]
    webhook_url = os.environ["VOCAB_DISCORD_WEBHOOK_URL"]
    thread_id = os.environ.get("VOCAB_DISCORD_THREAD_ID") or None

    topic = todays_topic()
    words = generate_vocab_list(api_key, topic)
    print(f"Generated {len(words)} words for topic '{topic}'")

    today = datetime.now(TZ).strftime("%d/%m/%Y")
    color = 0x16A085
    banner = {
        "title": f"📚 Từ vựng hôm nay — {today}",
        "description": f"Chủ đề: **{topic}** · Mức độ: {VOCAB_LEVEL}",
        "color": color,
    }

    embeds = [banner] + [build_word_embed(w, color) for w in words]
    # Discord allows at most 10 embeds per message.
    for i in range(0, len(embeds), 10):
        post_message(webhook_url, {"embeds": embeds[i : i + 10]}, thread_id=thread_id)

    print("Posted vocab list to Discord.")


if __name__ == "__main__":
    main()
