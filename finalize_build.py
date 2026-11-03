import os
import re
import time
import shutil

def main():
    version_name = os.environ.get("VERSION_NAME", "")
    version_code = os.environ.get("VERSION_CODE", "201")
    if not version_name and os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            m_ver = re.search(r'window\.__APP_VERSION__\s*=\s*"([^"]+)"', f.read())
            if m_ver:
                version_name = m_ver.group(1)
    if not version_name:
        version_name = "2.9.0"

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
    signingConfigs {
        debug {
            if (file("../../priceradar-signing.keystore").exists()) {
                storeFile file("../../priceradar-signing.keystore")
                storePassword "android"
                keyAlias "androiddebugkey"
                keyPassword "android"
            }
        }
    }
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

    # 2. Update www/index.html version while preserving __BUILD_TIMESTAMP__ from index.html
    p_html = "www/index.html"
    if os.path.exists(p_html):
        with open(p_html, "r", encoding="utf-8") as f:
            ch = f.read()
        ch = re.sub(r'window\.__APP_VERSION__\s*=\s*"[^"]+"', f'window.__APP_VERSION__ = "{version_name}"', ch)
        with open(p_html, "w", encoding="utf-8") as f:
            f.write(ch)
        print(f"Injected into {p_html}: version={version_name}")

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
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
"""
        if "POST_NOTIFICATIONS" not in m:
            m = m.replace("</manifest>", perms + "</manifest>")
        rcvr = """
        <meta-data android:name="com.google.firebase.messaging.default_notification_channel_id" android:value="price_radar_alerts" />
        <service android:name=".MainActivity$TaskRemovedWatchdogService" android:enabled="true" android:exported="false" android:stopWithTask="false" android:foregroundServiceType="dataSync" />
        <receiver android:name=".MainActivity$BackgroundAlertReceiver" android:enabled="true" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.QUICKBOOT_POWERON" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
                <action android:name="com.priceradar.app.CHECK_ALERTS" />
                <action android:name="com.priceradar.app.DELAYED_TEST_NOTIFICATION" />
            </intent-filter>
        </receiver>
"""
        if "BackgroundAlertReceiver" not in m:
            m = m.replace("</application>", rcvr + "</application>")
        share_filter = """
            <intent-filter>
                <action android:name="android.intent.action.SEND" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:mimeType="text/plain" />
            </intent-filter>
            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="priceradar" />
            </intent-filter>
