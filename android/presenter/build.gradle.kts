plugins {
    kotlin("jvm")
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    api(project(":sim"))
    testImplementation(kotlin("test"))
}

// Tests reuse the engine's conformance vectors and its test-only JSON reader (MiniJson). They
// are read in place from :sim's test output, never copied, so the repo holds one copy of each.
evaluationDependsOn(":sim")

dependencies {
    val simTest = rootProject.project(":sim").extensions.getByType<SourceSetContainer>()["test"]
    testImplementation(simTest.output)
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "failed", "skipped")
        showStandardStreams = false
    }
}
