package com.driveworkspace.uploader

import android.content.Context
import com.driveworkspace.uploader.api.DriveUploader
import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.internal.DriveUploaderImpl
import com.driveworkspace.uploader.internal.ResumableUploadEngine
import com.driveworkspace.uploader.internal.RetryPolicy
import com.driveworkspace.uploader.internal.checkpoint.BankStore
import com.driveworkspace.uploader.internal.checkpoint.DriveUploadDatabase
import com.driveworkspace.uploader.internal.checkpoint.LocalCheckpointStore
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/**
 * Manual-construction entry point for hosts that don't use Hilt.
 *
 * Hilt hosts should depend on [com.driveworkspace.uploader.di.DriveUploaderModule]
 * and inject [DriveUploader] directly.
 */
object DriveUploaderFactory {

    @JvmOverloads
    fun create(
        context: Context,
        initiator: UploadInitiator,
        config: DriveUploaderConfig = DriveUploaderConfig(),
        httpClient: OkHttpClient? = null,
    ): DriveUploader {
        val client = httpClient ?: defaultHttpClient(config)
        val db = DriveUploadDatabase.get(context)
        val checkpointStore = LocalCheckpointStore(db.checkpointDao())
        val bankStore = BankStore(db.bankedSessionDao())
        val retry = RetryPolicy(config)
        val engine = ResumableUploadEngine(client, checkpointStore, retry, config)
        return DriveUploaderImpl(initiator, engine, config, bankStore)
    }

    private fun defaultHttpClient(config: DriveUploaderConfig): OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(config.requestTimeout.inWholeMilliseconds, TimeUnit.MILLISECONDS)
            .writeTimeout(config.requestTimeout.inWholeMilliseconds, TimeUnit.MILLISECONDS)
            .readTimeout(config.requestTimeout.inWholeMilliseconds, TimeUnit.MILLISECONDS)
            .retryOnConnectionFailure(false) // engine has its own retry policy
            .build()
}
