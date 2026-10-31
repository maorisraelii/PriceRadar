<div align="center">

# 🛍️ PriceRadar IL

### Autonomous Universal E-Commerce Price Tracker & Android App

<p align="center">
<strong>מערכת מעקב מחירים חכמה ואוטונומית לכל אתרי הסחר בישראל ובעולם • זיהוי וריאציות מוצר (מידות / משקלים) • ניטור ענן 24/7 ללא צורך בשרת • התראות ירידת מחיר ודו"ח יומי ישירות לטלגרם</strong>
</p>

<p align="center">
<a href="https://android.com"><img src="https://img.shields.io/badge/Platform-Android%20%7C%20PWA-3DDC84?style=for-the-badge&logo=android&logoColor=white" alt="Platform: Android" /></a>
<a href="https://github.com/actions"><img src="https://img.shields.io/badge/CI%2FCD-GitHub%20Actions%2024%2F7-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" /></a>
<a href="https://supabase.com"><img src="https://img.shields.io/badge/Backend-Supabase%20PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase" /></a>
<a href="https://playwright.dev"><img src="https://img.shields.io/badge/Scraper-Playwright%20Chromium-45ba4b?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright" /></a>
<a href="https://telegram.org"><img src="https://img.shields.io/badge/Alerts-Telegram%20Bot%20API-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" /></a>
<a href="https://tailwindcss.com"><img src="https://img.shields.io/badge/UI-Liquid%20Glassmorphism-ec4899?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS" /></a>
</p>

<p align="center">
<a href="#-למשתמשי-האפליקציה-הורדת-apk-והתקנה-מהירה"><b>📥 הורדת APK למכשיר</b></a> •
<a href="#-תאימות-מנוע-הסריקה-חנויות-נתמכות"><b>🛒 חנויות נתמכות</b></a> •
<a href="#-ארכיטקטורת-מערכת"><b>🏗️ ארכיטקטורה</b></a> •
<a href="#-מדריך-הקמה-עצמאית-self-hosting"><b>⚙️ מדריך הקמה (Self-Hosting)</b></a> •
<a href="#-פרטיות-ואבטחה-rls--zero-pii"><b>🛡️ פרטיות ואבטחה</b></a>
</p>

</div>

## 📱 למשתמשי האפליקציה: הורדת APK והתקנה מהירה

> **אין צורך בהגדרות טכניות!** כל מי שמוריד את האפליקציה מקבל חוויית שימוש מיידית: מזהה מכשיר אנונימי מוקצה אוטומטית, והנתונים מסונכרנים ישירות לענן.

1. **הורדת קובץ ה-APK:** עבור ללשונית **\[suspicious link removed\]** במאגר -> בחר בתהליך **Build Android APK** -> לחץ על הריצה האחרונה והורד את **`PriceRadar-Debug-APK`**.

2. **התקנה בטלפון:** פתח את קובץ ה-`.apk` במכשיר האנדרואיד שלך ואשר התקנה ממקור זה.

3. **התחלת מעקב:** הדבק קישור לכל מוצר שתרצה, בחר מידה או משקל, ולחץ על **"חבר את הטלגרם שלי בלחיצה אחת"** כדי לקבל עדכונים שוטפים.

## ✨ תכונות ליבה (Key Features)

