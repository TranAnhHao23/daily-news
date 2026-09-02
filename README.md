# Daily News Digest

Tự động tổng hợp tin tức (Việt Nam / Thế giới / Công nghệ & AI) từ RSS, tóm tắt
bằng Google Gemini (miễn phí), và gửi vào Discord (qua webhook) mỗi ngày lúc
**9:00 sáng (giờ Việt Nam)**.

Chạy hoàn toàn bằng **GitHub Actions** — không cần server riêng.

## Cách hoạt động

1. GitHub Actions chạy `scripts/fetch_and_summarize.py` theo lịch cron
   `0 2 * * *` (UTC) = 9:00 sáng giờ Việt Nam (UTC+7).
2. Script lấy tin từ các nguồn RSS trong khoảng **00:00 hôm qua → 9:00 sáng
   hôm nay**.
3. Gửi toàn bộ tin thô cho Gemini để tóm tắt súc tích theo từng chủ đề.
4. Đăng bản tin vào kênh Discord của bạn qua webhook.

Nguồn tin mặc định (chỉnh trong `scripts/fetch_and_summarize.py`, biến `FEEDS`):

- **Tin tức Việt Nam**: VnExpress, Tuổi Trẻ, Dân Trí, CafeBiz
- **Tin thế giới**: VnExpress Thế giới, BBC World
- **Công nghệ & AI**: VnExpress Số hóa, TechCrunch

## Nhận thông báo trên iPhone

Cài app **Discord** trên iPhone, join server chứa kênh có webhook, bật thông
báo cho kênh đó → bạn sẽ nhận push notification lúc 9h sáng mỗi ngày.

## Thiết lập

### 1. Đẩy project này lên GitHub

```bash
cd "Daily news"
git init
git add .
git commit -m "Initial daily news digest project"
```

Tạo repo mới trên github.com (private nếu muốn), rồi:

```bash
git remote add origin git@github.com:<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

### 2. Lấy Gemini API key (miễn phí)

Vào https://aistudio.google.com/apikey, đăng nhập bằng tài khoản Google, bấm
**Create API key**. Free tier hiện tại đủ dùng thoải mái cho 1 lần chạy/ngày.

### 3. Thêm GitHub Secrets

Vào repo trên GitHub → **Settings → Secrets and variables → Actions → New
repository secret**, thêm 2 secret:

| Name | Giá trị |
|---|---|
| `GEMINI_API_KEY` | API key lấy ở bước 2 |
| `DISCORD_WEBHOOK_URL` | Webhook URL của kênh Discord bạn muốn nhận tin |

**Không** commit 2 giá trị này vào code — luôn để trong GitHub Secrets.

### 4. Test thử

Vào tab **Actions** trên GitHub → chọn workflow **Daily News Digest** →
**Run workflow** để chạy thử ngay, không cần chờ đến 9h sáng.

### 5. Chạy tự động

Workflow đã cấu hình sẵn cron `0 2 * * *` (UTC) = 9:00 sáng giờ Việt Nam,
chạy mỗi ngày mà không cần làm gì thêm.

> Lưu ý: GitHub Actions cron không đảm bảo chạy đúng giờ tuyệt đối — có thể
> trễ vài phút vào giờ cao điểm.

## Chạy thử ở máy local (tùy chọn)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="AIza..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python scripts/fetch_and_summarize.py
```

## Tùy chỉnh

- Đổi/thêm nguồn RSS: sửa dict `FEEDS` trong `scripts/fetch_and_summarize.py`.
- Đổi số lượng tin mỗi chủ đề: sửa `MAX_ARTICLES_PER_CATEGORY`.
- Đổi giờ chạy: sửa dòng `cron` trong
  `.github/workflows/daily-digest.yml` (nhớ tính theo giờ UTC).
