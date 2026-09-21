"""
Bot AI gửi tin tức thị trường qua Telegram (dùng Gemini API - miễn phí)
=========================================================================
Luồng hoạt động:
1. Lấy tin mới nhất từ (các) RSS feed tài chính/kinh doanh
2. Lọc ra những tin CHƯA từng gửi (dựa vào file sent_links.json)
3. Nếu có tin mới -> gửi cho Gemini tóm tắt -> gửi qua Telegram
4. Nếu không có tin mới -> không làm gì (tiết kiệm quota API)
5. Cập nhật lại sent_links.json để lần chạy sau không gửi trùng

LƯU Ý VỀ MODEL GEMINI:
Model "gemini-2.5-flash" dùng trong file này thuộc gói FREE TIER của Google,
nhưng theo lịch công bố, Google sẽ ngừng hỗ trợ dòng Gemini 2.5 vào 16/10/2026.
Sau mốc đó, đổi biến GEMINI_MODEL bên dưới sang model mới hơn (kiểm tra tại
https://ai.google.dev/gemini-api/docs/models để biết model free tier hiện hành).
"""

import os
import json
import feedparser
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()  # đọc biến môi trường từ .env khi chạy ở máy cá nhân

# ---------- CẤU HÌNH ----------

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Đổi model tại đây nếu Google ngừng hỗ trợ gemini-2.5-flash sau 16/10/2026
GEMINI_MODEL = "gemini-2.5-flash"

RSS_FEEDS = [
    "https://cafef.vn/thi-truong-chung-khoan.rss",
    "https://vnexpress.net/rss/kinh-doanh.rss",
]

MAX_ARTICLES_PER_FEED = 10       # số bài mới nhất lấy từ mỗi nguồn mỗi lần quét
SENT_LINKS_FILE = "sent_links.json"
MAX_SENT_LINKS_KEPT = 300        # chỉ giữ lại N link gần nhất để file không phình to mãi

client = genai.Client(api_key=GEMINI_API_KEY)


# ---------- BƯỚC 1: LẤY TIN TỪ RSS ----------

def fetch_latest_news():
    """Lấy các bài viết mới nhất từ danh sách RSS feed."""
    articles = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "source": feed.feed.get("title", feed_url),
            })
    return articles


# ---------- BƯỚC 2: CHỐNG GỬI TRÙNG ----------

def load_sent_links():
    """Đọc danh sách link đã từng gửi từ file JSON (nếu chưa có thì trả về set rỗng)."""
    if not os.path.exists(SENT_LINKS_FILE):
        return set()
    with open(SENT_LINKS_FILE, "r", encoding="utf-8") as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()


def save_sent_links(sent_links_set):
    """Lưu danh sách link đã gửi, chỉ giữ lại N link gần nhất."""
    links_list = list(sent_links_set)[-MAX_SENT_LINKS_KEPT:]
    with open(SENT_LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links_list, f, ensure_ascii=False, indent=2)


def filter_new_articles(articles, sent_links_set):
    """Chỉ giữ lại các bài có link chưa từng xuất hiện trong sent_links_set."""
    return [a for a in articles if a["link"] and a["link"] not in sent_links_set]


# ---------- BƯỚC 3: DÙNG AI TÓM TẮT / PHÂN TÍCH ----------

def summarize_with_ai(articles):
    """Gửi danh sách bài viết MỚI cho Gemini để tóm tắt thành bản tin ngắn gọn."""
    raw_text = "\n\n".join(
        f"Nguồn: {a['source']}\nTiêu đề: {a['title']}\nMô tả: {a['summary']}\nLink: {a['link']}"
        for a in articles
    )

    prompt = f"""Dưới đây là các tin tức thị trường/kinh doanh VỪA MỚI xuất hiện (chưa từng được gửi trước đây):

{raw_text}

Hãy viết một bản tin ngắn gọn bằng tiếng Việt cho nhà đầu tư cá nhân, gồm:
1. Điểm qua từng tin quan trọng (1-2 câu mỗi tin)
2. Nhận định ngắn về tác động tới thị trường (nếu có đủ thông tin)
3. Định dạng Markdown đơn giản (in đậm bằng *, không dùng bảng)
Giữ bản tin ngắn gọn, súc tích."""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


# ---------- BƯỚC 4: GỬI QUA TELEGRAM ----------

def send_telegram_message(text):
    """Gửi tin nhắn tới Telegram bằng Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------- CHẠY TOÀN BỘ LUỒNG ----------

def main():
    print("Đang lấy tin tức mới nhất...")
    all_articles = fetch_latest_news()

    sent_links = load_sent_links()
    new_articles = filter_new_articles(all_articles, sent_links)

    if not new_articles:
        print("Không có tin mới. Không gửi gì cả.")
        return

    print(f"Phát hiện {len(new_articles)} tin mới. Đang tóm tắt bằng Gemini...")
    summary = summarize_with_ai(new_articles)

    print("Đang gửi bản tin qua Telegram...")
    send_telegram_message(f"📈 *Bản tin thị trường*\n\n{summary}")

    # Cập nhật danh sách link đã gửi
    sent_links.update(a["link"] for a in new_articles)
    save_sent_links(sent_links)

    print("Xong! Kiểm tra Telegram của bạn.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Có lỗi xảy ra: {e}")
        raise