* **🌐 מנוע סריקה אוניברסלי רב-שכבתי (Multi-Layer Scraping):** שילוב מתקדם של חילוץ נתוני `Schema.org/Product` (JSON-LD), מטא-תגיות OpenGraph, וסריקה מלאה באמצעות דפדפן Chromium אמיתי ([Playwright](https://playwright.dev)) לעקיפת מנגנוני הגנה נגד בוטים (Cloudflare, PerimeterX).

* **🎯 זיהוי וריאציות עמוק (Deep Variant Extraction):** חילוץ אוטומטי של תתי-דגמים, משקלים (לדוגמה 2 ק"ג מול 4 ק"ג באותה כתובת ב-WooCommerce) ומידות הנעלה (כגון מידה 41 ב-Shopify דרך פרמטר `variant=`), ומעקב ממוקד לפי בחירת המשתמש.

* **☁️ ניטור ענן אוטונומי 24/7 ללא תחזוקת שרת:** משימת [GitHub Actions](https://docs.github.com/actions) מתעוררת בכל שעה עגולה לפי לוח זמנים מוגדר ([Cron Trigger](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions)), מבצעת בדיקה שקטה ברקע, ושומרת את היסטוריית המחירים המעודכנת.

* **⚡ התראות ירידת מחיר מיידיות + דו"ח יומי מרוכז:** שליחת התראת Push מידית ברגע שמחיר של פריט צונח (כולל חישוב אחוזי חיסכון ולינק ישיר לרכישה), לצד דו"ח סטטוס יומי מרוכז בשעה קבועה (ברירת מחדל: 09:00).

* **🎨 ממשק משתמש אולטרה-מודרני (Liquid Glassmorphism):** עיצוב מותאם מובייל עם אפקטי זכוכית ושכבות Aurora, גרפי מגמת מחירים מובנים ([Chart.js](https://www.chartjs.org/)), תמונות מוצר וסמלי חנויות מזוהים.

* **🛡️ אבטחה ופרטיות מלאה (Row-Level Security & Zero-PII):** כל מכשיר מקבל טוקן אישי מבודד ברמת מסד הנתונים ([Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)). אין צורך בשם, סיסמה או דוא"ל.

## 🛒 תאימות מנוע הסריקה (חנויות נתמכות)

המערכת תוכננה לעבוד באופן גנרי על כל אתר סחר מודרני, ונבדקה במיוחד מול האתרים המובילים:

| חנות לדוגמה | פלטפורמה / מנגנון | תמיכה בווריאציות (מידות / משקלים) | מנגנון עקיפת חסימות | סטטוס | 
| ----- | ----- | ----- | ----- | ----- | 
| **טרקלין חשמל** | Custom Engine | זיהוי מוצר ראשי וסינון מוצרים נלווים בדף | דפדפן Headless Playwright | 🟢 נתמך מלא | 
| **הארנב שלי (MyRabbit)** | WooCommerce | זיהוי מערכי `data-product_variations` (2 ק"ג / 4 ק"ג) | פענוח מובנה של JSON בדף | 🟢 נתמך מלא | 
| **פוט לוקר (Foot Locker)** | Shopify Israel | זיהוי פרמטר `variant=` ובדיקת זמינות מלאי למידה | Shopify Product JSON API | 🟢 נתמך מלא | 
| **KSP / אייבורי** | Single Page App | שליפת מחיר ראשי, מק"ט ואחריות | דפדפן וירטואלי + Schema.org | 🟢 נתמך מלא | 
| **Amazon / AliExpress** | Global Marketplace | המרת מטבעות אוטומטית ובדיקת מלאי | OpenGraph & DOM Fallback | 🟢 נתמך מלא | 

## 🏗️ ארכיטקטורת מערכת

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      📱 Client Layer (Mobile App / PWA)                      │
│      Liquid Glass UI • IndexedDB Offline Cache • Web Audio • Chart.js       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │  REST API (x-device-id / x-device-secret)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  🛡️ Secure Database Layer (Supabase Postgres)                │
│       Row-Level Security (RLS) Policies • Isolated Device Records           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │  Service Role Authentication
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  ☁️ Automation Engine (GitHub Actions 24/7)                 │
│                                                                             │
│   ┌────────────────────────┐  ┌────────────────────────┐  ┌──────────────┐  │
│   │ Playwright (Chromium)  │  │ Universal Parser       │  │ Time-Engine  │  │
│   │ Headless Browser Farm  │─▶│ Schema / DOM / Shopify │─▶│ Hourly Cron  │  │
│   └────────────────────────┘  └────────────────────────┘  └──────┬───────┘  │
└──────────────────────────────────────────────────────────────────┼──────────┘
                                                                   │
                                                                   ▼
                                              ┌───────────────────────────────┐
                                              │    ✈️ Telegram Bot Alerts     │
                                              │  Instant Drops • Daily Digest │
                                              └───────────────────────────────┘

```

## ⚙️ מדריך הקמה עצמאית (Self-Hosting)

למפתחים המעוניינים להריץ עותק פרטי ועצמאי של הפרויקט:

### 1. הכנת מסד הנתונים ב-[Supabase](https://supabase.com)

1. פתח פרויקט חינמי ב-[Supabase](https://supabase.com).

2. נווט ל-**SQL Editor**, הדבק את תוכנו של הקובץ [supabase_schema.sql](https://www.google.com/search?q=./supabase_schema.sql) והרץ אותו (מפעיל את טבלת הפרופילים ומדיניות ה-RLS).

3. תחת **Project Settings -> API Keys**, העתק את ה-**Project URL**, את ה-**Publishable Key** ואת ה-**Secret Key**.

### 2. יצירת בוט בטלגרם

1. פנה ל-**`@BotFather`** בטלגרם והקלד `/newbot`.

2. הגדר שם ותגית משתמש לבוט (לדוגמה `PriceRadarBot`), ושמור את ה-**Bot Token** שסופק לך.

### 3. הגדרת כספת המפתחות ב-GitHub (Repository Secrets)

במאגר ה-GitHub שלך, עבור אל:
**Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret**

והגדר את שלושת המפתחות הבאים:

| שם המפתח (Secret Name) | תיאור | 
| ----- | ----- | 
| `SUPABASE_URL` | כתובת ה-API של הפרויקט ב-Supabase (`https://xxxx.supabase.co`) | 
| `SUPABASE_SERVICE_ROLE_KEY` | מפתח ה-Secret המאובטח מ-Supabase (לצורך גישת שרת מורשית) | 
| `TELEGRAM_BOT_TOKEN` | הטוקן שסופק על-ידי BotFather | 

## 📦 קימפול קובץ APK ישירות ב-GitHub Actions

המאגר כולל תהליך CI/CD מובנה המקמפל את קוד האפליקציה לסביבת אנדרואיד באמצעות [Capacitor](https://capacitorjs.com/) ו-Gradle:

1. היכנס ללשונית **Actions** במאגר.

2. בחר בסרגל הצד ב-**Build Android APK**.

3. לחץ על **Run workflow** ובחר בענף `main`.

4. בסיום הריצה (כ-2 דקות), היכנס לסיכום הריצה והורד את ה-Artifact תחת השם **`PriceRadar-Debug-APK`**.

## 🛡️ פרטיות ואבטחה (RLS & Zero-PII)

* **הפרדת משתמשים ברמת מסד הנתונים (RLS):** מסד הנתונים משתמש במדיניות [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security) המאמתת את צמד הכותרות `x-device-id` ו-`x-device-secret` בכל פנייה. מכשיר אחד אינו מסוגל לקרוא או לעדכן נתונים של מכשיר אחר.

* **אפס מידע מזהה (Zero-PII):** אין שימוש במספרי טלפון, שמות או כתובות אימייל. החיבור לטלגרם מתבצע דרך Deep-Link אנונימי (`/start PR-XXXX`).

* **סודיות מפתחות שרת:** מפתח הניהול (`Secret Key`) מנוהל אך ורק בכספת של GitHub Secrets ואינו נחשף לעולם בקוד ה-Frontend או ב-APK.

## 📄 רישיון (License)

פרויקט זה מופץ תחת רישיון **MIT Open Source License**. למידע נוסף עיין בקובץ [LICENSE](https://www.google.com/search?q=./LICENSE).