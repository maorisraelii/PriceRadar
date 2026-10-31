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
FIREBASE_SERVICE_ACCOUNT = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()


def send_fcm_notification(fcm_token: str, title: str, body: str, url: str = ""):
    if not fcm_token or not FIREBASE_SERVICE_ACCOUNT:
        return
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        sa_info = json.loads(FIREBASE_SERVICE_ACCOUNT)
        project_id = sa_info.get("project_id")
        creds = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        bearer = creds.token

        fcm_endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        payload = {
            "message": {
                "token": fcm_token,
                "notification": {
                    "title": title,
                    "body": body
                },
                "data": {
                    "url": url
                },
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": "price_radar_alerts",
                        "default_sound": True,
                        "default_vibrate_timings": True
                    }
                }
            }
        }
        req = urllib.request.Request(
            fcm_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {bearer}",
                "Content-Type": "application/json"
            }
        )
        urllib.request.urlopen(req, timeout=12)
        print(f"✅ FCM Push sent successfully to {fcm_token[:15]}...")
    except Exception as exc:
        print("FCM Push error:", exc)



def check_amazon_free_shipping(html: str) -> bool:
    if not html:
        return False
    clean = re.sub(r"[\u200E\u200F\u202A-\u202E]", "", html)
    pattern = r"(?:FREE Shipping|משלוח חינם|זכאי למשלוח חינם).*(?:to Israel|לישראל|מעל\s*\$?49|49\$)|qualif(?:y|ies) for FREE Shipping to Israel|eligible for FREE Shipping to Israel"
    return bool(re.search(pattern, clean, re.I))


def extract_ksp_uin(url: str) -> str:
    m = re.search(r"ksp\.co\.il/(?:web/|mob/)?item/(\d+)", url or "", re.I)
    return m.group(1) if m else ""


def get_scrape_candidates(url: str) -> list[str]:
    """Returns ordered scrape candidate URLs (including KSP anti-bot mirrors and SSR routes)."""
    uin = extract_ksp_uin(url)
    if uin:
        return [
            f"https://pricedrop.co.il/item/{uin}",
            f"https://ksp.co.il/mob/item/{uin}",
            f"https://ksp-co-il.translate.goog/mob/item/{uin}?_x_tr_sl=es&_x_tr_tl=iw&_x_tr_hl=iw&_x_tr_pto=wapp"
        ]
    return [url.strip()]


def is_blocked_html(html: str) -> bool:
    if not html or len(html) < 160:
        return True
    blocked_markers = [
        "Just a moment...",
        "cf_chl_opt",
        "cf-browser-verification",
        "Attention Required! | Cloudflare",
        "Enable JavaScript and cookies to continue",
        "Access Denied",
        "שגיאה 500",
        "אירעה שגיאה לא צפויה"
    ]
    return any(marker in html for marker in blocked_markers)


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
    if is_blocked_html(html):
        return None

    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(url)
    url_variant_id = parse_qs(parsed_url.query).get("variant", [""])[0]

    # 1. Amazon Specific Selectors
    amz_el = soup.select_one(".a-price:not(.a-text-price) .a-offscreen, #corePrice_feature_div .a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice")
    if amz_el:
        txt = re.sub(r"[^0-9.]", "", amz_el.get_text(strip=True))
        try:
            val = float(txt)
            if val > 0.5:
                return val
        except ValueError:
            pass

    # 2. Machsanei Hashmal (payngo.co.il) Selectors
    payngo_el = soup.select_one('[data-price-type="finalPrice"] .price, .special-price .price, .price-box .price')
    if payngo_el:
        clean_txt = re.sub(r"[‎‏‪-‮]", "", payngo_el.get_text(strip=True))
        clean_txt = re.sub(r"[^0-9.]", "", clean_txt)
        try:
            val = float(clean_txt)
            if val > 5:
                if "אילת" in selected_variant:
                    return round(val / 1.18)
                return val
        except ValueError:
            pass

    # 3. AliExpress Selectors
    ali_el = soup.select_one(".product-price-current, .uniform-banner-box-price")
    if ali_el:
        txt = re.sub(r"[^0-9.]", "", ali_el.get_text(strip=True))
        try:
            val = float(txt)
            if val > 0.5:
                return val
        except ValueError:
            pass

    # 4. WooCommerce data-product_variations
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

    # 5. Schema.org JSON-LD
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

    # 6. OpenGraph Meta Price
    for prop in ["product:price:amount", "og:price:amount"]:
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            try:
                return float(meta["content"])
            except ValueError:
                pass

    # 7. Clean text extraction with Unicode RTL stripping & Multi-Currency support
    for rel in soup.select("script, style, .related, .upsells, footer, nav, header"):
        rel.decompose()
    full_text = re.sub(r"[\u200E\u200F\u202A-\u202E]", "", soup.get_text("\n", strip=True))

    # 7a. Pricedrop KSP mirror pattern
    pd1 = re.search(r"₪\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*מחיר\s+(?:נוכחי|אחרון)", full_text)
    pd2 = re.search(r"מחיר\s+(?:נוכחי|אחרון)\s*[:\s\r\n]*?(?:₪\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*₪?", full_text)
    if pd1 or pd2:
        reg_val = float((pd1.group(1) if pd1 else pd2.group(1)).replace(",", ""))
        if reg_val > 5:
            return float(round(reg_val / 1.18)) if "אילת" in selected_variant else reg_val

    # 7b. Machsanei Hashmal (payngo) text pattern
    m_payngo = re.search(r"מחיר\s*(?:מיוחד)?\s*:\s*(?:לרכישה עכשיו ב\s*:\s*)?₪?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*₪?", full_text)
    if m_payngo:
        val = float(m_payngo.group(1).replace(",", ""))
        if "אילת" in selected_variant:
            m_eil = re.search(r"קנו באילת ב\s*:\s*₪?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*₪?", full_text)
            if m_eil:
                return float(m_eil.group(1).replace(",", ""))
            return float(round(val / 1.18))
        return val

    for marker in ["אפשרות איסוף ומשלוח", "הטבות והצעות משלימות", "לקוחות שהתעניינו במוצר זה", "מוצרים נוספים שיכולים להתאים"]:
        idx = full_text.find(marker)
        if idx > 40:
            full_text = full_text[:idx]

    if "אילת" in selected_variant:
        m_eilat = re.search(r"מחיר\s+אילת\s*:\s*[\r\n]*\s*(?:₪|שח|ILS)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", full_text, re.I)
        if m_eilat:
            return float(m_eilat.group(1).replace(",", ""))

    m_reg = re.search(r"מחיר\s*:\s*[\r\n]*\s*(?:₪|שח|ILS)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", full_text, re.I)
    if m_reg:
        reg_val = float(m_reg.group(1).replace(",", ""))
        if "אילת" in selected_variant:
            return float(round(reg_val / 1.18))
        return reg_val

    # 7c. Multi-currency match for Amazon ($ / € / £ / ₪) and AliExpress
    m_curr = re.search(r"(?:Price|Deal Price|Our Price|מחיר|מחיר מבצע)?\s*[:\s]*?(?:(?:US\s*)?([₪$€£]|USD|ILS|EUR)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)|(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:[₪$€£]|USD|ILS|EUR))", full_text, re.I)
    if m_curr:
        val = float((m_curr.group(2) or m_curr.group(3)).replace(",", ""))
        if 0.5 < val < 500000:
            return val

    for line in full_text.splitlines():
        if re.search(r"משלוח|איסוף|מינימום|מקסימום|קופון|בקנייה מעל|תוספת|shipping|delivery", line, re.I):
            continue
        m = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*[₪$€£]|[₪$€£]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", line)
        if m:
            val = float((m.group(1) or m.group(2)).replace(",", ""))
            if 1 < val < 500000:
                return val

    return None

