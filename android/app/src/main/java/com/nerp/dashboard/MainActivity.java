package com.nerp.dashboard;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.google.mlkit.vision.barcode.common.Barcode;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner;
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning;

/**
 * NERP - the live ERP dashboard of NERP on the phone.
 *
 * The dashboard is served by "NERP Mobile" on the company PC (same Wi-Fi). The first
 * start asks to scan the QR code shown on the PC (Google code scanner - no camera
 * permission needed); the link contains the address of the PC and the pairing key. The
 * dashboard itself is the web page of NERP Mobile in a WebView; it is read-only and
 * updates live. Only the paired PC is shown inside the app, other links open the browser.
 */
public class MainActivity extends Activity {
    private static final String PREFS = "nerp";
    private static final String BASE = "base";
    private static final int NAVY = Color.parseColor("#0b1f3a");
    private static final int BLUE = Color.parseColor("#0a6ed1");

    private FrameLayout root;
    private WebView web;
    private String base;            // e.g. http://192.168.1.25:8090

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        root = new FrameLayout(this);
        root.setBackgroundColor(NAVY);
        root.setOnApplyWindowInsetsListener((v, insets) -> {     // Android 15: content edge to edge
            int top, bottom, left, right;
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets i = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                top = i.top; bottom = i.bottom; left = i.left; right = i.right;
            } else {
                top = insets.getSystemWindowInsetTop(); bottom = insets.getSystemWindowInsetBottom();
                left = insets.getSystemWindowInsetLeft(); right = insets.getSystemWindowInsetRight();
            }
            v.setPadding(left, top, right, bottom);
            return insets;
        });
        setContentView(root);
        if (android.os.Build.VERSION.SDK_INT >= 33) {           // back gesture (predictive back, Android 13+)
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::goBack);
        }
        base = getSharedPreferences(PREFS, MODE_PRIVATE).getString(BASE, null);
        if (base == null) showSetup(null);
        else showDashboard(base + "/m/");
    }

    // ------------------------------------------------------------------ setup (pairing)
    private void showSetup(String problem) {
        root.removeAllViews();
        web = null;
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        int p = dp(24);
        box.setPadding(p, dp(48), p, p);

        TextView logo = text("NERP", 30, Color.WHITE, true);
        TextView sub = text("Live dashboard", 16, Color.parseColor("#9fb4cf"), false);
        TextView how = text("1. On the PC start \"NERP Mobile\" - a QR code appears.\n"
                + "2. This phone must be in the same Wi-Fi as the PC.\n"
                + "3. Tap \"Scan QR code\" and point the camera at the code.", 15, Color.WHITE, false);
        how.setPadding(0, dp(32), 0, dp(24));
        how.setLineSpacing(0, 1.3f);
        Button scan = button("Scan QR code", BLUE);
        scan.setOnClickListener(v -> scan());

        TextView or = text("or enter the link / address of the PC", 13, Color.parseColor("#9fb4cf"), false);
        or.setPadding(0, dp(28), 0, dp(6));
        EditText addr = new EditText(this);
        addr.setHint("http://192.168.1.25:8090");
        addr.setHintTextColor(Color.parseColor("#6f84a0"));
        addr.setTextColor(Color.WHITE);
        addr.setSingleLine(true);
        addr.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        Button go = button("Connect", Color.parseColor("#1b3253"));
        go.setOnClickListener(v -> use(addr.getText().toString().trim()));

        box.addView(logo);
        box.addView(sub);
        if (problem != null) {
            TextView err = text(problem, 14, Color.parseColor("#ff8a8a"), false);
            err.setPadding(0, dp(20), 0, 0);
            box.addView(err);
        }
        box.addView(how);
        box.addView(scan, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));
        box.addView(or);
        box.addView(addr, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        box.addView(go, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));
        if (base != null) {
            Button back = button("Back to the dashboard", Color.TRANSPARENT);
            back.setOnClickListener(v -> showDashboard(base + "/m/"));
            box.addView(back);
        }
        android.widget.ScrollView sv = new android.widget.ScrollView(this);
        sv.addView(box);
        root.addView(sv);
    }

    private void scan() {
        GmsBarcodeScannerOptions opt = new GmsBarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_QR_CODE).build();
        GmsBarcodeScanner scanner = GmsBarcodeScanning.getClient(this, opt);
        scanner.startScan()
                .addOnSuccessListener(code -> use(code.getRawValue()))
                .addOnFailureListener(e -> Toast.makeText(this,
                        "The scanner could not start: " + e.getMessage(), Toast.LENGTH_LONG).show());
    }

    /** a scanned / typed link: http(s)://host:port[/m/#k=key] */
    private void use(String link) {
        if (link == null || link.isEmpty()) return;
        if (!link.startsWith("http://") && !link.startsWith("https://")) link = "http://" + link;
        Uri u = Uri.parse(link);
        if (u.getHost() == null || u.getHost().isEmpty()) {
            showSetup("This is not an NERP Mobile link - scan the QR code on the PC.");
            return;
        }
        String path = u.getPath() == null ? "" : u.getPath();
        if (!path.isEmpty() && !path.equals("/") && !path.startsWith("/m")) {
            showSetup("This is not an NERP Mobile link - scan the QR code on the PC.");
            return;
        }
        base = u.getScheme() + "://" + u.getHost() + (u.getPort() > 0 ? ":" + u.getPort() : "");
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(BASE, base).apply();
        String frag = u.getFragment();
        showDashboard(base + "/m/" + (frag != null && frag.startsWith("k=") ? "#" + frag : ""));
    }

    // ------------------------------------------------------------------ dashboard
    private void showDashboard(String url) {
        root.removeAllViews();
        web = new WebView(this);
        web.setBackgroundColor(NAVY);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setUserAgentString(s.getUserAgentString() + " NERPApp/1.0");
        CookieManager.getInstance().setAcceptCookie(true);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if ("nerp".equals(u.getScheme())) {                // links of the page: nerp://rescan
                    showSetup(null);
                    return true;
                }
                String b = Uri.parse(base).getHost();
                if (u.getHost() != null && u.getHost().equals(b)) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u));   // anything else: browser
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) showOffline(err.getDescription().toString());
            }

            @Override
            public void onPageFinished(WebView view, String u) {
                CookieManager.getInstance().flush();                 // keep the pairing
            }
        });
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        web.loadUrl(url);
    }

    private void showOffline(String why) {
        root.removeAllViews();
        web = null;
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        int p = dp(28);
        box.setPadding(p, p, p, p);
        box.addView(text("No connection to the PC", 22, Color.WHITE, true));
        TextView t = text("Is the PC on, \"NERP Mobile\" running and this phone in the same Wi-Fi?\n\n" + base
                + "\n(" + why + ")", 15, Color.parseColor("#c6d3e3"), false);
        t.setPadding(0, dp(16), 0, dp(24));
        box.addView(t);
        Button again = button("Try again", BLUE);
        again.setOnClickListener(v -> showDashboard(base + "/m/"));
        box.addView(again, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));
        Button rescan = button("Scan a new QR code", Color.parseColor("#1b3253"));
        rescan.setOnClickListener(v -> showSetup(null));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(48));
        lp.topMargin = dp(12);
        box.addView(rescan, lp);
        root.addView(box);
    }

    private void goBack() {
        if (web != null && web.canGoBack()) web.goBack();
        else finish();
    }

    @android.annotation.SuppressLint("GestureBackNavigation")    // Android 12 and older only
    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        goBack();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
    }

    @Override
    protected void onPause() {
        if (web != null) web.onPause();
        super.onPause();
    }

    // ------------------------------------------------------------------ small helpers
    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private TextView text(String s, int sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setGravity(Gravity.CENTER_HORIZONTAL);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button button(String s, int color) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(16);
        b.setBackgroundColor(color);
        return b;
    }
}
