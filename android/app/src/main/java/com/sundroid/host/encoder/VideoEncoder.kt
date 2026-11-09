package com.sundroid.host.encoder

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.util.Log
import android.view.Surface
import java.io.OutputStream

class VideoEncoder(
    private val width: Int,
    private val height: Int,
    private val fps: Int,
    private val bitrate: Int,
    private val onPacketEncoded: (ByteArray, Int, Int) -> Unit
) {
    private var mediaCodec: MediaCodec? = null
    var inputSurface: Surface? = null
        private set

    @Volatile private var isEncoding = false
    private var drainThread: Thread? = null

    companion object {
        private const val TAG = "VideoEncoder"
        private const val MIME_TYPE = MediaFormat.MIMETYPE_VIDEO_AVC
    }

    fun start() {
        if (isEncoding) return

        try {
            val format = MediaFormat.createVideoFormat(MIME_TYPE, width, height).apply {
                setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface)
                setInteger(MediaFormat.KEY_BIT_RATE, bitrate)
                setInteger(MediaFormat.KEY_FRAME_RATE, fps)
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1) // 1 second I-frame interval for fast recovery
                setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)
                setLong(MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER, 1000000L / fps)
            }

            mediaCodec = MediaCodec.createEncoderByType(MIME_TYPE).apply {
                configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
                inputSurface = createInputSurface()
                start()
            }

            isEncoding = true
            drainThread = Thread({ drainLoop() }, "EncoderDrainThread").apply { start() }
            Log.i(TAG, "Hardware H.264 Encoder started: ${width}x${height} @ ${fps}fps, ${bitrate / 1000}kbps")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start MediaCodec: ${e.message}")
            stop()
        }
    }

    private fun drainLoop() {
        val bufferInfo = MediaCodec.BufferInfo()
        val tempBuffer = ByteArray(256 * 1024)

        while (isEncoding) {
            val codec = mediaCodec ?: break
            try {
                val outputBufferIndex = codec.dequeueOutputBuffer(bufferInfo, 10_000)
                if (outputBufferIndex >= 0) {
                    val outputBuffer = codec.getOutputBuffer(outputBufferIndex)
                    if (outputBuffer != null && bufferInfo.size > 0) {
                        outputBuffer.position(bufferInfo.offset)
                        outputBuffer.limit(bufferInfo.offset + bufferInfo.size)

                        if (bufferInfo.size <= tempBuffer.size) {
                            outputBuffer.get(tempBuffer, 0, bufferInfo.size)
                            onPacketEncoded(tempBuffer, 0, bufferInfo.size)
                        } else {
                            val bigBuffer = ByteArray(bufferInfo.size)
                            outputBuffer.get(bigBuffer)
                            onPacketEncoded(bigBuffer, 0, bigBuffer.size)
                        }
                    }
                    codec.releaseOutputBuffer(outputBufferIndex, false)
                }
            } catch (e: Exception) {
                if (isEncoding) {
                    Log.e(TAG, "Drain error: ${e.message}")
                }
            }
        }
    }

    fun stop() {
        isEncoding = false
        try {
            drainThread?.join(500)
        } catch (e: Exception) {}
        drainThread = null

        try {
            mediaCodec?.stop()
            mediaCodec?.release()
        } catch (e: Exception) {}
        mediaCodec = null

        try {
            inputSurface?.release()
        } catch (e: Exception) {}
        inputSurface = null
        Log.i(TAG, "MediaCodec Encoder stopped")
    }
}
