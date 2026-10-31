import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import urllib.request
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DATA_FILE = "data.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def send_telegram(text: str, chat_id: str = ""):
    target_chat = (chat_id or TELEGRAM_CHAT_ID).strip()
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        print("Telegram not configured for target, message:\n", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": target_chat,
        "text": text,
        "disable_web_page_preview": False
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=12)
    except Exception as exc:
        print("Telegram send error:", exc)


def sync_telegram_bot_subscribers():
    """Links users who clicked /start PR-XXXX in Telegram to their device_id in Supabase."""
    if not TELEGRAM_BOT_TOKEN or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        res = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        updates = json.loads(res).get("result", [])
        for upd in updates:
            msg = upd.get("message") or {}
            txt = (msg.get("text") or "").strip()
            chat = msg.get("chat") or {}
            chat_id = str(chat.get("id") or "")
            if txt.startswith("/start ") and chat_id:
                device_id = txt.split("/start ", 1)[1].strip()
                if device_id.startswith("PR-"):
                    sb_url = f"{SUPABASE_URL}/rest/v1/user_profiles?device_id=eq.{device_id}"
                    body = json.dumps({"telegram_chat_id": chat_id}).encode("utf-8")
                    req = urllib.request.Request(sb_url, data=body, method="PATCH", headers={
                        "apikey": SUPABASE_SERVICE_KEY,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                        "Content-Type": "application/json"
                    })
                    urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        print("Telegram sync warning:", exc)


def extract_price_from_html(html: str, url: str, selected_variant: str = ""):
    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(url)
    url_variant_id = parse_qs(parsed_url.query).get("variant", [""])[0]

    form = soup.find(attrs={"data-product_variations": True})
    if form:
        try:
            variations = json.loads(form["data-product_variations"])
            for v in variations:
                attrs_str = " ".join(str(val) for val in (v.get("attributes") or {}).values())
                if selected_variant and (selected_variant in attrs_str or attrs_str in selected_variant):
                    return float(v.get("display_price") or v.get("display_regular_price"))
            if variations:
                return float(variations[0].get("display_price") or variations[0].get("display_regular_price"))
        except Exception:
            pass

    for scr in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(scr.string or "{}")
            items = data if isinstance(data, list) else data.get("@graph", [data])
            for item in items:
                if isinstance(item, dict) and "Product" in str(item.get("@type", "")):
                    offers = item.get("offers")
                    offer_list = offers if isinstance(offers, list) else (offers.get("offers", [offers]) if isinstance(offers, dict) else [])
                    for off in offer_list:
                        if not isinstance(off, dict):
                            continue
                        p = off.get("price") or off.get("lowPrice")
                        if p:
                            if url_variant_id and str(off.get("sku", "")) == url_variant_id:
                                return float(p)
                            if selected_variant and selected_variant in str(off.get("name", "")):
                                return float(p)
                    for off in offer_list:
                        if isinstance(off, dict) and (off.get("price") or off.get("lowPrice")):
                            return float(off.get("price") or off.get("lowPrice"))
        except Exception:
            pass

    for prop in ["product:price:amount", "og:price:amount"]:
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            try:
                return float(meta["content"])
            except ValueError:
                pass

    for rel in soup.select(".related, .upsells, footer, nav, header"):
        rel.decompose()
    for el in soup.select(".price, .product-price, .sale-price, [class*='price']"):
        txt = el.get_text(" ", strip=True)
        m = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*₪|₪\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", txt)
        if m:
            val = float((m.group(1) or m.group(2)).replace(",", ""))
            if 5 < val < 100000:
                return val

    return None


