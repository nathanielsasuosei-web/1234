package com.meetbeatz.app

import androidx.browser.customtabs.CustomTabsCallback
import com.google.androidbrowserhelper.trusted.LauncherActivity
import com.google.androidbrowserhelper.trusted.TwaLauncher

/**
 * The app's entry point: a Trusted Web Activity around meetbeatz.com.
 *
 * Everything the customer does — browsing the store, previewing a beat, checking out
 * with Mobile Money, recording a verse in the online booth — is the website itself,
 * rendered by the device's browser engine with no browser UI around it. This class
 * adds nothing visual; it only decides what happens in the two cases where the stock
 * behaviour would be wrong for a store:
 *
 * 1. [getFallbackStrategy] — when no browser on the device can host a Trusted Web
 *    Activity, android-browser-helper would normally open a plain Custom Tab. A
 *    customer who just tapped the app icon would land in a browser-looking window
 *    that cannot save the files they paid for. The native shell in
 *    [MeetbeatzWebViewActivity] is used instead.
 *
 * 2. [getCustomTabsCallback] — android-browser-helper installs a `QualityEnforcer`
 *    callback which *deliberately throws* a RuntimeException in the host app when the
 *    browser provider reports a TWA quality problem. That is a reasonable choice for
 *    a news reader; it is not one for an app whose most likely failure moment is
 *    mid-checkout. The plain callback is returned here so a provider hiccup degrades
 *    into a normal Custom Tab launch instead of a crash dialog.
 */
class MeetbeatzLauncherActivity : LauncherActivity() {

    override fun getCustomTabsCallback(): CustomTabsCallback = CustomTabsCallback()

    override fun getFallbackStrategy(): TwaLauncher.FallbackStrategy =
        TwaLauncher.FallbackStrategy { context, twaBuilder, _, _ ->
            context.startActivity(
                MeetbeatzWebViewActivity.createIntent(context, twaBuilder.uri),
            )
        }
}
