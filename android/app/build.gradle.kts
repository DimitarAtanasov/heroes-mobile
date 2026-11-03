// Android app module. Included only with -PwithApp=true (needs the Google Maven repo).
plugins {
    id("com.android.application")
    kotlin("android")
    kotlin("plugin.compose")
}

// The three data packs the engine needs, plus the CRTRAITS column mapping the roster loader reads
// (assets path txt_maps/crtraits.json), are copied from the repo's data/ into generated assets, so only
// these files ship (not the whole data/ directory). creatures.json is a fixture pack for the replay
// pack hashes only; the battle roster is the player's own CRTRAITS.TXT. Edit data/, never the copies.
val h3Assets = layout.buildDirectory.dir("generated/h3assets")
val copyH3Data = tasks.register<Copy>("copyH3Data") {
    from(rootProject.layout.projectDirectory.dir("../data")) {
        include("rules.json", "battle_policy.json", "creatures.json", "txt_maps/crtraits.json")
    }
    into(h3Assets)
}

android {
    namespace = "h3.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "h3.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    sourceSets["main"].assets.srcDir(h3Assets)
}

// The packs must be copied before anything reads the merged assets (preBuild runs first).
tasks.configureEach {
    if (name == "preBuild" || (name.startsWith("merge") && name.endsWith("Assets"))) dependsOn(copyH3Data)
}

dependencies {
    implementation(project(":sim"))
    implementation(project(":presenter"))
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.runtime:runtime")
    implementation("androidx.activity:activity-compose:1.9.3")
}
