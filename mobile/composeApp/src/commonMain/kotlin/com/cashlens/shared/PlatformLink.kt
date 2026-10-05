package com.cashlens.shared

/** Opens the Mono hosted link using the safest platform browser surface. */
expect class PlatformLinkLauncher {
    fun open(url: String)
}
