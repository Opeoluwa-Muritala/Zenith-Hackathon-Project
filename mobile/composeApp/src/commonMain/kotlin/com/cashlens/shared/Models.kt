package com.cashlens.shared

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Overview(
    @SerialName("income_minor") val incomeMinor: Long,
    @SerialName("spend_minor") val spendMinor: Long,
    @SerialName("total_balance_minor") val totalBalanceMinor: Long,
    @SerialName("savings_rate_bps") val savingsRateBps: Int,
)

@Serializable
data class Insight(
    val id: String,
    val module: String,
    val kind: String,
    val severity: String,
    val title: String,
    val body: String,
    val footer: String? = null,
)

sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>
    data object Empty : LoadState<Nothing>
    data class Content<T>(val value: T) : LoadState<T>
    data class Failed(val message: String) : LoadState<Nothing>
}
