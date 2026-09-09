import json
import os
import feedparser
import requests
from google import genai

# 讀取 GitHub Secrets 環境變數
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# 動態讀取 stocks.json 內的監控清單
def load_watchlist():
  if os.path.exists("stocks.json"):
    with open("stocks.json", "r", encoding="utf-8") as f:
      return json.load(f)
  return ["ONDS"]


# 讀取/儲存已發送過嘅新聞記錄 (防重複)
SEEN_FILE = "seen_news.json"


def load_seen():
  if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  return []


def save_seen(seen_list):
  with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(seen_list[-100:], f, ensure_ascii=False)


stocks = load_watchlist()
seen_news = load_seen()
client = genai.Client(api_key=GEMINI_API_KEY)
new_entries_found = False

for ticker in stocks:
  rss_url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
  feed = feedparser.parse(rss_url)

  for entry in feed.entries[:1]:  # 每隻股每次抓最新 1 條
    link = entry.link
    if link in seen_news:
      continue

    seen_news.append(link)
    new_entries_found = True
    title = entry.title
    summary = entry.get("summary", title)

    # 專業分析 Prompt (Professional Cross-Reference)
    prompt = f"""
        請針對美股 {ticker} 嘅呢篇最新新聞進行專業財經分析，嚴格按照以下格式輸出，語氣要精準、專業、帶有實戰視角：
        📊 【美股實時深度快訊】{ticker}
        -----------------------------------
        📌 新聞標題：{title}
        🔥 影響程度：(高 / 中 / 低)
        ⚖️ 利好/利淡：🟢 利好 / 🔴 利淡 / ⚪ 中性
        🎯 核心邏輯與數據點評：(用 2-3 句專業剖析對其財務、Backlog 或燒錢率嘅實質影響)
        🔗 傳送門：{link}

        新聞內容：{summary}
        """

    try:
      response = client.models.generate_content(
          model="gemini-2.5-flash", contents=prompt
      )
      msg_text = response.text
    except Exception as e:
      msg_text = (
          f"📊 【美股快訊】{ticker}\n📌 {title}\n🔗 {link}\n(AI 分析暫時繁忙)"
      )

    # Push 落 Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
      tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
      payload = {
          "chat_id": TELEGRAM_CHAT_ID,
          "text": msg_text,
          "disable_web_page_preview": False,
      }
      requests.post(tg_url, json=payload)

if new_entries_found:
  save_seen(seen_news)
