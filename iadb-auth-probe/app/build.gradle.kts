plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.cyccc038.esauthprobe"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.cyccc038.esauthprobe"
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }
}

dependencies {
    implementation(files("libs/aidl-release.aar"))
    implementation(files("libs/api-release.aar"))
    implementation(files("libs/provider-release.aar"))
    implementation(files("libs/shared-release.aar"))
}