def check_product_live(browser_page, product: dict):
    url = product.get("url", "")
    selected_variant = product.get("SelectedVariant") or ""
    parsed_url = urlparse(url)
    url_variant_id = parse_qs(parsed_url.query).get("variant", [""])[0]

    if "/products/" in parsed_url.path:
        try:
            json_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rstrip('/')}.json"
            req = urllib.request.Request(json_url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
            prod_data = json.loads(raw).get("product", {})
            for v in prod_data.get("variants", []):
                if (url_variant_id and str(v.get("id")) == url_variant_id) or (selected_variant and v.get("title") in selected_variant):
                    return float(v["price"])
            if prod_data.get("variants"):
                return float(prod_data["variants"][0]["price"])
        except Exception:
            pass

    # Optimized loader for KSP & Client-Side SPA stores
    if "ksp.co.il" in parsed_url.netloc:
        try:
            browser_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                browser_page.wait_for_selector("text=₪, [class*='price'], .price", timeout=8000)
            except Exception:
                browser_page.wait_for_timeout(4000)
            html = browser_page.content()
            price = extract_price_from_html(html, url, selected_variant)
            if price:
                return price
        except Exception as exc:
            print(f"Error checking KSP live: {exc}")

    try:
        browser_page.goto(url, wait_until="domcontentloaded", timeout=25000)
        browser_page.wait_for_timeout(2000)
        html = browser_page.content()
        return extract_price_from_html(html, url, selected_variant)
    except Exception as exc:
        print(f"Error checking {url}: {exc}")
        return None


def process_profile(page, data: dict, chat_id: str, now_il: datetime):
    products = data.get("products", [])
    if not products:
        return False

    time_str = now_il.strftime("%H:%M")
    date_str = now_il.strftime("%d/%m/%Y")
    today_iso = now_il.strftime("%Y-%m-%d")

    for prod in products:
        new_price = check_product_live(page, prod)
        if new_price is None or new_price <= 0:
            continue

        old_price = float(prod.get("currentPrice") or new_price)
        prod["currentPrice"] = new_price
        prod["lowestPrice"] = min(float(prod.get("lowestPrice") or new_price), new_price)
        prod["lastChecked"] = f"{time_str} {date_str}"
        history = prod.get("history") or []
        history.append({"time": time_str, "price": new_price})
        prod["history"] = history[-15:]

        if new_price < old_price:
            saved = round(old_price - new_price, 2)
            pct = round((saved / old_price) * 100)
            var_txt = f" ({prod['SelectedVariant']})" if prod.get("SelectedVariant") else ""
            msg = (
                f"🎉 התראת ירידת מחיר!\n\n"
                f"🛍️ מוצר: {prod.get('title')}{var_txt}\n"
                f"🏪 חנות: {prod.get('store')}\n"
                f"💰 מחיר חדש: {new_price} ₪ (במקום {old_price} ₪)\n"
                f"📉 חיסכון: {saved} ₪ (-{pct}%)\n\n"
                f"🛒 להזמנה מהירה:\n{prod.get('url')}"
            )
            send_telegram(msg, chat_id)
            alerts = data.get("alerts") or []
            alerts.insert(0, {
                "id": f"drop_{int(now_il.timestamp())}",
                "type": "drop",
                "timestamp": f"{time_str} {date_str}",
                "title": f"🔥 המחיר ירד! {prod.get('title')}{var_txt}",
                "messagePlain": f"ירד מ-{old_price} ₪ ל-{new_price} ₪!",
                "telegramText": msg,
                "url": prod.get("url")
            })
            data["alerts"] = alerts[:100]

    settings = data.get("settings") or {}
    daily_hour = (settings.get("dailyTime") or "09:00").split(":")[0]
    if now_il.strftime("%H") == daily_hour and settings.get("lastDailySentDate") != today_iso:
        settings["lastDailySentDate"] = today_iso
        data["settings"] = settings
        lines = []
        drops = 0
        for idx, prod in enumerate(products, 1):
            curr = float(prod.get("currentPrice") or 0)
            init = float(prod.get("initialPrice") or curr)
            diff = round(curr - init, 2)
            if diff < 0:
                drops += 1
                status = f"🔥 ירד ב-{abs(diff)} ₪!"
            elif diff > 0:
                status = f"⬆️ עלה ב-{diff} ₪"
            else:
                status = "➖ ללא שינוי"
            var_txt = f" [{prod['SelectedVariant']}]" if prod.get("SelectedVariant") else ""
            lines.append(f"{idx}. {prod.get('title')}{var_txt} ({prod.get('store')}): כעת {curr} ₪ | {status}")

        daily_msg = (
            f"📊 עדכון מחירים יומי ({settings.get('dailyTime', '09:00')})\n"
            f"מוצרים במעקב: {len(products)} | ירידות מחיר: {drops}\n\n"
            + "\n".join(lines)
        )
        send_telegram(daily_msg, chat_id)

    return True


def main():
    now_il = datetime.now(ZoneInfo("Asia/Jerusalem"))
    sync_telegram_bot_subscribers()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()

        # Mode A: Multi-User Supabase Cloud
        if SUPABASE_URL and SUPABASE_SERVICE_KEY:
            try:
                req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/user_profiles?select=*", headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
                })
                rows = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
                for row in rows:
                    device_id = row.get("device_id")
                    payload = row.get("payload") or {}
                    user_chat = row.get("telegram_chat_id") or TELEGRAM_CHAT_ID
                    if process_profile(page, payload, user_chat, now_il):
                        upd_url = f"{SUPABASE_URL}/rest/v1/user_profiles?device_id=eq.{device_id}"
                        body = json.dumps({"payload": payload, "updated_at": now_il.isoformat()}).encode("utf-8")
                        upd_req = urllib.request.Request(upd_url, data=body, method="PATCH", headers={
                            "apikey": SUPABASE_SERVICE_KEY,
                            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                            "Content-Type": "application/json"
                        })
                        urllib.request.urlopen(upd_req, timeout=15)
            except Exception as exc:
                print("Supabase multi-user check error:", exc)

        # Mode B: Local data.json fallback
        elif os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if process_profile(page, data, TELEGRAM_CHAT_ID, now_il):
                data["updatedAt"] = now_il.isoformat()
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        browser.close()


if __name__ == "__main__":
    main()
