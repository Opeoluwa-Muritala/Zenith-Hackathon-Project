package com.cashlens.shared

import android.content.Context
import androidx.browser.customtabs.CustomTabsIntent
import androidx.core.net.toUri

/** Android Custom Tabs implementation; URLs originate from the trusted backend. */
actual class PlatformLinkLauncher(private val context: Context) {
    actual fun open(url: String) {
        require(url.startsWith("https://")) { "Only HTTPS provider links are allowed" }
        CustomTabsIntent.Builder().build().launchUrl(context, url.toUri())
    }
}
