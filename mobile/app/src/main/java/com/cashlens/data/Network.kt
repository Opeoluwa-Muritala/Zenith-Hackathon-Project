package com.cashlens.data
import com.cashlens.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import okhttp3.MediaType.Companion.toMediaType
class TokenStore { var accessToken:String?=null }
fun api(store:TokenStore):CashlensApi { val client=OkHttpClient.Builder().addInterceptor(Interceptor { chain -> val request=chain.request().newBuilder();store.accessToken?.let { request.header("Authorization","Bearer $it") };chain.proceed(request.build()) }).build();return Retrofit.Builder().baseUrl(BuildConfig.BASE_URL).client(client).addConverterFactory(Json { ignoreUnknownKeys=true }.asConverterFactory("application/json".toMediaType())).build().create(CashlensApi::class.java) }
