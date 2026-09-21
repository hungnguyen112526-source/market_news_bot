# Bot AI gửi tin tức thị trường qua Telegram (chạy bằng GitHub Actions)

Bot tự động quét tin tức thị trường mỗi 10 phút, chỉ gửi những tin **thực sự mới**
(chống trùng lặp), tóm tắt bằng AI, rồi gửi qua Telegram.

## Cấu trúc file

```
.
├── market_news_bot.py          # Script chính: lấy tin -> lọc trùng -> tóm tắt AI -> gửi Telegram
├── sent_links.json             # "Bộ nhớ" lưu các link đã gửi, để không gửi lại
├── requirements.txt            # Danh sách thư viện Python cần cài
├── .env.example                # Mẫu khai báo key (dùng khi chạy ở máy cá nhân)
├── .gitignore                  # Đảm bảo file .env thật không bị đẩy lên GitHub
└── .github/workflows/news.yml  # Cấu hình để GitHub tự chạy bot theo lịch
```

## Cài đặt

### 1. Tạo Telegram Bot
- Chat với **@BotFather** → `/newbot` → lấy **Bot Token**
- Nhắn 1 tin bất kỳ cho bot, sau đó mở:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
  để lấy **Chat ID** (nằm trong `"chat":{"id": ...}`)

### 2. Lấy Anthropic API key
Tại https://console.anthropic.com

### 3. Đưa code lên GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ten-ban/ten-repo.git
git branch -M main
git push -u origin main
```
(`.gitignore` đã đảm bảo `.env` không bị đẩy lên — chỉ `.env.example` được đẩy)

### 4. Khai báo Secrets trên GitHub
Vào repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**,
thêm lần lượt:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ANTHROPIC_API_KEY`

### 5. Xong — bot sẽ tự chạy
Workflow `.github/workflows/news.yml` đã được cấu hình chạy **mỗi 10 phút**.
Bạn có thể vào tab **Actions** trên GitHub để xem lịch sử chạy, hoặc bấm
**Run workflow** để chạy thử ngay lập tức.

## Cách hoạt động chống gửi trùng

Mỗi lần chạy:
1. Bot đọc `sent_links.json` để biết những link đã từng gửi
2. So sánh với tin mới lấy từ RSS
3. Chỉ tóm tắt + gửi những tin **chưa từng gửi**
4. Ghi lại các link vừa gửi vào `sent_links.json`
5. Workflow tự động `git commit` + `git push` file này để lần chạy sau (trên máy chủ GitHub khác) vẫn nhớ được lịch sử

→ Nhờ vậy dù chạy mỗi 10 phút, bot sẽ **không gửi lại các tin cũ**, và khi có tin mới thì gửi gần như ngay lập tức.

## Tùy chỉnh

| Muốn thay đổi | Sửa ở đâu |
|---|---|
| Tần suất quét tin | `cron: '*/10 * * * *'` trong `news.yml` (đổi số 10 thành số phút bạn muốn, tối thiểu ~5) |
| Nguồn tin | Danh sách `RSS_FEEDS` trong `market_news_bot.py` |
| Văn phong/nội dung bản tin | Đoạn `prompt` trong hàm `summarize_with_ai()` |
| Số bài quét mỗi nguồn mỗi lần | `MAX_ARTICLES_PER_FEED` |
| Số link nhớ để chống trùng | `MAX_SENT_LINKS_KEPT` |

## Lưu ý

- Cron của GitHub Actions chạy theo **giờ UTC**, có thể trễ vài phút vào giờ cao điểm — đây là giới hạn của GitHub, không phải lỗi code.
- Repo **public**: chạy Actions miễn phí không giới hạn. Repo **private**: có khoảng 2000 phút chạy free/tháng — với tần suất 10 phút/lần, mỗi lần chạy ~30-60 giây thì vẫn thoải mái trong hạn mức.
- Nếu muốn thực sự tức thời với **giá** (không phải tin văn bản), cân nhắc dùng WebSocket của sàn giao dịch (ví dụ Binance) thay vì polling RSS.
