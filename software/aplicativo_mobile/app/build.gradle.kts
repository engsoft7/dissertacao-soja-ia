plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

kotlin {
    jvmToolchain(17)
}

android {
    namespace = "com.agrointeligencia.app"
    compileSdk = 37

    
    val keystoreFile = rootProject.file("keystore.properties")
    val keystoreProps = java.util.Properties()
    if (keystoreFile.exists()) keystoreProps.load(keystoreFile.inputStream())

    signingConfigs {
        create("release") {
            storeFile = file(keystoreProps.getProperty("storeFile", "../agro_playstore.jks"))
            storePassword = keystoreProps.getProperty("storePassword", "")
            keyAlias = keystoreProps.getProperty("keyAlias", "")
            keyPassword = keystoreProps.getProperty("keyPassword", "")
        }
    }

    defaultConfig {
        applicationId = "com.agrointeligencia.app"
        minSdk = 26
        targetSdk = 37
        versionCode = 11
        versionName = "2.1.4"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (file("../agro_playstore.jks").exists()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
        debug {
            // Suffix removed to avoid Android Studio Intent launch mismatch
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    
    // Retrofit (Network)
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    
    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Extended Icons
    implementation(libs.androidx.material.icons.extended)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)

    androidTestImplementation(platform(libs.androidx.compose.bom))
    debugImplementation(platform(libs.androidx.compose.bom))

    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}
