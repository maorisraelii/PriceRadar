# PriceRadar IL — Project Memory & Continuity Guide
> **Note for AI Coding Agent (Cline / Roo Code / Cursor):**  
> This file contains the complete, uncompressed development context, architectural decisions, solved issues, and active state of **PriceRadar IL**. Read this file first to resume the conversation and codebase seamlessly.

---

## 1. Project Overview & Identity
- **Product Name:** PriceRadar IL
- **Repository:** `maorisraelii/PriceRadar` (Branch: `main`)
- **Platform:** Android Mobile App (Capacitor 6 APK) + Progressive Web App (PWA) with GitHub Pages live sync.
- **UI Design System:** Modern **Liquid Glassmorphism** (RTL Hebrew, dark aurora theme `#090716`, Tailwind CSS, smooth responsive glass cards, Chart.js price history graphs).
- **Core Principle:** **Zero preloaded/hardcoded products**. The app dynamically scans any pasted product URL, extracts titles, images, variations, and prices live, and tracks them over time.

---

## 2. Configured Infrastructure & Credentials
- **Supabase Cloud Backend:**
  - **Project URL:** `https://ljggqatmryzfvvveefiz.supabase.co`
  - **Publishable / Anon Key:** `<SUPABASE_PUBLISHABLE_ANON_KEY>` (configured in `index.html`)
  - **Service Role Key (GitHub Secret only):** `SUPABASE_SERVICE_ROLE_KEY` (stored in GitHub Secrets)
  - **PostgreSQL Schema:** `public.user_profiles` with Row-Level Security (RLS) isolating each `device_id` (`PR-XXXXXX`) and `device_secret`.
  - **Columns:** `device_id`, `device_secret`, `payload` (JSONB), `telegram_chat_id`, `fcm_token`, `updated_at`.
- **Telegram Bot:**
  - **Bot Username:** `@Priceradar_maorisr_bot`
  - **Deep Link:** `https://t.me/Priceradar_maorisr_bot?start=PR-XXXX`
  - **Bot Token (GitHub Secret only):** `TELEGRAM_BOT_TOKEN` (stored in GitHub Secrets)
- **Google FCM Push Notifications:**
  - **Android Package:** `com.priceradar.app`
  - **Firebase Configuration:** `google-services.json` (placed in repo root / `android/app/`).
  - **GitHub Secret:** `FIREBASE_SERVICE_ACCOUNT` (Private key JSON for cloud push from `scraper.py`).

---

## 3. Store Scraping & Anti-Bot Engines (Client App + Cloud Scraper)
1. **KSP (`ksp.co.il`):**
   - **Challenge:** Cloudflare Bot Fight Mode challenges datacenter IPs and basic proxies (`Just a moment...`).
   - **Solution:** Multi-route extraction engine without hardcoding:
     1. Native Android WebView bridge (`AndroidNativeScraper.scrapeUrl`).
     2. Public KSP mirror (`pricedrop.co.il/item/<uin>`) for clean metadata and prices.
     3. Google Translate crawler proxy (`ksp-co-il.translate.goog/mob/item/<uin>`).
     4. KSP Mobile SSR (`ksp.co.il/mob/item/<uin>`).
     5. Automatic extraction of **Regular Price** and **Eilat Price** as selectable product variations.
2. **Machsanei Hashmal (`payngo.co.il` / `eilat.payngo.co.il`):**
   - **Challenge:** Numbers and currency signs are wrapped in invisible Unicode directional formatting marks (`‏` RTL and `‎` LTR), e.g. `‏118 ‏₪`.
   - **Solution:** Automatic stripping of `[‎‏‪-‮]` before regex matching, extraction of `[data-price-type="finalPrice"]`, and simultaneous detection of regular and Eilat prices.