def check_product_live(browser_page, product: dict):
    raw_url = product.get("url", "")
    selected_variant = product.get("SelectedVariant") or ""
    parsed_url = urlparse(raw_url)
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

    for candidate_url in get_scrape_candidates(raw_url):
        try:
            browser_page.goto(candidate_url, wait_until="domcontentloaded", timeout=28000)
            browser_page.wait_for_timeout(2200)
            html = browser_page.content()
            price = extract_price_from_html(html, raw_url, selected_variant)
            if price is not None and price > 0:
                return price
        except Exception as exc:
            print(f"Error checking candidate {candidate_url}: {exc}")

    return None


def process_profile(page, data: dict, chat_id: str, now_il: datetime, fcm_token: str = ""):
    products = data.get("products", [])
    if not products:
        return False

    time_str = now_il.strftime("%H:%M")
    date_str = now_il.strftime("%d/%m/%Y")
    today_iso = now_il.strftime("%Y-%m-%d")

    for prod in products:
        raw_url = prod.get("url", "")
        new_price = check_product_live(page, prod)

        # Check Amazon Free Shipping to Israel change:
        if "amazon." in raw_url.lower():
            try:
                page_content = page.content()
                is_free_ship = check_amazon_free_shipping(page_content)
                was_free_ship = bool(prod.get("freeShippingEligible"))
                prod["freeShippingEligible"] = is_free_ship

                if not was_free_ship and is_free_ship and prod.get("trackFreeShipping") is not False:
                    curr_p = new_price or prod.get("currentPrice") or 0
                    fs_text = (
                        f"✈️ בשורה מעולה! משלוח חינם לישראל באמזון!\n\n"
                        f"🛍️ מוצר: {prod.get('title')}\n"
                        f"📦 המוצר זכאי כעת למשלוח חינם לישראל בקנייה מעל $49!\n"
                        f"💰 מחיר נוכחי: {curr_p} ₪\n\n"
                        f"🛒 להזמנה מהירה:\n{prod.get('url')}"
                    )
                    send_telegram(fs_text, chat_id)
                    if fcm_token:
                        send_fcm_notification(fcm_token, f"✈️ משלוח חינם לישראל באמזון! {prod.get('title')}", "המוצר זכאי כעת למשלוח חינם לישראל בקנייה מעל 49$!", prod.get('url'))
                    alerts = data.get("alerts") or []
                    alerts.insert(0, {
                        "id": f"fs_{int(now_il.timestamp())}",
                        "type": "drop",
                        "timestamp": f"{time_str} {date_str}",
                        "title": f"✈️ נכנס למשלוח חינם לישראל מעל 49$! {prod.get('title')}",
                        "messagePlain": f"המוצר זכאי כעת למשלוח חינם לישראל בקנייה מעל 49$!",
                        "telegramText": fs_text,
                        "url": prod.get("url")
                    })
                    data["alerts"] = alerts[:100]
            except Exception as e:
                print("Amazon free shipping check notice:", e)
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
            if fcm_token:
                send_fcm_notification(fcm_token, f"🔥 המחיר ירד! {prod.get('title')}{var_txt}", f"ירד מ-{old_price} ₪ ל-{new_price} ₪! (חיסכון של {saved} ₪)", prod.get('url'))
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
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage"
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="he-IL",
            timezone_id="Asia/Jerusalem"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

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
                    fcm_token = row.get("fcm_token") or (payload.get("settings") or {}).get("fcmToken") or ""
                    if process_profile(page, payload, user_chat, now_il, fcm_token):
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
