package com.cashlens.data
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query
@Serializable data class Overview(@SerialName("income_minor") val income:Long,@SerialName("spend_minor") val spend:Long,@SerialName("total_balance_minor") val balance:Long,@SerialName("savings_rate_bps") val savingsRate:Int)
@Serializable data class InsightDto(val id:String,val module:String,val kind:String,val severity:String,val title:String,val body:String,val payload:Map<String,String>?=null,val footer:String?=null)
@Serializable data class ConsentDto(val id:String,val institution:String,val scope:String,@SerialName("revoked_at") val revokedAt:String?=null)
@Serializable data class RecurringDto(val id:String,@SerialName("amount_minor") val amount:Long,@SerialName("next_expected_at") val nextExpected:String,val status:String,@SerialName("annualised_minor") val annualised:Long)
interface CashlensApi {
 @GET("summary/overview") suspend fun overview():Overview
 @GET("insights") suspend fun insights(@Query("module") module:String?=null):List<InsightDto>
 @GET("consents") suspend fun consents():List<ConsentDto>
 @DELETE("consents/{id}") suspend fun revoke(@Path("id") id:String)
 @GET("recurring") suspend fun recurring():List<RecurringDto>
}
