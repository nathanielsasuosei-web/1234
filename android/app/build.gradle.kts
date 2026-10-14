import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

/**
 * Release signing, configured from either
 *
 *  - `android/keystore.properties` (local machine, git-ignored), or
 *  - the `ANDROID_KEYSTORE_*` environment variables (GitHub Actions secrets).
 *
 * When neither is present the release variant simply stays unsigned, so a plain
 * `./gradlew assembleDebug` — or the CI check — never needs a keystore.
 */
val keystoreProperties = Properties().apply {
    val file = rootProject.file("keystore.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun signingValue(property: String, environment: String): String? =
    keystoreProperties.getProperty(property) ?: System.getenv(environment)

val releaseKeystorePath = signingValue("storeFile", "ANDROID_KEYSTORE_PATH")

android {
    namespace = "com.meetbeatz.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.meetbeatz.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"

        // The SHA-256 fingerprint printed by `./gradlew signingReport` is the one that has
        // to appear in https://meetbeatz.com/.well-known/assetlinks.json for the app to open
        // links without the browser address bar. See docs/ANDROID_APP.md.
    }

    signingConfigs {
        create("release") {
            if (releaseKeystorePath != null) {
                storeFile = rootProject.file(releaseKeystorePath)
                storePassword = signingValue("storePassword", "ANDROID_KEYSTORE_PASSWORD")
                keyAlias = signingValue("keyAlias", "ANDROID_KEY_ALIAS")
                keyPassword = signingValue("keyPassword", "ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            // Same application id as the release build on purpose: Site-settings and
            // digital-asset-link verification are matched on application id plus signing
            // certificate, so a suffixed debug id could never verify its own deep links.
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            if (releaseKeystorePath != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            // Guava (pulled in by android-browser-helper) ships these licence files.
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    lint {
        // Lint findings should never be the reason a release cannot be cut from CI.
        abortOnError = false
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    // The Trusted Web Activity runtime: provider selection, splash screen, delegation
    // service, shortcuts and the WebView fallback plumbing.
    implementation(libs.android.browser.helper)
    implementation(libs.androidx.browser)
    implementation(libs.androidx.core.ktx)
}
