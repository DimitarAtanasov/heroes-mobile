pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
        // The Android Gradle plugin lives in google(); only needed with -PwithApp=true.
        if (providers.gradleProperty("withApp").orNull == "true") google()
    }
    // Plugin versions are declared ONCE, here. Modules and the root request plugins without a
    // version; declaring a version in two places makes Gradle fail with "plugin is already on the
    // classpath with an unknown version". Registering a version does not resolve the plugin, so the
    // Android plugin is still fetched only when :app is included (-PwithApp=true).
    plugins {
        id("org.jetbrains.kotlin.jvm") version "2.0.21"
        id("org.jetbrains.kotlin.android") version "2.0.21"
        id("org.jetbrains.kotlin.plugin.compose") version "2.0.21"
        id("com.android.application") version "8.7.3"
    }
}
dependencyResolutionManagement {
    repositories {
        mavenCentral()
        if (providers.gradleProperty("withApp").orNull == "true") google()
    }
}

rootProject.name = "heroes-mobile"
include(":sim")
// The Android app needs dl.google.com (AGP, androidx). Opt in: gradle -PwithApp=true :app:assembleDebug
if (providers.gradleProperty("withApp").orNull == "true") include(":app")
