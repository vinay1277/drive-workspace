plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.driveworkspace.uploader"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
        consumerProguardFiles("consumer-rules.pro")
        // Android instrumentation tests live under src/androidTest. The
        // single instrumented test today is the ADR-0010 main-thread
        // dispatcher check; see MainDispatcherInstrumentationTest.
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

dependencies {
    // OkHttp powers the resumable PUT engine
    implementation(libs.okhttp.core)
    implementation(libs.okhttp.logging)

    // Room for the library-owned checkpoint database
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    // Hilt (consumers may use the provided module or wire manually)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    // WorkManager (optional path; the host may schedule DriveUploadWorker)
    implementation(libs.work.runtime.ktx)
    implementation(libs.hilt.work)
    ksp(libs.hilt.compiler.androidx)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Structured logging
    implementation(libs.timber)

    coreLibraryDesugaring(libs.android.desugar.jdk.libs)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.room.testing)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.androidx.junit)
    testImplementation(libs.robolectric)

    // Android instrumentation tests (ADR-0010 main-thread dispatcher check).
    // Run on a connected device/emulator via:
    //   ./gradlew :library:connectedDebugAndroidTest
    androidTestImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.okhttp.mockwebserver)
    androidTestImplementation(libs.kotlinx.coroutines.android)
    androidTestImplementation(libs.kotlinx.coroutines.test)
}
