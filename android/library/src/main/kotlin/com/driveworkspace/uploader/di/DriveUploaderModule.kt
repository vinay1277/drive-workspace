package com.driveworkspace.uploader.di

import android.content.Context
import com.driveworkspace.uploader.DriveUploaderFactory
import com.driveworkspace.uploader.api.DriveUploader
import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadInitiator
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt wiring for hosts that opt in.
 *
 * The host must provide a binding for [UploadInitiator]. Everything else is
 * provided here. Hosts that want to override [DriveUploaderConfig] can declare
 * their own `@Provides DriveUploaderConfig` in a higher-priority module.
 */
@Module
@InstallIn(SingletonComponent::class)
object DriveUploaderModule {

    @Provides
    @Singleton
    fun provideDefaultConfig(): DriveUploaderConfig = DriveUploaderConfig()

    @Provides
    @Singleton
    fun provideDriveUploader(
        @ApplicationContext context: Context,
        initiator: UploadInitiator,
        config: DriveUploaderConfig,
    ): DriveUploader = DriveUploaderFactory.create(context, initiator, config)
}
