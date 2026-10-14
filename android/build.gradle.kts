// Top-level build file. Everything app-specific lives in app/build.gradle.kts and
// every version lives in gradle/libs.versions.toml, so a dependency bump is a
// one-line change in one file.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
}
