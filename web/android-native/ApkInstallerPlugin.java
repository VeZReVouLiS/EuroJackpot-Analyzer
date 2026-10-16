package io.github.vezrevoulis.eurojackpot;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Updates the app from inside: downloads the new APK of the project's GitHub release, checks its SHA-256 and hands it to
 * the Android installer (the user confirms). Only URLs of this project's releases are accepted.
 */
@CapacitorPlugin(name = "ApkInstaller")
public class ApkInstallerPlugin extends Plugin {
    private static final String ALLOWED = "https://github.com/VeZReVouLiS/EuroJackpot-Analyzer/releases/download/";

    @PluginMethod
    public void canInstall(PluginCall call) {
        JSObject r = new JSObject();
        r.put("allowed", Build.VERSION.SDK_INT < Build.VERSION_CODES.O || getContext().getPackageManager().canRequestPackageInstalls());
        call.resolve(r);
    }

    /** Opens the Android page where the user allows this app to install updates. */
    @PluginMethod
    public void openSettings(PluginCall call) {
        Context ctx = getContext();
        Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + ctx.getPackageName()));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        ctx.startActivity(i);
        call.resolve();
    }

    @PluginMethod
    public void downloadAndInstall(final PluginCall call) {
        final String apkUrl = call.getString("apkUrl", "");
        final String shaUrl = call.getString("shaUrl", "");
        if (!apkUrl.startsWith(ALLOWED) || !shaUrl.startsWith(ALLOWED)) {
            call.reject("The update address is not allowed.");
            return;
        }
        new Thread(() -> {
            try {
                String want = fetchSha(shaUrl);
                File dir = new File(getContext().getCacheDir(), "updates");
                if (!dir.exists() && !dir.mkdirs()) throw new Exception("Cannot create the download folder.");
                File apk = new File(dir, "EuroJackpotApp-update.apk");
                HttpURLConnection c = (HttpURLConnection) new URL(apkUrl).openConnection();
                c.setConnectTimeout(30000);
                c.setReadTimeout(60000);
                c.setInstanceFollowRedirects(true);
                if (c.getResponseCode() != 200) throw new Exception("Download failed (HTTP " + c.getResponseCode() + ").");
                long total = c.getContentLengthLong(), done = 0, lastEvent = 0;
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(apk)) {
                    byte[] buf = new byte[65536];
                    int n;
                    while ((n = in.read(buf)) > 0) {
                        out.write(buf, 0, n);
                        md.update(buf, 0, n);
                        done += n;
                        if (done - lastEvent > 131072 || done == total) {
                            lastEvent = done;
                            JSObject p = new JSObject();
                            p.put("done", done);
                            p.put("total", total);
                            notifyListeners("progress", p);
                        }
                    }
                }
                StringBuilder hex = new StringBuilder();
                for (byte b : md.digest()) hex.append(String.format("%02x", b));
                if (!hex.toString().equalsIgnoreCase(want)) {
                    //noinspection ResultOfMethodCallIgnored
                    apk.delete();
                    throw new Exception("Checksum mismatch - download discarded.");
                }
                Context ctx = getContext();
                Uri uri = FileProvider.getUriForFile(ctx, ctx.getPackageName() + ".fileprovider", apk);
                Intent i = new Intent(Intent.ACTION_VIEW);
                i.setDataAndType(uri, "application/vnd.android.package-archive");
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(i);
                call.resolve();
            } catch (Exception e) {
                call.reject(e.getMessage() == null ? e.toString() : e.getMessage());
            }
        }).start();
    }

    private String fetchSha(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(30000);
        c.setReadTimeout(30000);
        c.setInstanceFollowRedirects(true);
        if (c.getResponseCode() != 200) throw new Exception("Checksum download failed (HTTP " + c.getResponseCode() + ").");
        try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()))) {
            Matcher m = Pattern.compile("\\b([0-9a-fA-F]{64})\\b").matcher(r.readLine());
            if (!m.find()) throw new Exception("The checksum file is invalid.");
            return m.group(1);
        }
    }
}
