# Daily News Digest

Tự động lấy tin tức (Việt Nam / Thế giới / Công nghệ & AI) từ RSS và gửi vào
Discord dưới dạng **card** (ảnh thumbnail + tiêu đề + mô tả ngắn + link gốc)
mỗi ngày lúc **9:00 sáng (giờ Việt Nam)**.

Không dùng AI để tóm tắt — tiêu đề/mô tả lấy thẳng từ RSS, nên không có rủi ro
bị cắt cụt hay bịa nội dung, và cũng không cần đăng ký thêm API key nào ngoài
Discord.

Chạy hoàn toàn bằng **GitHub Actions** — không cần server riêng.

## Cách hoạt động

1. GitHub Actions chạy `scripts/fetch_and_summarize.py` theo lịch cron
   `0 2 * * *` (UTC) = 9:00 sáng giờ Việt Nam (UTC+7).
2. Script lấy tin từ các nguồn RSS trong khoảng **00:00 hôm qua → 9:00 sáng
   hôm nay**.
3. Mỗi chủ đề chọn tối đa 10 tin (chia đều theo từng nguồn để không báo nào
   lấn át báo khác), dựng thành card (Discord embed).
4. Đăng lần lượt từng chủ đề vào kênh Discord của bạn qua webhook — mỗi tin
   là 1 card riêng biệt, có ảnh, tiêu đề bấm được, mô tả ngắn, tên nguồn +
   giờ đăng.

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

### 2. Thêm GitHub Secret

Vào repo trên GitHub → **Settings → Secrets and variables → Actions → New
repository secret**, thêm:

| Name | Giá trị |
|---|---|
| `DISCORD_WEBHOOK_URL` | Webhook URL của kênh Discord bạn muốn nhận tin |

**Không** commit giá trị này vào code — luôn để trong GitHub Secrets.

#### (Tùy chọn) Gửi vào 1 thread cố định thay vì gửi thẳng ra channel

1. Trong Discord, bật **Developer Mode**: User Settings → Advanced → Developer Mode.
2. Tạo 1 thread trong channel đó (hoặc dùng thread có sẵn).
3. Chuột phải vào thread → **Copy Thread ID**.
4. Thêm secret `DISCORD_THREAD_ID` với giá trị là ID vừa copy.

Nếu không thêm secret này, bot sẽ gửi thẳng vào channel như bình thường.

### 3. Test thử

Vào tab **Actions** trên GitHub → chọn workflow **Daily News Digest** →
**Run workflow** để chạy thử ngay, không cần chờ đến 9h sáng.

### 4. Chạy tự động

Workflow đã cấu hình sẵn cron `0 2 * * *` (UTC) = 9:00 sáng giờ Việt Nam,
chạy mỗi ngày mà không cần làm gì thêm.

> Lưu ý: GitHub Actions cron không đảm bảo chạy đúng giờ tuyệt đối — có thể
> trễ vài phút vào giờ cao điểm.

## Chạy thử ở máy local (tùy chọn)

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python scripts/fetch_and_summarize.py
```

## Tùy chỉnh

- Đổi/thêm nguồn RSS: sửa dict `FEEDS` trong `scripts/fetch_and_summarize.py`.
- Đổi số card tối đa mỗi chủ đề: sửa `MAX_CARDS_PER_CATEGORY` (Discord giới
  hạn tối đa 10 embed/tin nhắn, tăng quá 10 sẽ tự động chia thành nhiều tin
  nhắn liên tiếp trong cùng chủ đề).
- Đổi màu card theo từng chủ đề: sửa dict `CATEGORY_COLORS`.
- Đổi giờ chạy: sửa dòng `cron` trong
  `.github/workflows/daily-digest.yml` (nhớ tính theo giờ UTC).
