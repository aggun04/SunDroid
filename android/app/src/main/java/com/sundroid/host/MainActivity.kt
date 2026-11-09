package com.sundroid.host

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.wifi.WifiManager
import android.os.Bundle
import android.provider.Settings
import android.text.format.Formatter
import android.util.DisplayMetrics
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.sundroid.host.databinding.ActivityMainBinding
import com.sundroid.host.service.ScreenCaptureService
import com.sundroid.host.service.SunDroidAccessibilityService

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var mediaProjectionManager: MediaProjectionManager

    private val screenCaptureLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startScreenCapture(result.resultCode, result.data!!)
        } else {
            Toast.makeText(this, "Izin perekaman layar ditolak!", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager

        setupUI()
        updateIpDisplay()
    }

    override fun onResume() {
        super.onResume()
        updateServiceStatus()
        updateAccessibilityStatus()
    }

    private fun setupUI() {
        // Resolutions: 1080p, 720p, Native
        val resolutions = listOf("1080p (1080x1920) - 60 FPS", "720p (720x1280) - Ultra Satset", "Native Resolusi HP")
        binding.spnResolution.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, resolutions)

        // Bitrates
        val bitrates = listOf("8 Mbps (Rekomendasi)", "4 Mbps (Hemat)", "16 Mbps (High Quality)", "25 Mbps (Ultra)")
        binding.spnBitrate.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, bitrates)

        // Accessibility Button
        binding.btnAccessibility.setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
            Toast.makeText(this, "Cari dan aktifkan 'SunDroid Host'", Toast.LENGTH_LONG).show()
        }

        // Toggle Service Button
        binding.btnToggleService.setOnClickListener {
            if (ScreenCaptureService.isServiceActive) {
                stopScreenCapture()
            } else {
                val intent = mediaProjectionManager.createScreenCaptureIntent()
                screenCaptureLauncher.launch(intent)
            }
        }
    }

    private fun updateIpDisplay() {
        try {
            val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val ip = Formatter.formatIpAddress(wm.connectionInfo.ipAddress)
            binding.txtIpAddress.text = "IP Wi-Fi: $ip\nPort Video: 7100 | Port Kontrol: 7101"
        } catch (e: Exception) {
            binding.txtIpAddress.text = "IP Wi-Fi: Periksa koneksi Wi-Fi"
        }
    }

    private fun updateAccessibilityStatus() {
        val isA11yActive = SunDroidAccessibilityService.isServiceRunning()
        if (isA11yActive) {
            binding.btnAccessibility.text = "✅ Izin Aksesibilitas Aktif"
            binding.btnAccessibility.isEnabled = false
        } else {
            binding.btnAccessibility.text = "⚠️ Aktifkan Izin Aksesibilitas"
            binding.btnAccessibility.isEnabled = true
        }
    }

    private fun updateServiceStatus() {
        if (ScreenCaptureService.isServiceActive) {
            binding.txtStatus.text = getString(R.string.status_running)
            binding.txtStatus.setTextColor(ContextCompat.getColor(this, R.color.green_active))
            binding.btnToggleService.text = getString(R.string.btn_stop_service)
            binding.btnToggleService.setBackgroundColor(ContextCompat.getColor(this, R.color.red_stop))
        } else {
            binding.txtStatus.text = getString(R.string.status_idle)
            binding.txtStatus.setTextColor(ContextCompat.getColor(this, R.color.text_white))
            binding.btnToggleService.text = getString(R.string.btn_start_service)
            binding.btnToggleService.setBackgroundColor(ContextCompat.getColor(this, R.color.primary))
        }
    }

    private fun startScreenCapture(resultCode: Int, data: Intent) {
        val (width, height) = when (binding.spnResolution.selectedItemPosition) {
            1 -> Pair(720, 1280)
            2 -> {
                val metrics = DisplayMetrics()
                windowManager.defaultDisplay.getRealMetrics(metrics)
                Pair(metrics.widthPixels, metrics.heightPixels)
            }
            else -> Pair(1080, 1920)
        }

        val bitrate = when (binding.spnBitrate.selectedItemPosition) {
            1 -> 4_000_000
            2 -> 16_000_000
            3 -> 25_000_000
            else -> 8_000_000
        }

        val serviceIntent = Intent(this, ScreenCaptureService::class.java).apply {
            putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, resultCode)
            putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, data)
            putExtra(ScreenCaptureService.EXTRA_WIDTH, width)
            putExtra(ScreenCaptureService.EXTRA_HEIGHT, height)
            putExtra(ScreenCaptureService.EXTRA_BITRATE, bitrate)
            putExtra(ScreenCaptureService.EXTRA_FPS, 60)
        }

        ContextCompat.startForegroundService(this, serviceIntent)
        updateServiceStatus()
        Toast.makeText(this, "SunDroid Host aktif! Hubungkan dari PC.", Toast.LENGTH_SHORT).show()
    }

    private fun stopScreenCapture() {
        val serviceIntent = Intent(this, ScreenCaptureService::class.java)
        stopService(serviceIntent)
        updateServiceStatus()
        Toast.makeText(this, "SunDroid Host dinonaktifkan.", Toast.LENGTH_SHORT).show()
    }
}
