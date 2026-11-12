package com.sundroid.host.encoder

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Bundle
import android.util.Log
import android.view.Surface

class VideoEncoder(
    private val width: Int,
    private val height: Int,
    private val fps: Int,
    private val bitrate: Int,
    private val onHeaderConfig: ((ByteArray) -> Unit)? = null,
    private val onPacketEncoded: (ByteArray, Int, Int) -> Unit
) {
    private var mediaCodec: MediaCodec? = null
    var inputSurface: Surface? = null
        private set

    @Volatile var cachedHeader: ByteArray? = null
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
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1) // 1 second I-frame interval
                setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)
                setLong(MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER, 1000000L / fps)

                // Prepend SPS/PPS to every IDR sync frame for fast Wi-Fi recovery
                try {
                    setInteger(MediaFormat.KEY_PREPEND_HEADER_TO_SYNC_FRAMES, 1)
                } catch (e: Exception) {}
                try {
                    setInteger("prepend-sps-pps-to-idr-frames", 1)
                } catch (e: Exception) {}
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

    fun requestKeyFrame() {
        try {
            val params = Bundle().apply {
                putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME, 0)
            }
            mediaCodec?.setParameters(params)
            Log.d(TAG, "Requested instant IDR Keyframe from MediaCodec")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to request sync frame: ${e.message}")
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

                        val isConfig = (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0

                        if (isConfig) {
                            // SPS/PPS Configuration NAL units
                            val header = ByteArray(bufferInfo.size)
                            outputBuffer.get(header)
                            cachedHeader = header
                            onHeaderConfig?.invoke(header)
                            Log.i(TAG, "Captured SPS/PPS Codec Header (${header.size} bytes)")
                        } else {
                            if (bufferInfo.size <= tempBuffer.size) {
                                outputBuffer.get(tempBuffer, 0, bufferInfo.size)
                                onPacketEncoded(tempBuffer, 0, bufferInfo.size)
                            } else {
                                val bigBuffer = ByteArray(bufferInfo.size)
                                outputBuffer.get(bigBuffer)
                                onPacketEncoded(bigBuffer, 0, bigBuffer.size)
                            }
                        }
                    }
                    codec.releaseOutputBuffer(outputBufferIndex, false)
                } else if (outputBufferIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    // Extract SPS/PPS from output format if available
                    try {
                        val outputFormat = codec.outputFormat
                        val csd0 = outputFormat.getByteBuffer("csd-0") // SPS
                        val csd1 = outputFormat.getByteBuffer("csd-1") // PPS
                        if (csd0 != null && csd1 != null) {
                            val sps = ByteArray(csd0.remaining()).also { csd0.get(it); csd0.rewind() }
                            val pps = ByteArray(csd1.remaining()).also { csd1.get(it); csd1.rewind() }
                            val fullHeader = sps + pps
                            cachedHeader = fullHeader
                            onHeaderConfig?.invoke(fullHeader)
                            Log.i(TAG, "Extracted SPS/PPS from format change (${fullHeader.size} bytes)")
                        }
                    } catch (e: Exception) {
                        Log.d(TAG, "Could not extract csd from format: ${e.message}")
                    }
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
