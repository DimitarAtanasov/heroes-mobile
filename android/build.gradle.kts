// The Android Gradle plugin must be on the ROOT build's classpath, next to the Kotlin plugin, so both
// share one class loader (otherwise the Kotlin Android plugin cannot see AGP classes such as
// com.android.build.gradle.api.BaseVariant). It is added only with -PwithApp=true, so the default
// build (:sim only) never needs the Google Maven repository.
buildscript {
    if (providers.gradleProperty("withApp").orNull == "true") {
        repositories {
            google()
            mavenCentral()
        }
        dependencies {
            classpath("com.android.tools.build:gradle:8.7.3")
        }
    }
}

plugins {
    kotlin("jvm") apply false
}
