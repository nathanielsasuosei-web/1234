package com.meetbeatz.app

import android.Manifest
import android.app.Activity
import android.app.DownloadManager
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.content.getSystemService
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat

/**
 * The native shell used when no browser on the device can host a Trusted Web Activity.
 *
 * It is not a second implementation of the site — the same pages load, from the same
 * origin, with the same session. What it adds is the four things a bare WebView would
 * otherwise drop on the floor, all of which are load-bearing on Meetbeatz:
 *
 *  1. **Downloads.** Beats, stems, sound kits and artwork are delivered as file
 *     downloads. `setDownloadListener` hands them to Android's `DownloadManager`, so a
 *     paid file lands in the Downloads folder, shows progress in the notification
 *     shade, and survives the app being closed.
 *
 *  2. **The microphone and camera.** `/record`, `/live-recording` and `/call` use
 *     `getUserMedia`. A WebView denies that by default: each request has to be answered
 *     with `PermissionRequest.grant()`, and Android's own runtime permission has to be
 *     held first.
 *
 *  3. **File uploads.** Artwork for `/distribution`, admin uploads and chat audio all
 *     use `<input type="file">`, which needs `onShowFileChooser` to open the system
 *     picker.
 *
 *  4. **Payments staying put.** Third-party cookies are enabled and `target="_blank"`
 *     links open in the same WebView, because Paystack's checkout and the 3-D Secure
 *     step hop between origins and windows; sending those hops to an external browser
 *     would strand the customer outside the order they were paying for.
 */
