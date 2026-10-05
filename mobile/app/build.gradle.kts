plugins { alias(libs.plugins.android.application); alias(libs.plugins.kotlin.android); alias(libs.plugins.kotlin.compose); alias(libs.plugins.serialization); alias(libs.plugins.ktlint) }
android { namespace="com.cashlens"; compileSdk=36
    defaultConfig { applicationId="com.cashlens"; minSdk=26; targetSdk=36; versionCode=1; versionName="0.1"; buildConfigField("String","BASE_URL","\"http://10.0.2.2:8000/\"") }
    buildFeatures { compose=true; buildConfig=true }
    compileOptions { sourceCompatibility=JavaVersion.VERSION_17; targetCompatibility=JavaVersion.VERSION_17 }
}
dependencies {
    implementation(platform(libs.androidx.compose.bom)); implementation(libs.compose.ui); implementation(libs.compose.preview); implementation(libs.material3); debugImplementation(libs.compose.tooling)
    implementation(libs.activity.compose); implementation(libs.lifecycle.viewmodel); implementation(libs.navigation); implementation(libs.koin.android); implementation(libs.koin.compose); implementation(libs.retrofit); implementation(libs.retrofit.json); implementation(libs.okhttp); implementation(libs.serialization.json)
}