"""
        if "android.intent.action.SEND" not in m:
            m = m.replace("</activity>", share_filter + "        </activity>", 1)
        with open(p_manifest, "w", encoding="utf-8") as f:
            f.write(m)
        print("Updated AndroidManifest.xml with permissions, Share Target intent-filter, FCM default channel, and boot/alarm receiver")

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
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
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
    public static final String MONITOR_CHANNEL_ID = "price_radar_monitor_silent";
    private WebView scraperWebView;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createNotificationChannel(this);
        requestNotificationPermissionIfNeeded();
        requestBatteryExemptionIfNeeded();
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
        scheduleNextDailyReportAlarm(this);
        // Dismiss any lingering foreground monitor notification from older versions
        try {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.cancel(7001);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    nm.deleteNotificationChannel(MONITOR_CHANNEL_ID);
                }
            }
        } catch (Exception ignored) {}
        handleIncomingShareIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingShareIntent(intent);
    }

    private void handleIncomingShareIntent(Intent intent) {
        if (intent == null) return;
        try {
            String action = intent.getAction();
            String type = intent.getType();
            String candidateText = null;
            if (Intent.ACTION_SEND.equals(action) && type != null && type.startsWith("text/")) {
                String sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
                String sharedSubj = intent.getStringExtra(Intent.EXTRA_SUBJECT);
                candidateText = (sharedText != null ? sharedText : "") + " " + (sharedSubj != null ? sharedSubj : "");
            } else if (Intent.ACTION_VIEW.equals(action) && intent.getDataString() != null) {
                candidateText = intent.getDataString();
            }
            if (candidateText != null && candidateText.contains("http")) {
                Matcher m = Pattern.compile("(https?://[^\\\\s\\\"'<>]+)").matcher(candidateText);
                if (m.find()) {
                    final String extractedUrl = m.group(1).replaceAll("[.,;!?\\\\)\\\\]]+$", "");
                    SharedPreferences sp = getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                    sp.edit().putString("pendingSharedUrl", extractedUrl).commit();
                    new Handler(Looper.getMainLooper()).postDelayed(() -> {
                        try {
                            if (getBridge() != null && getBridge().getWebView() != null) {
                                String safeUrl = JSONObject.quote(extractedUrl);
                                getBridge().getWebView().evaluateJavascript(
                                    "if (window.__handleIncomingSharedUrl) { window.__handleIncomingSharedUrl(" + safeUrl + "); }",
                                    null
                                );
                            }
                        } catch (Exception ignored) {}
                    }, 900);
                }
            }
        } catch (Exception ignored) {}
    }

    public static void startRadarMonitorService(Context ctx) {
        // Pure silent background alarm schedule — NO foreground service notification!
        try {
            scheduleNextBackgroundCheck(ctx, 15);
            scheduleNextDailyReportAlarm(ctx);
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.cancel(7001);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    nm.deleteNotificationChannel(MONITOR_CHANNEL_ID);
                }
            }
        } catch (Exception ignored) {}
    }

    private void requestBatteryExemptionIfNeeded() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
                if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
                    Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                }
            }
        } catch (Exception ignored) {}
    }

    public static class TaskRemovedWatchdogService extends Service {
        @Override
        public void onCreate() {
            super.onCreate();
        }

        @Override
        public int onStartCommand(Intent intent, int flags, int startId) {
            return START_NOT_STICKY;
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
            } catch (Exception ignored) {}
            stopSelf();
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
            NotificationManager nm = ctx.getSystemService(NotificationManager.class);
            if (nm != null) {
                NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "התראות מחיר PriceRadar",
                    NotificationManager.IMPORTANCE_HIGH
                );
                channel.setDescription("התראות מיידיות על ירידות מחיר ומשלוח חינם");
                channel.enableVibration(true);
                channel.enableLights(true);
                channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
                nm.createNotificationChannel(channel);

                try {
                    nm.deleteNotificationChannel(MONITOR_CHANNEL_ID);
                } catch (Exception ignored) {}
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

    public static void scheduleNextDailyReportAlarm(Context context) {
        try {
            SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
            int hour = sp.getInt("dailyHour", 9);
            int minute = sp.getInt("dailyMinute", 0);
            java.util.Calendar cal = java.util.Calendar.getInstance();
            cal.set(java.util.Calendar.HOUR_OF_DAY, hour);
            cal.set(java.util.Calendar.MINUTE, minute);
            cal.set(java.util.Calendar.SECOND, 0);
            cal.set(java.util.Calendar.MILLISECOND, 0);
            if (cal.getTimeInMillis() <= System.currentTimeMillis() + 2000L) {
                cal.add(java.util.Calendar.DAY_OF_YEAR, 1);
            }
            long triggerAt = cal.getTimeInMillis();
            AlarmManager am = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
            if (am == null) return;
            Intent i = new Intent(context, BackgroundAlertReceiver.class);
            i.setAction("com.priceradar.app.DAILY_REPORT_ALARM");
            PendingIntent pi = PendingIntent.getBroadcast(
                context,
                205,
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
            try {
                NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
                if (nm != null) {
                    nm.cancel(7001);
                }
            } catch (Exception ignored) {}
            if (intent != null && "com.priceradar.app.DELAYED_TEST_NOTIFICATION".equals(intent.getAction())) {
                String t = intent.getStringExtra("title");
                String m = intent.getStringExtra("message");
                showSystemNotification(
                    context,
                    t != null ? t : "🔔 התראת PriceRadar כשהאפליקציה סגורה!",
                    m != null ? m : "מנוע הרקע פועל בהצלחה גם לאחר סגירה מהמולטיטאסקינג!",
                    (int) (System.currentTimeMillis() & 0x7fffffff)
                );
                return;
            }
            if (intent != null && "com.priceradar.app.DAILY_REPORT_ALARM".equals(intent.getAction())) {
                SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                String dTitle = sp.getString("dailyTitle", "📊 דו\\"ח מחירים יומי — PriceRadar");
                String dMsg = sp.getString("dailyMessage", "הדו\\"ח היומי של המוצרים שלך במעקב מוכן!");
                showSystemNotification(context, dTitle, dMsg, 99001);
                scheduleNextDailyReportAlarm(context);
            }
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

                    // Load local backup first so background check works even before or without cloud sync!
                    JSONObject localPayload = null;
                    String localBackupStr = sp.getString("fullStateBackup", "");
                    if (localBackupStr != null && !localBackupStr.isEmpty()) {
                        try {
                            localPayload = new JSONObject(localBackupStr);
                        } catch (Exception ignored) {}
                    }

                    JSONObject activePayload = localPayload;

                    if (deviceId != null && !deviceId.isEmpty()) {
                        try {
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
                                    JSONObject cloudPayload = row.optJSONObject("payload");
                                    if (cloudPayload != null) {
                                        JSONArray cloudProds = cloudPayload.optJSONArray("products");
                                        JSONArray localProds = localPayload != null ? localPayload.optJSONArray("products") : null;
                                        if ((cloudProds != null && cloudProds.length() > 0) || localProds == null || localProds.length() == 0) {
                                            activePayload = cloudPayload;
                                        }
                                    }
                                }
                            }
                        } catch (Exception ignored) {}
                    }

                    if (activePayload != null) {
                        // 1. Check if cloud scraper added a new alert
                        JSONArray alerts = activePayload.optJSONArray("alerts");
                        if (alerts != null && alerts.length() > 0) {
                            JSONObject latest = alerts.getJSONObject(0);
                            String alertId = latest.optString("id");
                            String lastNotified = sp.getString("lastAlertId", "");

                            if (!alertId.isEmpty() && !alertId.equals(lastNotified)) {
                                sp.edit().putString("lastAlertId", alertId).commit();
                                String title = latest.optString("title", "🔥 המחיר ירד!");
                                String msg = latest.optString("messagePlain", "נמצאה ירידת מחיר באחד המוצרים שלך");
                                showSystemNotification(context, title, msg, Math.abs(alertId.hashCode()));
                            }
                        }

                        // 2. Perform direct background check on tracked products from device
                        JSONArray products = activePayload.optJSONArray("products");
                        boolean updated = false;
                        if (products != null && products.length() > 0) {
                            updated = checkProductsInBackground(context, sp, products, alerts != null ? alerts : new JSONArray(), activePayload);
                        }

                        // 3. Check if Daily Summary Report is due while app is closed
                        JSONObject settings = activePayload.optJSONObject("settings");
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
                                sp.edit().putString("lastDailySentDate", todayStr).commit();
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

                        if (updated) {
                            sp.edit().putString("fullStateBackup", activePayload.toString()).commit();
                            if (deviceId != null && !deviceId.isEmpty() && deviceSecret != null && !deviceSecret.isEmpty()) {
                                pushUpdatedPayloadToSupabase(deviceId, deviceSecret, activePayload);
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
                Matcher mFinal = Pattern.compile("data-price-type=[\\"']finalPrice[\\"'][^>]*data-price-amount=[\\"']([0-9.]+)[\\"']|data-price-amount=[\\"']([0-9.]+)[\\"'][^>]*data-price-type=[\\"']finalPrice[\\"']").matcher(html);
                if (mFinal.find()) {
                    String g = mFinal.group(1) != null ? mFinal.group(1) : mFinal.group(2);
                    double v = Double.parseDouble(g);
                    if (v > 5) return variant.contains("אילת") ? (double) Math.round(v / 1.18) : v;
                }
                Matcher mPayngoNow = Pattern.compile("(?:לרכישה עכשיו ב|מחיר\\\\s+(?:מיוחד|מבצע))\\\\s*:\\\\s*₪?\\\\s*(\\\\d{1,3}(?:,\\\\d{3})*(?:\\\\.\\\\d{1,2})?)").matcher(html);
                if (mPayngoNow.find()) {
                    double v = Double.parseDouble(mPayngoNow.group(1).replace(",", ""));
                    if (v > 5) return variant.contains("אילת") ? (double) Math.round(v / 1.18) : v;
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
        public void saveFullStateBackup(final String stateJson) {
            if (stateJson == null || stateJson.isEmpty()) return;
            SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
            sp.edit().putString("fullStateBackup", stateJson).commit();
        }

        @JavascriptInterface
        public String loadFullStateBackup() {
            SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
            return sp.getString("fullStateBackup", "");
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
            ed.commit();

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
        public void scheduleDailyAlarm(final int hour, final int minute, final String title, final String message) {
            try {
                SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                sp.edit()
                    .putInt("dailyHour", hour)
                    .putInt("dailyMinute", minute)
                    .putString("dailyTitle", title != null ? title : "📊 דו\\"ח מחירים יומי — PriceRadar")
                    .putString("dailyMessage", message != null ? message : "מעקב המחירים היומי שלך פעיל!")
                    .putString("lastDailySentDate", "")
                    .commit();
                scheduleNextDailyReportAlarm(context);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        @JavascriptInterface
        public void scheduleDelayedNotification(final String title, final String message, final int delaySeconds) {
            try {
                int secs = Math.max(1, delaySeconds);
                long triggerAt = System.currentTimeMillis() + (secs * 1000L);
                AlarmManager am = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
                if (am == null) return;
                Intent i = new Intent(context, BackgroundAlertReceiver.class);
                i.setAction("com.priceradar.app.DELAYED_TEST_NOTIFICATION");
                i.putExtra("title", title);
                i.putExtra("message", message);
                PendingIntent pi = PendingIntent.getBroadcast(
                    context,
                    (int) (System.currentTimeMillis() & 0xfff),
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

        @JavascriptInterface
        public String consumePendingSharedUrl() {
            try {
                SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                String u = sp.getString("pendingSharedUrl", "");
                if (u != null && !u.isEmpty()) {
                    sp.edit().putString("pendingSharedUrl", "").commit();
                    return u;
                }
            } catch (Exception ignored) {}
            return "";
        }

        @JavascriptInterface
        public String getClipboardText() {
            try {
                ClipboardManager cm = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
                if (cm != null && cm.hasPrimaryClip()) {
                    ClipData cd = cm.getPrimaryClip();
                    if (cd != null && cd.getItemCount() > 0) {
                        CharSequence cs = cd.getItemAt(0).coerceToText(context);
                        if (cs != null) {
                            return cs.toString();
                        }
                    }
                }
            } catch (Exception ignored) {}
            return "";
        }

        @JavascriptInterface
        public String resolveRedirectUrl(final String rawUrl) {
            if (rawUrl == null || rawUrl.isEmpty()) return "";
            String currentUrl = rawUrl;
            try {
                for (int hop = 0; hop < 6; hop++) {
                    URL u = new URL(currentUrl);
                    HttpURLConnection conn = (HttpURLConnection) u.openConnection();
                    conn.setInstanceFollowRedirects(false);
                    conn.setRequestMethod("GET");
                    conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36");
                    conn.setConnectTimeout(3500);
                    conn.setReadTimeout(3500);
                    int code = conn.getResponseCode();
                    if (code >= 300 && code < 400) {
                        String loc = conn.getHeaderField("Location");
                        conn.disconnect();
                        if (loc == null || loc.isEmpty()) break;
                        if (loc.startsWith("/")) {
                            currentUrl = u.getProtocol() + "://" + u.getHost() + loc;
                        } else if (!loc.startsWith("http")) {
                            currentUrl = new URL(u, loc).toString();
                        } else {
                            currentUrl = loc;
                        }
                    } else {
                        String finalUrl = conn.getURL() != null ? conn.getURL().toString() : currentUrl;
                        conn.disconnect();
                        currentUrl = finalUrl;
                        break;
                    }
                }
            } catch (Exception ignored) {}
            return currentUrl;
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
                                // Cleanly extract essential HTML (remove scripts, svgs, store notices and heavy tags) without corrupting price structure
                                String compactScript = "(function(){" +
                                    "try {" +
                                    "  var d = document;" +
                                    "  if (!d || !d.documentElement) return '';" +
                                    "  var title = d.title || '';" +
                                    "  if (title.indexOf('Just a moment') !== -1) return 'Just a moment';" +
                                    "  var removeSel = 'script, style, noscript, svg, iframe, .woocommerce-store-notice, .demo_store, [class*=\\\"store-notice\\\"], [class*=\\\"shipping-notice\\\"]';" +
                                    "  d.querySelectorAll(removeSel).forEach(function(el){ try{ el.remove(); }catch(e){} });" +
                                    "  return d.documentElement.outerHTML.substring(0, 320000);" +
                                    "} catch(e) { return ''; }" +
                                    "})();";
                                view.evaluateJavascript(compactScript, value -> {
                                    if (delivered) return;
                                    if (value != null && value.contains("Just a moment")) {
                                        mainHandler.postDelayed(() -> {
                                            if (delivered) return;
                                            delivered = true;
                                            view.evaluateJavascript(compactScript, val2 -> {
                                                sendResult(callbackId, val2);
                                            });
                                        }, 2000);
                                    } else {
                                        delivered = true;
                                        sendResult(callbackId, value);
                                    }
                                });
                            }, 1200);
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
