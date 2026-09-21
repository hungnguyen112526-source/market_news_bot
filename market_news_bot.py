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
Model đang dùng là "gemini-3.6-flash" (xem biến GEMINI_MODEL bên dưới). Google
thường xuyên thay đổi model được cấp miễn phí, nên nếu gặp lỗi "model not found"
trong log GitHub Actions, vào https://ai.google.dev/gemini-api/docs/models để
kiểm tra model free tier hiện hành và cập nhật lại biến GEMINI_MODEL.

LƯU Ý VỀ LỖI 503 (quá tải):
Nếu Gemini báo lỗi 503 "currently experiencing high demand", code sẽ tự động
thử lại tối đa 3 lần (đợi tăng dần 10s, 20s, 40s) trước khi báo lỗi thật sự.
"""

import os
import json
import time
import feedparser
import requests
from google import genai
from google.genai import errors as genai_errors
from dotenv import load_dotenv

load_dotenv()  # đọc biến môi trường từ .env khi chạy ở máy cá nhân

# ---------- CẤU HÌNH ----------

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# gemini-2.5-flash đã bị Google ngừng cấp cho user mới (10/2026), đổi sang gemini-3.6-flash.
# Nếu sau này lại đổi tiếp, xem model free tier hiện hành tại:
# https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = "gemini-3.6-flash"

RSS_FEEDS = [
    "https://cafef.vn/thi-truong-chung-khoan.rss",
    "https://vnexpress.net/rss/kinh-doanh.rss",
]

MAX_ARTICLES_PER_FEED = 10       # số bài mới nhất lấy từ mỗi nguồn mỗi lần quét
SENT_LINKS_FILE = "sent_links.json"
MAX_SENT_LINKS_KEPT = 300        # chỉ giữ lại N link gần nhất để file không phình to mãi

MAX_RETRIES = 3                  # số lần thử lại tối đa khi Gemini bị quá tải (503)
RETRY_BASE_DELAY_SECONDS = 10    # thời gian đợi trước lần thử lại đầu tiên (tăng dần gấp đôi)

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

    response = call_gemini_with_retry(prompt)
    return response.text


def call_gemini_with_retry(prompt):
    """Gọi Gemini, tự động thử lại (backoff tăng dần) nếu server báo quá tải (503)."""
    delay = RETRY_BASE_DELAY_SECONDS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        except genai_errors.ServerError as e:
            is_last_attempt = attempt == MAX_RETRIES
            print(f"Gemini đang quá tải (lần thử {attempt}/{MAX_RETRIES}): {e}")
            if is_last_attempt:
                raise
            print(f"Đợi {delay}s rồi thử lại...")
            time.sleep(delay)
            delay *= 2  # tăng gấp đôi thời gian đợi mỗi lần thử lại


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