3. **Amazon (`amazon.com`, `amazon.co.uk`, `amazon.de`, etc.):**
   - **Challenge:** Multiple currencies (`$`, `USD`, `€`, `£`, `₪`) and long tracking query parameters.
   - **Solution:** Canonical URL normalization to `/dp/<ASIN>`, multi-currency regex, extraction of `.a-price .a-offscreen` and `#productTitle`.
   - **Special Feature — Free Shipping over $49 to Israel:**
     - Automatic detection of `FREE Shipping to Israel on qualifying orders over $49` / `משלוח חינם לישראל בקנייה מעל 49$`.
     - Toggle in product modal to receive instant push + Telegram notifications when an item joins the Free Shipping program, even if the price has not changed.
     - Visual badge `✈️ חינם מעל 49$` on product cards.
4. **AliExpress (`aliexpress.com`, `he.aliexpress.com`):**
   - Extraction of `US $` prices, `.product-price-current`, OpenGraph meta tags, and JavaScript `window.runParams`.
5. **Shopify & WooCommerce:**
   - Automatic detection of `/products/<slug>.json` and `data-product_variations` JSON for instant size/color/weight extraction.

---

## 4. Notifications & Background Monitoring
1. **Three-Layer Notification Delivery:**
   - **Layer 1: Google FCM (Cloud-to-Device):** When `scraper.py` on GitHub Actions detects a price drop or Amazon free shipping change, it calls Google FCM v1 API (`send_fcm_notification`) using `FIREBASE_SERVICE_ACCOUNT`. Google Play Services wakes the device even if the app is killed.
   - **Layer 2: Native Android System Notifications:** `MainActivity.java` creates a High-Importance `NotificationChannel` (`price_radar_alerts` with sound, vibration, heads-up banner). Also includes `sendNativeNotification` direct Java bridge and `BackgroundAlertReceiver` alarm monitor.
   - **Layer 3: 1-Click Telegram Bot:** Instant price drop alerts and daily summary digest at user-chosen time (e.g. 09:00).
2. **In-App Notification Test:**
   - Settings tab includes a green **"🔔 שלח בדיקה למכשיר"** button that fires an immediate test push to the notification shade.

---

## 5. Build System & Dynamic Versioning
- **Workflow:** `.github/workflows/build_apk.yml`
- **Builder Helper:** `finalize_build.py`
  - Automatically calculates dynamic version based on `github.run_number`: **increments by 0.1 on every build** (`v1.1.0`, `v1.2.0`, `v1.3.0`...).
  - Updates `versionCode` and `versionName` in `android/app/build.gradle`.
  - Injects `VERSION_NAME` and `BUILD_TIMESTAMP` into `www/index.html`.
  - Automatically links `google-services.json` into Gradle if present.
  - Adds `packagingOptions` to prevent duplicate `META-INF` file conflicts.
  - Generates `MainActivity.java` and publishes `PriceRadar.apk` to GitHub Releases.
- **Over-The-Air (OTA) Live Updates:**
  - `index.html` includes a background check against `raw.githubusercontent.com/maorisraelii/PriceRadar/main/index.html`.
  - Changes pushed to `index.html` in GitHub are fetched and hot-applied on app launch without needing to install a new APK.

---

## 6. Repository File Layout
```text
.
├── .github/
│   └── workflows/
│       ├── build_apk.yml       # Clean 65-line workflow for APK build & release
│       └── price_checker.yml   # 24/7 background scraper runner
├── capacitor.config.json       # Capacitor configuration
├── package.json                # Dependencies (@capacitor/core, android, local/push notifs)
├── finalize_build.py           # Native Android setup & versioning script
├── index.html                  # Main Liquid Glass Web App & Scanners
├── scraper.py                  # 24/7 Python cloud scraper with FCM & Telegram
├── supabase_schema.sql         # PostgreSQL database schema & RLS policies
├── requirements.txt            # Python dependencies (playwright, bs4, google-auth, requests)
├── icon-192.png, icon-512.png  # High-res liquid glass app icons
├── manifest.json, sw.js        # PWA manifest and service worker
├── data.json                   # Local data fallback
├── README.md                   # Project documentation
└── PROJECT_MEMORY.md           # This continuity memory file
```
