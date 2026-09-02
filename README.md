# Daily Discord Digests

3 script tự động chạy mỗi ngày **9:00 sáng (giờ Việt Nam)** bằng **GitHub
Actions** (không cần server riêng), gửi kết quả vào Discord dưới dạng card:

| Script | Nội dung | Cần API key ngoài Discord? |
|---|---|---|
| `scripts/fetch_and_summarize.py` | Tin tức VN / Thế giới / Công nghệ từ RSS | Không |
| `scripts/leetcode_daily.py` | 5 bài LeetCode (2 Dễ + 2 TB + 1 Khó) | Không |
| `scripts/vocab_daily.py` | Từ vựng tiếng Anh theo chủ đề + mức độ | Có — Gemini (miễn phí) |

Mỗi script có workflow GitHub Actions riêng, chạy độc lập, gửi vào webhook
Discord riêng (bạn có thể trỏ cả 3 vào cùng 1 kênh/channel nếu muốn, chỉ cần
dùng chung 1 webhook URL cho các secret tương ứng).

## 1. Bản tin tin tức — `daily-digest.yml`

Lấy tin từ RSS (VnExpress, Tuổi Trẻ, Dân Trí, CafeBiz, BBC World,
TechCrunch...) trong khoảng **00:00 hôm qua → 9:00 sáng hôm nay**, chọn tối đa
10 tin/chủ đề (chia đều theo từng nguồn), đăng thành card (ảnh + tiêu đề +
mô tả ngắn + nguồn) vào Discord. Không dùng AI — tiêu đề/mô tả lấy thẳng từ
RSS.

Nguồn tin mặc định (chỉnh trong `scripts/fetch_and_summarize.py`, biến `FEEDS`):

- **Tin tức Việt Nam**: VnExpress, Tuổi Trẻ, Dân Trí, CafeBiz
- **Tin thế giới**: VnExpress Thế giới, BBC World
- **Công nghệ & AI**: VnExpress Số hóa, TechCrunch

**Secrets cần thêm:**

| Name | Giá trị |
|---|---|
| `DISCORD_WEBHOOK_URL` | Webhook URL của kênh/thread Discord nhận bản tin |
| `DISCORD_THREAD_ID` *(tùy chọn)* | Gửi vào 1 thread cố định thay vì channel gốc |

## 2. LeetCode mỗi ngày — `leetcode-daily.yml`

Chọn ngẫu nhiên (theo ngày, có seed nên chạy lại trong ngày ra kết quả giống
nhau) 5 bài từ LeetCode: 2 Dễ + 2 Trung bình + 1 Khó, tự động bỏ qua bài
Premium-only. Mỗi bài là 1 card: tên bài (bấm vào mở LeetCode), độ khó, tag
chủ đề, tỉ lệ AC.

**Secrets cần thêm:**

| Name | Giá trị |
|---|---|
| `LEETCODE_DISCORD_WEBHOOK_URL` | Webhook URL của kênh/thread Discord nhận bài |
| `LEETCODE_DISCORD_THREAD_ID` *(tùy chọn)* | Gửi vào 1 thread cố định |

Đổi tỉ lệ độ khó: sửa `DIFFICULTY_PLAN` trong `scripts/leetcode_daily.py`.

## 3. Từ vựng mỗi ngày — `vocab-daily.yml`

Dùng Google Gemini (miễn phí) để tạo danh sách từ vựng tiếng Anh theo chủ đề
+ mức độ bạn chọn, mỗi từ gồm: phiên âm, từ loại, nghĩa tiếng Việt, câu ví dụ
Anh–Việt. Chủ đề xoay vòng mỗi ngày nếu bạn khai nhiều hơn 1 chủ đề.

Cấu hình trong `scripts/vocab_daily.py`:

```python
VOCAB_TOPICS = ["Giao tiếp hàng ngày", "IELTS/TOEIC học thuật"]
VOCAB_LEVEL = "Intermediate (CEFR B1-B2)"
WORDS_PER_DAY = 8
```

**Secrets cần thêm:**

| Name | Giá trị |
|---|---|
| `GEMINI_API_KEY` | Lấy miễn phí tại https://aistudio.google.com/apikey |
| `VOCAB_DISCORD_WEBHOOK_URL` | Webhook URL của kênh/thread Discord nhận từ vựng |
| `VOCAB_DISCORD_THREAD_ID` *(tùy chọn)* | Gửi vào 1 thread cố định |

## Nhận thông báo trên iPhone

Cài app **Discord** trên iPhone, join server chứa các kênh/thread trên, bật
thông báo cho từng kênh/thread → nhận push notification lúc 9h sáng mỗi ngày.

## Thiết lập chung

### 1. Đẩy project này lên GitHub

```bash
cd "Daily news"
git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

### 2. Thêm GitHub Secrets

Vào repo trên GitHub → **Settings → Secrets and variables → Actions → New
repository secret**, thêm các secret liệt kê ở từng mục phía trên tùy theo
script bạn muốn bật. **Không** commit các giá trị này vào code.

#### Lấy Discord Thread ID (nếu muốn gửi vào 1 thread cố định)

1. Trong Discord, bật **Developer Mode**: User Settings → Advanced → Developer Mode.
2. Tạo 1 thread trong channel đó (hoặc dùng thread có sẵn).
3. Chuột phải vào thread → **Copy Thread ID**.

### 3. Test thử

Vào tab **Actions** trên GitHub → chọn workflow tương ứng (**Daily News
Digest** / **Daily LeetCode Picks** / **Daily Vocabulary**) → **Run
workflow** để chạy thử ngay, không cần chờ đến 9h sáng.

### 4. Chạy tự động

Cả 3 workflow đã cấu hình sẵn cron `0 2 * * *` (UTC) = 9:00 sáng giờ Việt
Nam, chạy mỗi ngày mà không cần làm gì thêm.

> Lưu ý: GitHub Actions cron không đảm bảo chạy đúng giờ tuyệt đối — có thể
> trễ vài phút vào giờ cao điểm.

## Chạy thử ở máy local (tùy chọn)

```bash
pip install -r requirements.txt

# Bản tin tin tức
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python scripts/fetch_and_summarize.py

# LeetCode
export LEETCODE_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python scripts/leetcode_daily.py

# Từ vựng
export GEMINI_API_KEY="AIza..."
export VOCAB_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python scripts/vocab_daily.py
```