class MeetbeatzWebViewActivity : Activity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var errorView: View

    /** The `<input type="file">` callback awaiting a picker result. */
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    /** A `getUserMedia` request awaiting Android's runtime permission answer. */
    private var pendingPermissionRequest: PermissionRequest? = null

    /** A paid download waiting on storage permission (Android 9 and below only). */
    private var pendingDownload: PendingDownload? = null

    private var customView: View? = null
    private var customViewCallback: WebChromeClient.CustomViewCallback? = null
    private var recoveredFromRenderProcessGone = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        progressBar = createProgressBar()
        errorView = createErrorView()

        val root = FrameLayout(this).apply {
            setBackgroundColor(ContextCompat.getColor(this@MeetbeatzWebViewActivity, R.color.ink))
            addView(
                webView,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
            addView(
                progressBar,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    (3 * resources.displayMetrics.density).toInt(),
                    Gravity.TOP,
                ),
            )
            addView(
                errorView,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
        }
        setContentView(root)

        // Android 15 and later draw every app edge to edge whether it asked to or not,
        // and this app targets that level. Opting in explicitly keeps older devices
        // identical, and the listener below is what stops the page sliding under the
        // status bar or the keyboard covering the field a customer is typing in.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout(),
            )
            val keyboard = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom
            view.setPadding(bars.left, bars.top, bars.right, maxOf(bars.bottom, keyboard))
            insets
        }

        if (BuildConfig.DEBUG) {
            WebView.setWebContentsDebuggingEnabled(true)
        }

        configure(webView)
        webView.webViewClient = MeetbeatzWebViewClient()
        webView.webChromeClient = MeetbeatzChromeClient()
        webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            startDownload(url, userAgent, contentDisposition, mimeType)
        }

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState)
        } else {
            webView.loadUrl(intent.getStringExtra(EXTRA_URL) ?: DEFAULT_URL)
        }
    }

    // ---------------------------------------------------------------- configuration

    private fun configure(webView: WebView) {
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            loadsImagesAutomatically = true

            // Beat previews start from a tap on a play button, but the player bar moves
            // between tracks on its own. Without this, the second track is blocked.
            mediaPlaybackRequiresUserGesture = false

            // The site is HTTPS-only; never silently downgrade a payment page.
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setGeolocationEnabled(false)
            cacheMode = WebSettings.LOAD_DEFAULT

            // Pinch to zoom is useful for the licence tables; the on-screen +/- buttons
            // are not, so only the gesture is left on.
            builtInZoomControls = true
            displayZoomControls = false

            // `target="_blank"` and JS `window.open` load in this WebView instead of a
            // new window that a WebView cannot create — see point 4 in the class comment.
            setSupportMultipleWindows(false)
            javaScriptCanOpenWindowsAutomatically = true

            // No file:// access: nothing in the site needs it, and it is the usual
            // bridge between a hostile page and the device's storage.
            allowFileAccess = false
            allowContentAccess = true

            // The site's own analytics and the producer's admin pages can tell the app
            // from a browser tab, which is what makes an "installed from the app" number
            // possible without a separate tracking SDK.
            userAgentString = listOfNotNull(userAgentString, APP_USER_AGENT).joinToString(" ")
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            // Paystack's checkout and 3-D Secure run inside iframes on other origins.
            setAcceptThirdPartyCookies(webView, true)
        }
    }

    // ------------------------------------------------------------------ page loading

    private inner class MeetbeatzWebViewClient : WebViewClient() {

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val url = request.url
            return if (url.scheme == "http" || url.scheme == "https") {
                // Stay in the WebView — including for checkout and 3-D Secure.
                false
            } else {
                openExternally(url)
                true
            }
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
            progressBar.visibility = View.VISIBLE
            errorView.visibility = View.GONE
        }

        override fun onPageFinished(view: WebView, url: String?) {
            progressBar.visibility = View.GONE
        }

        override fun onReceivedError(
            view: WebView,
            request: WebResourceRequest,
            error: WebResourceError,
        ) {
            if (!request.isForMainFrame) return
            progressBar.visibility = View.GONE
            errorView.visibility = View.VISIBLE
        }

        override fun onReceivedSslError(
            view: WebView,
            handler: SslErrorHandler,
            error: SslError,
        ) {
            // A certificate problem on a page that takes payments is never "proceed".
            handler.cancel()
        }

        override fun onRenderProcessGone(
            view: WebView,
            detail: RenderProcessGoneDetail,
        ): Boolean {
            // The renderer was killed (usually memory pressure). Rebuilding the WebView
            // once keeps a customer's session instead of killing the app; a second
            // death is treated as unrecoverable.
            if (!recoveredFromRenderProcessGone) {
                recoveredFromRenderProcessGone = true
                recreate()
                return true
            }
            finish()
            return true
        }
    }

    private inner class MeetbeatzChromeClient : WebChromeClient() {

        override fun onProgressChanged(view: WebView, newProgress: Int) {
            progressBar.progress = newProgress
            progressBar.visibility = if (newProgress in 1..99) View.VISIBLE else View.GONE
        }

        override fun onPermissionRequest(request: PermissionRequest) {
            val wantsAudio = request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
            val wantsVideo = request.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)

            val missing = buildList {
                if (wantsAudio && !hasPermission(Manifest.permission.RECORD_AUDIO)) {
                    add(Manifest.permission.RECORD_AUDIO)
                }
                if (wantsVideo && !hasPermission(Manifest.permission.CAMERA)) {
                    add(Manifest.permission.CAMERA)
                }
            }

            if (missing.isEmpty()) {
                if (wantsAudio || wantsVideo) request.grant(request.resources) else request.deny()
                return
            }

            pendingPermissionRequest = request
            ActivityCompat.requestPermissions(this@MeetbeatzWebViewActivity, missing.toTypedArray(), REQUEST_MEDIA)
        }

        override fun onGeolocationPermissionsShowPrompt(
            origin: String?,
            callback: android.webkit.GeolocationPermissions.Callback?,
        ) {
            // Meetbeatz sends `Permissions-Policy: geolocation=()` and has no feature
            // that needs a location; nothing to ask the user for.
            callback?.invoke(origin, false, false)
        }

        override fun onShowFileChooser(
            webView: WebView,
            callback: ValueCallback<Array<Uri>>,
            params: FileChooserParams,
        ): Boolean {
            filePathCallback?.onReceiveValue(null)
            filePathCallback = callback
            return try {
                startActivityForResult(params.createIntent(), REQUEST_FILE)
                true
            } catch (_: ActivityNotFoundException) {
                filePathCallback = null
                false
            }
        }

        override fun onShowCustomView(view: View, callback: CustomViewCallback) {
            if (customView != null) {
                callback.onCustomViewHidden()
                return
            }
            customView = view
            customViewCallback = callback
            (window.decorView as ViewGroup).addView(view)
            webView.visibility = View.GONE
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }

        override fun onHideCustomView() {
            val view = customView ?: return
            (window.decorView as ViewGroup).removeView(view)
            customView = null
            webView.visibility = View.VISIBLE
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            customViewCallback?.onCustomViewHidden()
            customViewCallback = null
        }
    }

    // -------------------------------------------------------------------- downloads

    /** Everything needed to enqueue a download once permission allows it. */
    private data class PendingDownload(
        val url: String,
        val userAgent: String,
        val contentDisposition: String,
        val mimeType: String,
    )

    /**
     * Paid files, stems and sound kits arrive as downloads.
     *
     * Two details matter here. First, the site's download routes are authorised by the
     * session cookie, and `DownloadManager` runs outside the WebView, so the cookie is
     * copied onto the request — without it the customer is served the "no such token"
     * page instead of the file they paid for. Second, on Android 9 and below writing to
     * the shared Downloads folder needs `WRITE_EXTERNAL_STORAGE` at runtime, so that is
     * requested first and the download is queued behind the answer.
     */
    private fun startDownload(
        url: String,
        userAgent: String,
        contentDisposition: String,
        mimeType: String,
    ) {
        if (url.startsWith("blob:") || url.startsWith("data:")) {
            // Files generated in the page (the colour adjuster's 3000 x 3000 export)
            // never reach a DownloadListener: the bytes exist only in the renderer.
            // They need a full browser download, so say so instead of failing silently.
            toast(getString(R.string.blob_download_unsupported))
            return
        }

        val request = PendingDownload(url, userAgent, contentDisposition, mimeType)

        if (needsLegacyStoragePermission() && !hasPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)) {
            pendingDownload = request
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE),
                REQUEST_STORAGE,
            )
            return
        }

        enqueue(request, publicDestination = true)
    }

    private fun needsLegacyStoragePermission() = Build.VERSION.SDK_INT <= Build.VERSION_CODES.P

    private fun enqueue(download: PendingDownload, publicDestination: Boolean) {
        val fileName = URLUtil.guessFileName(
            download.url,
            download.contentDisposition,
            download.mimeType,
        )

        try {
            val request = DownloadManager.Request(Uri.parse(download.url)).apply {
                setMimeType(download.mimeType.ifBlank { null })
                addRequestHeader("User-Agent", download.userAgent)
                addRequestHeader("Cookie", CookieManager.getInstance().getCookie(download.url) ?: "")
                setTitle(fileName)
                setDescription(getString(R.string.app_name))
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                if (publicDestination) {
                    // Where the customer expects to find it: Downloads, visible in the
                    // Files app and to any DAW or player on the phone.
                    setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
                } else {
                    // Permission was refused: the file still arrives, in the app's own
                    // files folder, and the toast says where.
                    setDestinationInExternalFilesDir(
                        this@MeetbeatzWebViewActivity,
                        Environment.DIRECTORY_DOWNLOADS,
                        fileName,
                    )
                }
                // The site only ever serves these over TLS, and a customer on mobile
                // data in Accra is the expected case, not the exception.
                setAllowedOverMetered(true)
                setAllowedOverRoaming(false)
            }

            requireNotNull(getSystemService<DownloadManager>()).enqueue(request)
            toast(getString(if (publicDestination) R.string.download_started else R.string.download_private_folder))
        } catch (_: Exception) {
            toast(getString(R.string.download_failed))
        }
    }

    // ------------------------------------------------------ results and permissions

    @Deprecated("startActivityForResult is still the documented WebView file-chooser path")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_FILE) return

        val callback = filePathCallback ?: return
        filePathCallback = null
        callback.onReceiveValue(
            if (resultCode == RESULT_OK && data != null) {
                WebChromeClient.FileChooserParams.parseResult(resultCode, data)
            } else {
                null
            },
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        if (requestCode == REQUEST_STORAGE) {
            val download = pendingDownload ?: return
            pendingDownload = null
            val granted = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
            enqueue(download, publicDestination = granted)
            return
        }

        if (requestCode != REQUEST_MEDIA) return

        val request = pendingPermissionRequest ?: return
        pendingPermissionRequest = null

        val granted = permissions.indices.all { grantResults.getOrNull(it) == PackageManager.PERMISSION_GRANTED }
        if (granted) {
            request.grant(request.resources)
        } else {
            request.deny()
            toast(
                getString(
                    if (permissions.contains(Manifest.permission.RECORD_AUDIO)) {
                        R.string.microphone_denied
                    } else {
                        R.string.camera_denied
                    },
                ),
            )
        }
    }

    private fun hasPermission(permission: String) =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    // -------------------------------------------------------------- chrome and views

    private fun createProgressBar() = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
        max = 100
        progress = 0
        visibility = View.GONE
        progressTintList = android.content.res.ColorStateList.valueOf(
            ContextCompat.getColor(this@MeetbeatzWebViewActivity, R.color.acid),
        )
    }

    /**
     * The offline/error screen. It is deliberately native and local: while it is on
     * screen there is nothing to load from the network by definition.
     */
    private fun createErrorView(): View {
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 48, 48, 48)
            setBackgroundColor(ContextCompat.getColor(this@MeetbeatzWebViewActivity, R.color.ink))
            visibility = View.GONE
        }

        column.addView(
            TextView(this).apply {
                text = getString(R.string.offline_title)
                setTextAppearance(R.style.MeetbeatzTitle)
                gravity = Gravity.CENTER
            },
        )
        column.addView(
            TextView(this).apply {
                text = getString(R.string.offline_body)
                setTextAppearance(R.style.MeetbeatzBody)
                gravity = Gravity.CENTER
                setPadding(0, 16, 0, 0)
            },
        )
        column.addView(
            Button(this).apply {
                text = getString(R.string.offline_retry)
                setTextAppearance(R.style.MeetbeatzButton)
                setOnClickListener { retry() }
            },
        )
        column.addView(
            Button(this).apply {
                text = getString(R.string.open_in_browser)
                setTextAppearance(R.style.MeetbeatzBody)
                setTextColor(ContextCompat.getColor(this@MeetbeatzWebViewActivity, R.color.cream))
                setBackgroundColor(android.graphics.Color.TRANSPARENT)
                setPadding(0, 24, 0, 0)
                setOnClickListener {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(webView.url ?: DEFAULT_URL)))
                }
            },
        )
        return column
    }

    private fun retry() {
        errorView.visibility = View.GONE
        if (isOnline()) {
            webView.reload()
        } else {
            errorView.visibility = View.VISIBLE
        }
    }

    private fun isOnline(): Boolean {
        val manager = getSystemService<ConnectivityManager>() ?: return true
        return manager.activeNetwork != null
    }

    private fun openExternally(uri: Uri) {
        try {
            // tel:, mailto:, whatsapp:, sms:, intent:, market: and USSD codes — anything
            // that is not a web page belongs to another app, if one is installed.
            startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: ActivityNotFoundException) {
            toast(getString(R.string.no_app_for_link))
        }
    }

    private fun toast(message: String) =
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()

    // ---------------------------------------------------------------- lifecycle

    @Deprecated("Back handling for a WebView shell")
    override fun onBackPressed() {
        when {
            customView != null -> webView.webChromeClient?.onHideCustomView()
            errorView.visibility == View.VISIBLE -> finish()
            webView.canGoBack() -> webView.goBack()
            else -> super.onBackPressed()
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        webView.saveState(outState)
    }

    override fun onDestroy() {
        filePathCallback?.onReceiveValue(null)
        filePathCallback = null
        pendingPermissionRequest?.deny()
        pendingPermissionRequest = null
        webView.destroy()
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_URL = "com.meetbeatz.app.extra.URL"
        private const val DEFAULT_URL = "https://meetbeatz.com"
        private const val REQUEST_FILE = 4101
        private const val REQUEST_MEDIA = 4102
        private const val REQUEST_STORAGE = 4103
        private const val APP_USER_AGENT = "MeetbeatzAndroid/1.0.0"

        fun createIntent(context: Context, uri: Uri): Intent =
            Intent(context, MeetbeatzWebViewActivity::class.java)
                .putExtra(EXTRA_URL, uri.toString())
    }
}
