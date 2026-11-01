pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
        // The Android Gradle plugin lives in google(); only needed with -PwithApp=true.
        if (providers.gradleProperty("withApp").orNull == "true") google()
    }
    // Plugin versions are declared ONCE, here. Modules and the root request plugins without a
    // version; declaring a version in two places makes Gradle fail with "plugin is already on the
    // classpath with an unknown version". The Android Gradle plugin is NOT listed here: it is
    // put on the root classpath in build.gradle.kts, only when -PwithApp=true.
    plugins {
        id("org.jetbrains.kotlin.jvm") version "2.0.21"
        id("org.jetbrains.kotlin.android") version "2.0.21"
        id("org.jetbrains.kotlin.plugin.compose") version "2.0.21"
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
