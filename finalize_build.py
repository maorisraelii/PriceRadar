import os
import re
import time
import shutil

def main():
    version_name = os.environ.get("VERSION_NAME", "1.1.0")
    version_code = os.environ.get("VERSION_CODE", "101")
    ts = int(time.time())

    print(f"=== Running finalize_build.py (Version: {version_name}, Code: {version_code}) ===")

    # 1. Update android/app/build.gradle version
    p_gradle = "android/app/build.gradle"
    if os.path.exists(p_gradle):
        with open(p_gradle, "r", encoding="utf-8") as f:
            c = f.read()
        c = re.sub(r"versionCode\s+\d+", f"versionCode {version_code}", c)
        c = re.sub(r'versionName\s+"[^"]+"', f'versionName "{version_name}"', c)
        if "packagingOptions" not in c:
            pkg_opts = """
    packagingOptions {
        resources {
            excludes += ['META-INF/DEPENDENCIES', 'META-INF/LICENSE', 'META-INF/LICENSE.txt', 'META-INF/license.txt', 'META-INF/NOTICE', 'META-INF/NOTICE.txt', 'META-INF/notice.txt', 'META-INF/ASL2.0', 'META-INF/*.kotlin_module']
        }
    }
"""
            c = c.replace("android {", "android {" + pkg_opts, 1)

        with open(p_gradle, "w", encoding="utf-8") as f:
            f.write(c)

        # Set Gradle JVM memory args to prevent OOM / hanging during mergeDebugJavaResource
        p_props = "android/gradle.properties"
        if os.path.exists(p_props):
            with open(p_props, "r", encoding="utf-8") as pf:
                props = pf.read()
            if "org.gradle.jvmargs" not in props:
                with open(p_props, "a", encoding="utf-8") as pf:
                    pf.write("\norg.gradle.jvmargs=-Xmx3072m -XX:MaxMetaspaceSize=512m\n")
                print("Configured gradle.properties with optimized memory limits")
        print(f"Configured {p_gradle} with versionCode={version_code}, versionName={version_name}")

    # 2. Update www/index.html version and timestamp
    p_html = "www/index.html"
    if os.path.exists(p_html):
        with open(p_html, "r", encoding="utf-8") as f:
            ch = f.read()
        ch = re.sub(r'window\.__APP_VERSION__\s*=\s*"[^"]+"', f'window.__APP_VERSION__ = "{version_name}"', ch)
        ch = re.sub(r'window\.__BUILD_TIMESTAMP__\s*=\s*\d+', f'window.__BUILD_TIMESTAMP__ = {ts}', ch)
        with open(p_html, "w", encoding="utf-8") as f:
            f.write(ch)
        print(f"Injected into {p_html}: version={version_name}, timestamp={ts}")

    # 3. Setup Google FCM if google-services.json exists
    if os.path.exists("google-services.json"):
        print("Found google-services.json! Linking Firebase FCM...")
        os.makedirs("android/app", exist_ok=True)
        shutil.copy("google-services.json", "android/app/google-services.json")

        top_gradle = "android/build.gradle"
        if os.path.exists(top_gradle):
            with open(top_gradle, "r", encoding="utf-8") as f:
                c_top = f.read()
            if "com.google.gms:google-services" not in c_top:
                c_top = c_top.replace("dependencies {", "dependencies {\n        classpath 'com.google.gms:google-services:4.4.2'")
                with open(top_gradle, "w", encoding="utf-8") as f:
                    f.write(c_top)
                print("Added Google Services classpath to top-level build.gradle")

        if os.path.exists(p_gradle):
            with open(p_gradle, "r", encoding="utf-8") as f:
                c_app = f.read()
            if "com.google.gms.google-services" not in c_app:
                c_app = c_app.rstrip() + "\napply plugin: 'com.google.gms.google-services'\n"
                with open(p_gradle, "w", encoding="utf-8") as f:
                    f.write(c_app)
                print("Applied google-services plugin in app build.gradle")
    else:
        print("No google-services.json found — building in native LocalNotifications mode.")

    # 4. Update AndroidManifest.xml with full background notification & alarm permissions
    p_manifest = "android/app/src/main/AndroidManifest.xml"
    if os.path.exists(p_manifest):
        with open(p_manifest, "r", encoding="utf-8") as f:
            m = f.read()
        perms = """
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />
    <uses-permission android:name="android.permission.USE_EXACT_ALARM" />
"""
        if "POST_NOTIFICATIONS" not in m:
            m = m.replace("</manifest>", perms + "</manifest>")
        rcvr = """
        <meta-data android:name="com.google.firebase.messaging.default_notification_channel_id" android:value="price_radar_alerts" />
        <service android:name=".MainActivity$TaskRemovedWatchdogService" android:enabled="true" android:exported="false" android:stopWithTask="false" />
        <receiver android:name=".MainActivity$BackgroundAlertReceiver" android:enabled="true" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.QUICKBOOT_POWERON" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
                <action android:name="com.priceradar.app.CHECK_ALERTS" />
            </intent-filter>
        </receiver>
"""
        if "BackgroundAlertReceiver" not in m:
            m = m.replace("</application>", rcvr + "</application>")
        with open(p_manifest, "w", encoding="utf-8") as f:
            f.write(m)
        print("Updated AndroidManifest.xml with permissions, FCM default channel, and boot/alarm receiver")

    # 5. Write MainActivity.java
    main_activity_dir = "android/app/src/main/java/com/priceradar/app"
    os.makedirs(main_activity_dir, exist_ok=True)
    main_activity_path = os.path.join(main_activity_dir, "MainActivity.java")

    java_code = """package com.priceradar.app;

import android.Manifest;
import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.BitmapFactory;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class MainActivity extends BridgeActivity {
    public static final String CHANNEL_ID = "price_radar_alerts";
    private WebView scraperWebView;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createNotificationChannel(this);
        requestNotificationPermissionIfNeeded();
        try {
            WebView mainWv = this.getBridge().getWebView();
            WebSettings ws = mainWv.getSettings();
            ws.setJavaScriptEnabled(true);
            ws.setDomStorageEnabled(true);
            mainWv.addJavascriptInterface(new NativeScraperBridge(mainWv, this), "AndroidNativeScraper");
        } catch (Exception e) {
            e.printStackTrace();
        }
        scheduleNextBackgroundCheck(this, 15);
        try {
            startService(new Intent(this, TaskRemovedWatchdogService.class));
        } catch (Exception ignored) {}
    }

    public static class TaskRemovedWatchdogService extends Service {
        @Override
        public int onStartCommand(Intent intent, int flags, int startId) {
            return START_STICKY;
        }

        @Override
        public IBinder onBind(Intent intent) {
            return null;
        }

        @Override
        public void onTaskRemoved(Intent rootIntent) {
            try {
                SharedPreferences sp = getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                int mins = sp.getInt("checkIntervalMinutes", 15);
                scheduleNextBackgroundCheck(getApplicationContext(), mins);
                // Also schedule a quick 60-second wakeup check after swipe-away from multitasking
                AlarmManager am = (AlarmManager) getSystemService(Context.ALARM_SERVICE);
                if (am != null) {
                    Intent i = new Intent(getApplicationContext(), BackgroundAlertReceiver.class);
                    i.setAction("com.priceradar.app.CHECK_ALERTS");
                    PendingIntent pi = PendingIntent.getBroadcast(
                        getApplicationContext(),
                        102,
                        i,
                        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
                    );
                    long triggerSoon = System.currentTimeMillis() + 60000L;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && am.canScheduleExactAlarms()) {
                        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerSoon, pi);
                    } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerSoon, pi);
                    } else {
                        am.set(AlarmManager.RTC_WAKEUP, triggerSoon, pi);
                    }
                }
            } catch (Exception ignored) {}
            super.onTaskRemoved(rootIntent);
        }
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1001);
            }
        }
    }

    public static void createNotificationChannel(Context ctx) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "התראות מחיר PriceRadar",
                NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("התראות מיידיות על ירידות מחיר ומשלוח חינם");
            channel.enableVibration(true);
            channel.enableLights(true);
            channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            NotificationManager nm = ctx.getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    public static void showSystemNotification(Context context, String title, String message, int notifId) {
        try {
            createNotificationChannel(context);
            Intent tapIntent = new Intent(context, MainActivity.class);
            tapIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            PendingIntent pi = PendingIntent.getActivity(
                context,
                notifId,
                tapIntent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
            );

            int smallIconId = context.getApplicationInfo().icon;
            if (smallIconId == 0) {
                smallIconId = android.R.drawable.ic_dialog_info;
            }

            NotificationCompat.Builder b = new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(smallIconId)
                .setLargeIcon(BitmapFactory.decodeResource(context.getResources(), context.getApplicationInfo().icon))
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_PROMO)
                .setDefaults(NotificationCompat.DEFAULT_ALL)
                .setAutoCancel(true)
                .setContentIntent(pi);

            NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.notify(notifId, b.build());
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void scheduleNextBackgroundCheck(Context context, int intervalMinutes) {
        try {
            int mins = Math.max(5, intervalMinutes);
            long triggerAt = System.currentTimeMillis() + (mins * 60L * 1000L);
            AlarmManager am = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
            if (am == null) return;

            Intent i = new Intent(context, BackgroundAlertReceiver.class);
            i.setAction("com.priceradar.app.CHECK_ALERTS");
            PendingIntent pi = PendingIntent.getBroadcast(
                context,
                101,
                i,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
            );

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && am.canScheduleExactAlarms()) {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi);
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi);
            } else {
                am.setExact(AlarmManager.RTC_WAKEUP, triggerAt, pi);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static class BackgroundAlertReceiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context context, Intent intent) {
            final PendingResult pendingResult = goAsync();
            new Thread(() -> {
                PowerManager.WakeLock wl = null;
                try {
                    PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
                    if (pm != null) {
                        wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PriceRadar::BgCheckWakeLock");
                        wl.acquire(45000L);
                    }
                    SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                    int intervalMins = sp.getInt("checkIntervalMinutes", 15);
                    scheduleNextBackgroundCheck(context, intervalMins);

                    String deviceId = sp.getString("deviceId", "");
                    String deviceSecret = sp.getString("deviceSecret", "");
                    if (deviceId == null || deviceId.isEmpty()) return;

                    String sbUrl = "https://ljggqatmryzfvvveefiz.supabase.co/rest/v1/user_profiles?device_id=eq." + deviceId + "&select=payload";
                    String sbKey = "sb_publishable_BEFtsujmDeFgYfUicT0aTA_e5H2f6bx";
                    URL u = new URL(sbUrl);
                    HttpURLConnection conn = (HttpURLConnection) u.openConnection();
                    conn.setRequestMethod("GET");
                    conn.setRequestProperty("apikey", sbKey);
                    conn.setRequestProperty("Authorization", "Bearer " + sbKey);
                    conn.setRequestProperty("x-device-id", deviceId);
                    if (deviceSecret != null && !deviceSecret.isEmpty()) {
                        conn.setRequestProperty("x-device-secret", deviceSecret);
                    }
                    conn.setConnectTimeout(10000);
                    conn.setReadTimeout(10000);

                    if (conn.getResponseCode() == 200) {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), "UTF-8"));
                        StringBuilder sb = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) sb.append(line);
                        reader.close();

                        JSONArray arr = new JSONArray(sb.toString());
                        if (arr.length() > 0) {
                            JSONObject row = arr.getJSONObject(0);
                            JSONObject payload = row.optJSONObject("payload");
                            if (payload != null) {
                                // 1. Check if cloud scraper added a new alert
                                JSONArray alerts = payload.optJSONArray("alerts");
                                if (alerts != null && alerts.length() > 0) {
                                    JSONObject latest = alerts.getJSONObject(0);
                                    String alertId = latest.optString("id");
                                    String lastNotified = sp.getString("lastAlertId", "");

                                    if (!alertId.isEmpty() && !alertId.equals(lastNotified)) {
                                        sp.edit().putString("lastAlertId", alertId).apply();
                                        String title = latest.optString("title", "🔥 המחיר ירד!");
                                        String msg = latest.optString("messagePlain", "נמצאה ירידת מחיר באחד המוצרים שלך");
                                        showSystemNotification(context, title, msg, Math.abs(alertId.hashCode()));
                                    }
                                }

                                // 2. Also perform lightweight background check on tracked products directly from device
                                JSONArray products = payload.optJSONArray("products");
                                boolean updated = false;
                                if (products != null && products.length() > 0 && deviceSecret != null && !deviceSecret.isEmpty()) {
                                    updated = checkProductsInBackground(context, sp, products, alerts != null ? alerts : new JSONArray(), payload);
                                }

                                // 3. Check if Daily Summary Report is due while app is closed
                                JSONObject settings = payload.optJSONObject("settings");
                                if (settings != null && products != null && products.length() > 0) {
                                    String dailyTime = settings.optString("dailyTime", "09:00");
                                    java.text.SimpleDateFormat sdfDate = new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US);
                                    java.text.SimpleDateFormat sdfTime = new java.text.SimpleDateFormat("HH:mm", java.util.Locale.US);
                                    java.util.Date nowDate = new java.util.Date();
                                    String todayStr = sdfDate.format(nowDate);
                                    String nowHm = sdfTime.format(nowDate);
                                    String lastDailySent = settings.optString("lastDailySentDate", "");
                                    String spLastDaily = sp.getString("lastDailySentDate", "");
                                    if (nowHm.compareTo(dailyTime) >= 0 && !todayStr.equals(lastDailySent) && !todayStr.equals(spLastDaily)) {
                                        sp.edit().putString("lastDailySentDate", todayStr).apply();
                                        settings.put("lastDailySentDate", todayStr);
                                        int dropsCount = 0;
                                        for (int p = 0; p < products.length(); p++) {
                                            JSONObject pr = products.optJSONObject(p);
                                            if (pr != null && pr.optDouble("currentPrice", 0) < pr.optDouble("initialPrice", 0)) {
                                                dropsCount++;
                                            }
                                        }
                                        String dTitle = "📊 דו\\"ח מחירים יומי (" + products.length() + " מוצרים)";
                                        String dMsg = "סיכום יומי: " + dropsCount + " מוצרים בירידת מחיר מתוך " + products.length() + " במעקב.";
                                        showSystemNotification(context, dTitle, dMsg, 99001);
                                        updated = true;
                                    }
                                }

                                if (updated && deviceSecret != null && !deviceSecret.isEmpty()) {
                                    pushUpdatedPayloadToSupabase(deviceId, deviceSecret, payload);
                                }
                            }
                        }
                    }
                } catch (Exception ignored) {
                } finally {
                    try {
                        if (wl != null && wl.isHeld()) wl.release();
                    } catch (Exception ignored) {}
                    try {
                        pendingResult.finish();
                    } catch (Exception ignored) {}
                }
            }).start();
        }

        private boolean checkProductsInBackground(Context ctx, SharedPreferences sp, JSONArray products, JSONArray alerts, JSONObject payload) {
            boolean anyChange = false;
            int count = Math.min(products.length(), 6);
            for (int i = 0; i < count; i++) {
                try {
                    JSONObject prod = products.optJSONObject(i);
                    if (prod == null) continue;
                    String rawUrl = prod.optString("url", "");
                    double oldPrice = prod.optDouble("currentPrice", 0);
                    if (rawUrl.isEmpty() || oldPrice <= 0) continue;

                    String targetUrl = rawUrl;
                    Matcher kspM = Pattern.compile("ksp\\\\.co\\\\.il/(?:web/|mob/)?item/(\\\\d+)").matcher(rawUrl);
                    if (kspM.find()) {
                        targetUrl = "https://pricedrop.co.il/item/" + kspM.group(1);
                    }

                    URL u = new URL(targetUrl);
                    HttpURLConnection c = (HttpURLConnection) u.openConnection();
                    c.setRequestMethod("GET");
                    c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126.0.0.0 Mobile Safari/537.36");
                    c.setConnectTimeout(8000);
                    c.setReadTimeout(8000);
                    if (c.getResponseCode() != 200) continue;

                    BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
                    StringBuilder htmlSb = new StringBuilder();
                    String ln;
                    while ((ln = r.readLine()) != null && htmlSb.length() < 250000) {
                        htmlSb.append(ln).append("\\n");
                    }
                    r.close();
                    String html = htmlSb.toString().replaceAll("[\\u200E\\u200F\\u202A-\\u202E]", "");
                    if (html.contains("Just a moment...") || html.length() < 200) continue;

                    Double detected = extractQuickPrice(html, prod.optString("SelectedVariant", ""));
                    if (detected != null && detected > 1 && detected < oldPrice) {
                        double saved = Math.round((oldPrice - detected) * 100.0) / 100.0;
                        prod.put("currentPrice", detected);
                        double lowest = prod.optDouble("lowestPrice", oldPrice);
                        if (detected < lowest) prod.put("lowestPrice", detected);

                        String alertId = "bg_drop_" + System.currentTimeMillis();
                        String title = "🔥 המחיר ירד! " + prod.optString("title", "מוצר במעקב");
                        String msg = "ירד מ-" + oldPrice + " ₪ ל-" + detected + " ₪ (חיסכון של " + saved + " ₪)!";

                        JSONObject newAlert = new JSONObject();
                        newAlert.put("id", alertId);
                        newAlert.put("type", "drop");
                        newAlert.put("title", title);
                        newAlert.put("messagePlain", msg);
                        newAlert.put("url", rawUrl);

                        JSONArray newAlerts = new JSONArray();
                        newAlerts.put(newAlert);
                        for (int a = 0; a < Math.min(alerts.length(), 99); a++) {
                            newAlerts.put(alerts.get(a));
                        }
                        payload.put("alerts", newAlerts);
                        sp.edit().putString("lastAlertId", alertId).apply();
                        showSystemNotification(ctx, title, msg, Math.abs(alertId.hashCode()));
                        anyChange = true;
                    }
                } catch (Exception ignored) {}
            }
            return anyChange;
        }

        private Double extractQuickPrice(String html, String variant) {
            try {
                Matcher mPd = Pattern.compile("₪\\\\s*(\\\\d{1,3}(?:,\\\\d{3})*(?:\\\\.\\\\d{1,2})?)\\\\s*מחיר\\\\s+(?:נוכחי|אחרון)").matcher(html);
                if (mPd.find()) {
                    double v = Double.parseDouble(mPd.group(1).replace(",", ""));
                    return variant.contains("אילת") ? (double) Math.round(v / 1.18) : v;
                }
                Matcher mMeta = Pattern.compile("property=[\\"'](?:product|og):price:amount[\\"'][^>]*content=[\\"']([0-9.]+)[\\"']").matcher(html);
                if (mMeta.find()) {
                    return Double.parseDouble(mMeta.group(1));
                }
                Matcher mSchema = Pattern.compile("\\"price\\"\\\\s*:\\\\s*[\\"']?(\\\\d+(?:\\\\.\\\\d{1,2})?)[\\"']?").matcher(html);
                if (mSchema.find()) {
                    double v = Double.parseDouble(mSchema.group(1));
                    if (v > 1) return v;
                }
            } catch (Exception ignored) {}
            return null;
        }

        private void pushUpdatedPayloadToSupabase(String deviceId, String deviceSecret, JSONObject payload) {
            try {
                String sbUrl = "https://ljggqatmryzfvvveefiz.supabase.co/rest/v1/user_profiles?device_id=eq." + deviceId;
                String sbKey = "sb_publishable_BEFtsujmDeFgYfUicT0aTA_e5H2f6bx";
                URL u = new URL(sbUrl);
                HttpURLConnection conn = (HttpURLConnection) u.openConnection();
                conn.setRequestMethod("PATCH");
                conn.setRequestProperty("apikey", sbKey);
                conn.setRequestProperty("Authorization", "Bearer " + sbKey);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("x-device-id", deviceId);
                conn.setRequestProperty("x-device-secret", deviceSecret);
                conn.setDoOutput(true);
                JSONObject body = new JSONObject();
                body.put("payload", payload);
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(body.toString().getBytes("UTF-8"));
                }
                conn.getResponseCode();
            } catch (Exception ignored) {}
        }
    }

    public class NativeScraperBridge {
        private final WebView hostWebView;
        private final Context context;
        private final Handler mainHandler = new Handler(Looper.getMainLooper());

        public NativeScraperBridge(WebView host, Context ctx) {
            this.hostWebView = host;
            this.context = ctx;
        }

        @JavascriptInterface
        public void saveDeviceId(final String deviceId) {
            saveDeviceCredentials(deviceId, "", 15);
        }

        @JavascriptInterface
        public void saveDeviceCredentials(final String deviceId, final String deviceSecret, final int intervalMinutes) {
            if (deviceId == null || deviceId.isEmpty()) return;
            SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
            SharedPreferences.Editor ed = sp.edit();
            ed.putString("deviceId", deviceId);
            if (deviceSecret != null && !deviceSecret.isEmpty()) {
                ed.putString("deviceSecret", deviceSecret);
            }
            if (intervalMinutes > 0) {
                ed.putInt("checkIntervalMinutes", intervalMinutes);
            }
            ed.apply();

            scheduleNextBackgroundCheck(context, intervalMinutes > 0 ? intervalMinutes : 15);
            try {
                Intent i = new Intent(context, BackgroundAlertReceiver.class);
                i.setAction("com.priceradar.app.CHECK_ALERTS");
                context.sendBroadcast(i);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        @JavascriptInterface
        public void sendNativeNotification(final String title, final String message) {
            mainHandler.post(() -> {
                requestNotificationPermissionIfNeeded();
                int id = (int) (System.currentTimeMillis() & 0x7fffffff);
                showSystemNotification(context, title, message, id);
            });
        }

        @JavascriptInterface
        public void scrapeUrl(final String targetUrl, final String callbackId) {
            mainHandler.post(() -> {
                try {
                    if (scraperWebView != null) {
                        scraperWebView.destroy();
                    }
                    scraperWebView = new WebView(MainActivity.this);
                    WebSettings s = scraperWebView.getSettings();
                    s.setJavaScriptEnabled(true);
                    s.setDomStorageEnabled(true);
                    s.setUserAgentString("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36");
                    scraperWebView.setWebViewClient(new WebViewClient() {
                        private boolean delivered = false;
                        @Override
                        public void onPageFinished(WebView view, String url) {
                            mainHandler.postDelayed(() -> {
                                if (delivered) return;
                                view.evaluateJavascript("(function(){ return document.documentElement ? document.documentElement.outerHTML : ''; })();", value -> {
                                    if (delivered) return;
                                    if (value != null && value.contains("Just a moment")) {
                                        mainHandler.postDelayed(() -> {
                                            if (delivered) return;
                                            delivered = true;
                                            view.evaluateJavascript("(function(){ return document.documentElement ? document.documentElement.outerHTML : ''; })();", val2 -> {
                                                sendResult(callbackId, val2);
                                            });
                                        }, 2500);
                                    } else {
                                        delivered = true;
                                        sendResult(callbackId, value);
                                    }
                                });
                            }, 1600);
                        }
                    });
                    scraperWebView.loadUrl(targetUrl);
                } catch (Exception e) {
                    sendResult(callbackId, "\\"\\"");
                }
            });
        }

        private void sendResult(final String callbackId, final String rawJsString) {
            mainHandler.post(() -> {
                try {
                    String safeId = JSONObject.quote(callbackId);
                    String payload = (rawJsString == null || rawJsString.equals("null")) ? "\\"\\"" : rawJsString;
                    hostWebView.evaluateJavascript("window.__resolveNativeScrape && window.__resolveNativeScrape(" + safeId + ", " + payload + ");", null);
                } catch (Exception ignored) {}
            });
        }
    }
}
"""
    with open(main_activity_path, "w", encoding="utf-8") as f:
        f.write(java_code)
    print(f"Generated clean {main_activity_path}")

    # 6. Replace ALL launcher icons (including Adaptive Icons foreground & removing default Capacitor vector override)
    anydpi_dir = "android/app/src/main/res/mipmap-anydpi-v26"
    if os.path.exists(anydpi_dir):
        shutil.rmtree(anydpi_dir, ignore_errors=True)
        print(f"Removed {anydpi_dir} so Android uses the custom PNG launcher icons directly without Capacitor's default adaptive icon override")

    # Also update ic_launcher_background color to match #090716 dark aurora theme if referenced anywhere
    bg_xml_path = "android/app/src/main/res/values/ic_launcher_background.xml"
    if os.path.exists(bg_xml_path):
        with open(bg_xml_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#090716</color>\n</resources>\n')

    for density in ["hdpi", "mdpi", "xhdpi", "xxhdpi", "xxxhdpi"]:
        folder = f"android/app/src/main/res/mipmap-{density}"
        os.makedirs(folder, exist_ok=True)
        if os.path.exists("icon-512.png"):
            shutil.copy("icon-512.png", f"{folder}/ic_launcher.png")
            shutil.copy("icon-512.png", f"{folder}/ic_launcher_round.png")
            shutil.copy("icon-512.png", f"{folder}/ic_launcher_foreground.png")
    print("Copied icon-512.png to all mipmap-* folders (ic_launcher, ic_launcher_round, ic_launcher_foreground)!")

if __name__ == "__main__":
    main()
