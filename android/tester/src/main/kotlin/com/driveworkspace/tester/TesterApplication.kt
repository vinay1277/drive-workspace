package com.driveworkspace.tester

import android.app.Application
import timber.log.Timber

class TesterApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        Timber.plant(Timber.DebugTree())
    }
}
