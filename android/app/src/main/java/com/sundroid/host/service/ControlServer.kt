package com.sundroid.host.service

import android.content.Context
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket
import kotlin.math.abs

class ControlServer(
    private val context: Context,
    private val port: Int = 7101
) {
    private var serverSocket: ServerSocket? = null
    @Volatile private var isRunning = false
    private var serverThread: Thread? = null

    // Tracking active touch positions for swipe calculations
    private val touchStartMap = mutableMapOf<Int, Pair<Float, Float>>()
    private val touchLastMap = mutableMapOf<Int, Pair<Float, Float>>()

    private val screenWidth: Float
    private val screenHeight: Float

    companion object {
        private const val TAG = "ControlServer"
    }

    init {
        val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val metrics = DisplayMetrics()
        wm.defaultDisplay.getRealMetrics(metrics)
        screenWidth = metrics.widthPixels.toFloat()
        screenHeight = metrics.heightPixels.toFloat()
    }

    fun start() {
        if (isRunning) return
        isRunning = true
        serverThread = Thread({ runServer() }, "ControlServerThread").apply { start() }
        Log.i(TAG, "Control Server listening on port $port (Screen: ${screenWidth.toInt()}x${screenHeight.toInt()})")
    }

    private fun runServer() {
        try {
            serverSocket = ServerSocket(port).apply {
                reuseAddress = true
            }

            while (isRunning) {
                val client = serverSocket?.accept() ?: break
                client.tcpNoDelay = true
                Log.i(TAG, "PC Client connected to Control channel from ${client.inetAddress.hostAddress}")
                handleClient(client)
            }
        } catch (e: Exception) {
            if (isRunning) {
                Log.e(TAG, "Control Server socket error: ${e.message}")
            }
        }
    }

    private fun handleClient(socket: Socket) {
        val a11y = SunDroidAccessibilityService.instance
        try {
            val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
            while (isRunning) {
                val line = reader.readLine() ?: break
                if (line.isNotBlank()) {
                    processCommand(line.trim(), a11y)
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "Control client connection closed: ${e.message}")
        } finally {
            try {
                socket.close()
            } catch (e: Exception) {}
        }
    }

    private fun processCommand(cmd: String, a11y: SunDroidAccessibilityService?) {
        val parts = cmd.split(" ")
        if (parts.isEmpty()) return

        when (parts[0]) {
            "T" -> { // Touch Event: T <action: D/M/U> <id> <x_pct> <y_pct>
                if (parts.size >= 5) {
                    val action = parts[1]
                    val id = parts[2].toIntOrNull() ?: 0
                    val xPct = parts[3].toFloatOrNull() ?: 0f
                    val yPct = parts[4].toFloatOrNull() ?: 0f

                    val px = xPct * screenWidth
                    val py = yPct * screenHeight

                    when (action) {
                        "D" -> {
                            touchStartMap[id] = Pair(px, py)
                            touchLastMap[id] = Pair(px, py)
                        }
                        "M" -> {
                            touchLastMap[id] = Pair(px, py)
                        }
                        "U" -> {
                            val start = touchStartMap[id] ?: Pair(px, py)
                            val end = Pair(px, py)
                            touchStartMap.remove(id)
                            touchLastMap.remove(id)

                            val dist = abs(end.first - start.first) + abs(end.second - start.second)
                            if (dist < 20f) {
                                // Short distance -> Tap
                                a11y?.injectTap(end.first, end.second)
                            } else {
                                // Swiped distance -> Gesture Swipe
                                a11y?.injectSwipe(start.first, start.second, end.first, end.second, 120)
                            }
                        }
                    }
                }
            }
            "S" -> { // Scroll: S <x_pct> <y_pct> <delta_y>
                if (parts.size >= 4) {
                    val xPct = parts[1].toFloatOrNull() ?: 0.5f
                    val yPct = parts[2].toFloatOrNull() ?: 0.5f
                    val deltaY = parts[3].toFloatOrNull() ?: 0.1f

                    val startX = xPct * screenWidth
                    val startY = yPct * screenHeight
                    val endY = (startY - (deltaY * screenHeight)).coerceIn(50f, screenHeight - 50f)

                    a11y?.injectSwipe(startX, startY, startX, endY, 80)
                }
            }
            "CMD" -> { // System Commands: CMD BACK / CMD HOME / CMD POWER
                if (parts.size >= 2) {
                    val act = parts[1]
                    a11y?.injectGlobalAction(act)
                }
            }
        }
    }

    fun stop() {
        isRunning = false
        try {
            serverSocket?.close()
        } catch (e: Exception) {}
        serverSocket = null
        try {
            serverThread?.join(500)
        } catch (e: Exception) {}
        serverThread = null
    }
}
