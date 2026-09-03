"""Shared helper: render a static HTML page, publish it to GitHub Pages
(via the repo's docs/ folder), and hand back its public URL.

Used by all 3 daily scripts so Discord messages can be a single short
line + link instead of a wall of cards. Discord auto-unfurls the link
into a rich preview using the page's Open Graph tags.
"""
import html
import os
import subprocess
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")


def pages_base_url():
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo"
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY env var not set (expected 'owner/repo').")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}"


def render_page(title, description, body_html, og_image=None):
    og_image_tag = f'<meta property="og:image" content="{html.escape(og_image)}">' if og_image else ""
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="website">
{og_image_tag}
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f5f7; color: #1a1a1a;
  }}
  .wrap {{ max-width: 720px; margin: 0 auto; padding: 28px 16px 56px; }}
  .page-header {{ margin-bottom: 24px; }}
  .page-header h1 {{ font-size: 22px; margin: 0 0 6px; }}
  .page-header p {{ margin: 0; color: #666; font-size: 14px; }}
  .section-title {{ font-size: 17px; font-weight: 700; margin: 28px 0 12px; }}
  .card {{
    background: #fff; border-radius: 14px; padding: 16px; margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
  }}
  .card img.thumb {{
    width: 100%; max-height: 180px; object-fit: cover; border-radius: 10px; margin-bottom: 10px;
  }}
  .card .title-link {{ font-size: 16px; font-weight: 600; color: #1a1a1a; text-decoration: none; }}
  .card .title-link:hover {{ text-decoration: underline; }}
  .card .meta {{ font-size: 12px; color: #888; margin-top: 6px; display: flex; align-items: center; gap: 6px; }}
  .card .meta img.favicon {{ width: 14px; height: 14px; border-radius: 3px; }}
  .card .desc {{ font-size: 14px; color: #444; margin-top: 8px; line-height: 1.5; }}
  .badge {{
    display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 10px;
    border-radius: 999px; color: #fff; margin-right: 8px;
  }}
  footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 32px; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111214; color: #eee; }}
    .page-header p {{ color: #aaa; }}
    .card {{ background: #1c1e21; box-shadow: none; border: 1px solid #2c2f33; }}
    .card .title-link {{ color: #f2f2f2; }}
    .card .desc {{ color: #c7c7c7; }}
    .card .meta {{ color: #999; }}
  }}
</style>
</head>
<body>
<div class="wrap">
{body_html}
<footer>Tự động tạo bởi GitHub Actions</footer>
</div>
</body>
</html>"""


def _run_git(args, check=True, capture=False):
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=capture,
        text=True,
    )


def publish_page(relative_path, html_content, commit_message):
    """Write html_content to docs/<relative_path>, commit, and push.

    Retries on push rejection (other daily workflows commit to the same
    branch around the same time). Returns the page's public URL.
    """
    full_path = os.path.join(DOCS_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    rel_git_path = os.path.relpath(full_path, REPO_ROOT)
    url = f"{pages_base_url()}/{relative_path}"

    _run_git(["config", "user.email", "actions@github.com"])
    _run_git(["config", "user.name", "github-actions[bot]"])
    _run_git(["add", rel_git_path])

    status = _run_git(["status", "--porcelain", rel_git_path], capture=True)
    if not status.stdout.strip():
        print(f"[pages] {rel_git_path} unchanged, skipping commit.")
        return url

    _run_git(["commit", "-m", commit_message])

    for attempt in range(5):
        push = _run_git(["push"], check=False, capture=True)
        if push.returncode == 0:
            print(f"[pages] Published {url}")
            return url
        print(f"[pages] push rejected (attempt {attempt + 1}/5): {push.stderr.strip()}")
        _run_git(["fetch", "origin"])
        _run_git(["rebase", "origin/main"])
        time.sleep(2)

    raise RuntimeError(f"Failed to push {rel_git_path} after retries.")
