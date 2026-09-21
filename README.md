# Bot AI gửi tin tức thị trường qua Telegram (GitHub Actions + Gemini API miễn phí)

Bot tự động quét tin tức thị trường mỗi 10 phút, chỉ gửi những tin **thực sự mới**
(chống trùng lặp), tóm tắt bằng **Google Gemini API (miễn phí)**, rồi gửi qua Telegram.

## Cấu trúc file

```
.
├── market_news_bot.py          # Script chính: lấy tin -> lọc trùng -> tóm tắt Gemini -> gửi Telegram
├── sent_links.json             # "Bộ nhớ" lưu các link đã gửi, để không gửi lại
├── requirements.txt            # Danh sách thư viện Python cần cài
├── .env.example                # Mẫu khai báo key (dùng khi chạy ở máy cá nhân)
├── .gitignore                  # Đảm bảo file .env thật không bị đẩy lên GitHub
└── .github/workflows/news.yml  # Cấu hình để GitHub tự chạy bot theo lịch
```

## Cài đặt

### 1. Tạo Telegram Bot
- Chat với **@BotFather** trên Telegram → `/newbot` → lấy **Bot Token**
- Nhắn 1 tin bất kỳ cho bot vừa tạo, sau đó mở:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
  để lấy **Chat ID** (nằm trong `"chat":{"id": ...}`)

### 2. Lấy Gemini API key (miễn phí)
- Vào https://aistudio.google.com/apikey
- Đăng nhập bằng tài khoản Google, bấm **Create API key**
- **Không cần khai báo thẻ thanh toán** để dùng gói free tier

> ⚠️ Model `gemini-2.5-flash` đang dùng trong code sẽ bị Google ngừng hỗ trợ vào
> **16/10/2026**. Sau mốc này, cần đổi biến `GEMINI_MODEL` trong
> `market_news_bot.py` sang model mới hơn — kiểm tra danh sách model free tier
> hiện hành tại https://ai.google.dev/gemini-api/docs/models

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
- `GEMINI_API_KEY`

### 5. Xong — bot sẽ tự chạy
Workflow `.github/workflows/news.yml` đã được cấu hình chạy **mỗi 10 phút**.
Vào tab **Actions** trên GitHub để xem lịch sử chạy, hoặc bấm **Run workflow**
để chạy thử ngay lập tức.

## Cách hoạt động chống gửi trùng

Mỗi lần chạy:
1. Bot đọc `sent_links.json` để biết những link đã từng gửi
2. So sánh với tin mới lấy từ RSS
3. Chỉ tóm tắt + gửi những tin **chưa từng gửi**
4. Ghi lại các link vừa gửi vào `sent_links.json`
5. Workflow tự động `git commit` + `git push` file này để lần chạy sau vẫn nhớ được lịch sử

## Về giới hạn miễn phí của Gemini API

Gói free tier của Gemini có giới hạn số lượt gọi theo phút/ngày (thay đổi tùy model
và thời điểm — Google cập nhật khá thường xuyên). Vì bot chỉ gọi AI **khi có tin mới**
(không gọi mỗi lần quét), mức dùng thực tế thường thấp. Nếu gặp lỗi `429` (rate limit)
trong log của GitHub Actions, nghĩa là bạn đã vượt hạn mức free tier tại thời điểm đó —
có thể giảm tần suất quét (sửa cron trong `news.yml`) hoặc đợi hạn mức reset (thường theo ngày).

## Tùy chỉnh

| Muốn thay đổi | Sửa ở đâu |
|---|---|
| Tần suất quét tin | `cron: '*/10 * * * *'` trong `news.yml` (đổi số 10 thành số phút bạn muốn, tối thiểu ~5) |
| Nguồn tin | Danh sách `RSS_FEEDS` trong `market_news_bot.py` |
| Model Gemini | Biến `GEMINI_MODEL` trong `market_news_bot.py` |
| Văn phong/nội dung bản tin | Đoạn `prompt` trong hàm `summarize_with_ai()` |
| Số bài quét mỗi nguồn mỗi lần | `MAX_ARTICLES_PER_FEED` |
| Số link nhớ để chống trùng | `MAX_SENT_LINKS_KEPT` |

## Lưu ý

- Cron của GitHub Actions chạy theo **giờ UTC**, có thể trễ vài phút vào giờ cao điểm — đây là giới hạn của GitHub, không phải lỗi code.
- Repo **public**: chạy Actions miễn phí không giới hạn. Repo **private**: có khoảng 2000 phút chạy free/tháng.
- Nếu muốn thực sự tức thời với **giá** (không phải tin văn bản), cân nhắc dùng WebSocket của sàn giao dịch (ví dụ Binance) thay vì polling RSS.
