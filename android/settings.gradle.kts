pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
        // The Android Gradle plugin lives in google(); only needed with -PwithApp=true.
        if (providers.gradleProperty("withApp").orNull == "true") google()
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
