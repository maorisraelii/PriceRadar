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

    # 4. Update AndroidManifest.xml
    p_manifest = "android/app/src/main/AndroidManifest.xml"
    if os.path.exists(p_manifest):
        with open(p_manifest, "r", encoding="utf-8") as f:
            m = f.read()
        perms = """
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />
"""
        if "POST_NOTIFICATIONS" not in m:
            m = m.replace("</manifest>", perms + "</manifest>")
        rcvr = """
        <receiver android:name=".MainActivity$BackgroundAlertReceiver" android:exported="false" />
"""
        if "BackgroundAlertReceiver" not in m:
            m = m.replace("</application>", rcvr + "</application>")
        with open(p_manifest, "w", encoding="utf-8") as f:
            f.write(m)
        print("Updated AndroidManifest.xml with permissions and receiver")

    # 5. Write MainActivity.java
    main_activity_dir = "android/app/src/main/java/com/priceradar/app"
    os.makedirs(main_activity_dir, exist_ok=True)
    main_activity_path = os.path.join(main_activity_dir, "MainActivity.java")

    java_code = """package com.priceradar.app;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.core.app.NotificationCompat;
import com.getcapacitor.BridgeActivity;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends BridgeActivity {
    public static final String CHANNEL_ID = "price_radar_alerts";
    private WebView scraperWebView;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createNotificationChannel();
        try {
            WebView mainWv = this.getBridge().getWebView();
            mainWv.addJavascriptInterface(new NativeScraperBridge(mainWv, this), "AndroidNativeScraper");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "התראות מחיר PriceRadar",
                NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("התראות מיידיות על ירידות מחיר מחוץ לאפליקציה");
            channel.enableVibration(true);
            channel.enableLights(true);
            channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    public static class BackgroundAlertReceiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context context, Intent intent) {
            new Thread(() -> {
                try {
                    SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
                    String deviceId = sp.getString("deviceId", "");
                    if (deviceId == null || deviceId.isEmpty()) return;

                    String sbUrl = "https://ljggqatmryzfvvveefiz.supabase.co/rest/v1/user_profiles?device_id=eq." + deviceId + "&select=payload";
                    String sbKey = "sb_publishable_BEFtsujmDeFgYfUicT0aTA_e5H2f6bx";
                    URL u = new URL(sbUrl);
                    HttpURLConnection conn = (HttpURLConnection) u.openConnection();
                    conn.setRequestMethod("GET");
                    conn.setRequestProperty("apikey", sbKey);
                    conn.setRequestProperty("Authorization", "Bearer " + sbKey);
                    conn.setConnectTimeout(8000);
                    conn.setReadTimeout(8000);

                    if (conn.getResponseCode() == 200) {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                        StringBuilder sb = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) sb.append(line);
                        reader.close();

                        JSONArray arr = new JSONArray(sb.toString());
                        if (arr.length() > 0) {
                            JSONObject row = arr.getJSONObject(0);
                            JSONObject payload = row.optJSONObject("payload");
                            if (payload != null) {
                                JSONArray alerts = payload.optJSONArray("alerts");
                                if (alerts != null && alerts.length() > 0) {
                                    JSONObject latest = alerts.getJSONObject(0);
                                    String alertId = latest.optString("id");
                                    String lastNotified = sp.getString("lastAlertId", "");

                                    if (!alertId.isEmpty() && !alertId.equals(lastNotified)) {
                                        sp.edit().putString("lastAlertId", alertId).apply();
                                        String title = latest.optString("title", "🔥 המחיר ירד!");
                                        String msg = latest.optString("messagePlain", "נמצאה ירידת מחיר באחד המוצרים שלך");

                                        Intent tapIntent = new Intent(context, MainActivity.class);
                                        tapIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                                        PendingIntent pi = PendingIntent.getActivity(context, 0, tapIntent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

                                        NotificationCompat.Builder b = new NotificationCompat.Builder(context, CHANNEL_ID)
                                            .setSmallIcon(context.getApplicationInfo().icon)
                                            .setContentTitle(title)
                                            .setContentText(msg)
                                            .setPriority(NotificationCompat.PRIORITY_HIGH)
                                            .setDefaults(NotificationCompat.DEFAULT_ALL)
                                            .setAutoCancel(true)
                                            .setContentIntent(pi);

                                        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
                                        if (nm != null) {
                                            nm.notify(Math.abs(alertId.hashCode()), b.build());
                                        }
                                    }
                                }
                            }
                        }
                    }
                } catch (Exception ignored) {}
            }).start();
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
            if (deviceId == null || deviceId.isEmpty()) return;
            SharedPreferences sp = context.getSharedPreferences("PriceRadarPrefs", Context.MODE_PRIVATE);
            sp.edit().putString("deviceId", deviceId).apply();

            try {
                AlarmManager am = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
                Intent i = new Intent(context, BackgroundAlertReceiver.class);
                PendingIntent pi = PendingIntent.getBroadcast(context, 101, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
                if (am != null) {
                    long interval = 15 * 60 * 1000;
                    am.setInexactRepeating(AlarmManager.RTC_WAKEUP, System.currentTimeMillis() + interval, interval, pi);
                          context.sendBroadcast(i);
                }
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        @JavascriptInterface
        public void sendNativeNotification(final String title, final String message) {
            mainHandler.post(() -> {
                try {
                    NotificationCompat.Builder b = new NotificationCompat.Builder(context, CHANNEL_ID)
                        .setSmallIcon(context.getApplicationInfo().icon)
                        .setContentTitle(title)
                        .setContentText(message)
                        .setPriority(NotificationCompat.PRIORITY_HIGH)
                        .setDefaults(NotificationCompat.DEFAULT_ALL)
                        .setAutoCancel(true);

                    Intent tapIntent = new Intent(context, MainActivity.class);
                    tapIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                    PendingIntent pi = PendingIntent.getActivity(context, (int) System.currentTimeMillis(), tapIntent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
                    b.setContentIntent(pi);

                    NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
                    if (nm != null) {
                        nm.notify((int) System.currentTimeMillis(), b.build());
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
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

    # 6. Copy launcher icons
    for density in ["hdpi", "mdpi", "xhdpi", "xxhdpi", "xxxhdpi"]:
        folder = f"android/app/src/main/res/mipmap-{density}"
        os.makedirs(folder, exist_ok=True)
        if os.path.exists("icon-512.png"):
            shutil.copy("icon-512.png", f"{folder}/ic_launcher.png")
            shutil.copy("icon-512.png", f"{folder}/ic_launcher_round.png")
    print("Copied all launcher icons successfully!")

if __name__ == "__main__":
    main()
