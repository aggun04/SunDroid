package com.sundroid.host

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkRequest
import android.os.Bundle
import android.provider.Settings
import android.util.DisplayMetrics
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.sundroid.host.databinding.ActivityMainBinding
import com.sundroid.host.service.ScreenCaptureService
import com.sundroid.host.service.SunDroidAccessibilityService
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Collections

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var mediaProjectionManager: MediaProjectionManager
    private var currentPrimaryIp: String? = null

    private var connectivityManager: ConnectivityManager? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    private val screenCaptureLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startScreenCapture(result.resultCode, result.data!!)
        } else {
            Toast.makeText(this, "Izin perekaman layar ditolak!", Toast.LENGTH_SHORT).show()
        }
    }

    data class NetworkIpInfo(
        val ifaceName: String,
        val label: String,
        val ip: String,
        val priority: Int
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager

        setupUI()
        updateIpDisplay()
        registerNetworkObserver()
    }

    override fun onResume() {
        super.onResume()
        updateIpDisplay()
        updateServiceStatus()
        updateAccessibilityStatus()
    }

    override fun onDestroy() {
        super.onDestroy()
        unregisterNetworkObserver()
    }

    private fun registerNetworkObserver() {
        try {
            val cm = connectivityManager ?: return
            val request = NetworkRequest.Builder().build()
            networkCallback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    runOnUiThread { updateIpDisplay() }
                }
                override fun onLost(network: Network) {
                    runOnUiThread { updateIpDisplay() }
                }
                override fun onCapabilitiesChanged(network: Network, caps: android.net.NetworkCapabilities) {
                    runOnUiThread { updateIpDisplay() }
                }
            }
            cm.registerNetworkCallback(request, networkCallback!!)
        } catch (e: Exception) {
            // Non-critical if callback registration fails
        }
    }

    private fun unregisterNetworkObserver() {
        try {
            networkCallback?.let {
                connectivityManager?.unregisterNetworkCallback(it)
            }
        } catch (e: Exception) {}
        networkCallback = null
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

        // Copy IP Button & Clickable IP Text
        val copyAction = View.OnClickListener {
            val ip = currentPrimaryIp
            if (!ip.isNullOrBlank()) {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("SunDroid IP", ip)
                clipboard.setPrimaryClip(clip)
                Toast.makeText(this, "IP $ip disalin ke clipboard! Siap dipaste di PC.", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Belum ada IP yang dapat disalin.", Toast.LENGTH_SHORT).show()
            }
        }
        binding.btnCopyIp.setOnClickListener(copyAction)
        binding.txtIpAddress.setOnClickListener(copyAction)

        // Refresh IP Button
        binding.btnRefreshIp.setOnClickListener {
            updateIpDisplay()
            Toast.makeText(this, "Mengecek ulang koneksi IP...", Toast.LENGTH_SHORT).show()
        }
    }

    private fun getAvailableIpAddresses(): List<NetworkIpInfo> {
        val list = mutableListOf<NetworkIpInfo>()
        try {
            val interfaces = Collections.list(NetworkInterface.getNetworkInterfaces())
            for (iface in interfaces) {
                if (!iface.isUp || iface.isLoopback) continue
                val addrs = Collections.list(iface.inetAddresses)
                for (addr in addrs) {
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val hostIp = addr.hostAddress ?: continue
                        val name = iface.name.lowercase()

                        // Determine friendly interface label and priority
                        val (label, priority) = when {
                            name.startsWith("wlan") -> Pair("Wi-Fi ($name)", 1)
                            name.startsWith("ap") || name.startsWith("softap") -> Pair("Hotspot HP ($name)", 2)
                            name.startsWith("rndis") || name.startsWith("usb") -> Pair("USB Tethering ($name)", 3)
                            name.startsWith("eth") -> Pair("Ethernet ($name)", 4)
                            name.startsWith("p2p") -> Pair("Wi-Fi Direct ($name)", 5)
                            else -> Pair("Jaringan ($name)", 6)
                        }

                        list.add(NetworkIpInfo(iface.name, label, hostIp, priority))
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        // Sort by priority (Wi-Fi first, then Hotspot, then USB, etc.)
        return list.sortedBy { it.priority }
    }

    private fun updateIpDisplay() {
        val ipList = getAvailableIpAddresses()

        if (ipList.isNotEmpty()) {
            val primary = ipList[0]
            currentPrimaryIp = primary.ip
            binding.txtIpBadge.text = "Alamat IP HP [ ${primary.label} ]:"
            binding.txtIpAddress.text = primary.ip
            binding.txtIpAddress.setTextColor(ContextCompat.getColor(this, R.color.text_white))

            if (ipList.size > 1) {
                val secondaries = ipList.drop(1).joinToString(" | ") { "${it.label}: ${it.ip}" }
                binding.txtSecondaryIp.text = "IP Alternatif: $secondaries"
                binding.txtSecondaryIp.visibility = View.VISIBLE
            } else {
                binding.txtSecondaryIp.visibility = View.GONE
            }
        } else {
            currentPrimaryIp = null
            binding.txtIpBadge.text = "Status Jaringan:"
            binding.txtIpAddress.text = getString(R.string.no_ip_found)
            binding.txtIpAddress.setTextColor(ContextCompat.getColor(this, R.color.accent))
            binding.txtSecondaryIp.visibility = View.GONE
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
