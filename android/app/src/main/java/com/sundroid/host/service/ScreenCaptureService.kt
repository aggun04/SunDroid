package com.sundroid.host.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import com.sundroid.host.encoder.VideoEncoder
import java.io.OutputStream
import java.net.ServerSocket
import java.net.Socket

class ScreenCaptureService : Service() {

    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var videoEncoder: VideoEncoder? = null
    private var controlServer: ControlServer? = null

    private var videoServerSocket: ServerSocket? = null
    @Volatile private var isRunning = false
    private var activeVideoClient: Socket? = null
    private var videoOutputStream: OutputStream? = null

    companion object {
        private const val TAG = "ScreenCaptureService"
        private const val NOTIF_CHANNEL_ID = "sundroid_service_channel"
        private const val NOTIF_ID = 1001

        const val EXTRA_RESULT_CODE = "extra_result_code"
        const val EXTRA_RESULT_DATA = "extra_result_data"
        const val EXTRA_WIDTH = "extra_width"
        const val EXTRA_HEIGHT = "extra_height"
        const val EXTRA_BITRATE = "extra_bitrate"
        const val EXTRA_FPS = "extra_fps"

        var isServiceActive = false
            private set
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
        val resultData = intent.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        val width = intent.getIntExtra(EXTRA_WIDTH, 1080)
        val height = intent.getIntExtra(EXTRA_HEIGHT, 1920)
        val bitrate = intent.getIntExtra(EXTRA_BITRATE, 8_000_000)
        val fps = intent.getIntExtra(EXTRA_FPS, 60)

        if (resultCode != Activity.RESULT_OK || resultData == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(NOTIF_ID, createNotification())
        isServiceActive = true
        isRunning = true

        // 1. Start Control Server (Port 7101)
        controlServer = ControlServer(this, 7101).apply { start() }

        // 2. Start Video Server & Pipeline (Port 7100)
        startVideoPipeline(resultCode, resultData, width, height, fps, bitrate)

        return START_STICKY
    }

    private fun startVideoPipeline(resultCode: Int, resultData: Intent, width: Int, height: Int, fps: Int, bitrate: Int) {
        Thread({
            try {
                videoServerSocket = ServerSocket(7100).apply { reuseAddress = true }
                Log.i(TAG, "Video server listening on port 7100...")

                // Obtain MediaProjection
                val mpManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                mediaProjection = mpManager.getMediaProjection(resultCode, resultData)

                // Initialize Encoder
                videoEncoder = VideoEncoder(width, height, fps, bitrate) { buffer, offset, length ->
                    try {
                        videoOutputStream?.write(buffer, offset, length)
                    } catch (e: Exception) {
                        Log.d(TAG, "Client disconnected from video socket")
                        disconnectVideoClient()
                    }
                }
                videoEncoder?.start()

                // Create Virtual Display targeting encoder input surface
                val density = resources.displayMetrics.densityDpi
                virtualDisplay = mediaProjection?.createVirtualDisplay(
                    "SunDroidDisplay",
                    width,
                    height,
                    density,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                    videoEncoder?.inputSurface,
                    null,
                    null
                )

                // Accept loop for PC client
                while (isRunning) {
                    val client = videoServerSocket?.accept() ?: break
                    client.tcpNoDelay = true
                    client.sendBufferSize = 64 * 1024
                    activeVideoClient = client
                    videoOutputStream = client.getOutputStream()
                    Log.i(TAG, "PC Client connected to Video stream: ${client.inetAddress.hostAddress}")
                }
            } catch (e: Exception) {
                if (isRunning) {
                    Log.e(TAG, "Video pipeline error: ${e.message}")
                }
            }
        }, "VideoServerThread").start()
    }

    private fun disconnectVideoClient() {
        try {
            videoOutputStream?.close()
        } catch (e: Exception) {}
        try {
            activeVideoClient?.close()
        } catch (e: Exception) {}
        videoOutputStream = null
        activeVideoClient = null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIF_CHANNEL_ID,
                "SunDroid Remote Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Streaming layar HP ke PC"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, NOTIF_CHANNEL_ID)
            .setContentTitle("☀️ SunDroid Host Aktif")
            .setContentText("Siap terhubung ke PC (Port: 7100, 7101)")
            .setSmallIcon(android.R.drawable.ic_menu_slideshow)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        isServiceActive = false

        disconnectVideoClient()
        try {
            videoServerSocket?.close()
        } catch (e: Exception) {}

        controlServer?.stop()
        controlServer = null

        virtualDisplay?.release()
        virtualDisplay = null

        videoEncoder?.stop()
        videoEncoder = null

        mediaProjection?.stop()
        mediaProjection = null

        Log.i(TAG, "ScreenCaptureService destroyed.")
    }
}
