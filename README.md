# ☀️ SunDroid — Reverse Sunshine & Moonlight (Remote HP dari PC)

**SunDroid** adalah solusi *remote control* dan *screen mirroring* Android-ke-PC ultra-low latency (< 15–20ms) yang memungkinkan kamu mengendalikan HP Android secara langsung dari PC Windows menggunakan mouse, keyboard, dan tombol klik layaknya Sunshine & Moonlight secara terbalik.

---

## ⚡ Fitur Utama & Pembaruan

1. **Dashboard GUI Modern & Klik-able (PC Control Center):**
   * Tampilan visual dark-mode yang elegan dan ramah pengguna.
   * Pilih metode koneksi cukup dengan sekali klik: **Mode USB (ADB)** atau **Mode Wi-Fi**.
   * Fitur **"Pindai HP via USB (Scan ADB)"** & **"Forward Port Otomatis"**.
   * Fitur **"Tes Ping Port HP"** untuk memverifikasi kesiapan host HP sebelum menghubungkan.
   * Fitur **"Cari HP Otomatis"** yang memindai subnet lokal untuk menemukan IP HP tanpa perlu mengetik manual.
   * Riwayat IP tersimpan otomatis (*IP memory*).
   * **Tidak Pernah Menutup Aplikasi Saat Gagal Koneksi:** Jika IP salah atau host HP belum aktif, aplikasi tetap terbuka dan menampilkan panduan diagnostik solutif agar kamu bisa langsung mencoba lagi.

2. **Toolbar Navigasi Interaktif di Layar Streaming (Clickable On-Screen Buttons):**
   * Di layar streaming PC kini tersedia bilah tombol navigasi yang dapat diklik langsung dengan mouse:
     * `◀ Back` | `⚪ Home` | `▢ Recents` | `⚡ Power` | `🔉 Vol -` | `🔊 Vol +` | `🎮 Game Mode` | `⛶ Fullscreen` | `❌ Keluar`
   * Dialog overlay saat koneksi terputus: tombol **"🔄 Sambung Ulang"** atau **"⬅ Menu Utama"**.

3. **Perbaikan Total Koneksi Wi-Fi & Deteksi IP HP:**
   * **Deteksi IP Akurat di HP:** Menggunakan pemindaian antarmuka jaringan (*NetworkInterface*) yang andal di semua versi Android (Android 9 hingga 15+). Mendukung Wi-Fi (`wlan0`), Hotspot HP (`ap0`), dan USB Tethering (`rndis0`).
   * Tombol **"Salin IP"** dan **"Refresh"** langsung di aplikasi HP.
   * **Streaming Wi-Fi Mulus & Instan:** Server Android otomatis meng-cache header *SPS/PPS* H.264 dan meminta *IDR keyframe* instan saat PC terhubung, sehingga PyAV di PC langsung menerima gambar tanpa blank/error.
   * Perlindungan **WifiLock & WakeLock** performa tinggi di HP untuk mencegah sleep mode dan lonjakan latency jaringan.

4. **Hardware H.264 Encoder (Zero-Copy):**
   * Menggunakan chip GPU Android (`MediaCodec`) untuk streaming 60 FPS / 120 FPS tanpa membuat HP panas dan baterai tetap awet.

5. **Kontrol Penuh Mouse & Keyboard:**
   * **Klik Kiri:** Sentuh layar (Tap) & Geser (Drag).
   * **Klik Kanan:** Tombol **BACK** Android.
   * **Klik Tengah:** Tombol **HOME** Android.
   * **Scroll Roda Mouse:** Swipe / Gulir layar atas & bawah.
   * **Ketik Keyboard:** Ketikan teks dari PC langsung masuk ke HP.

6. **Mode Game Keymapper (`F1`):**
   * Ubah tombol **W, A, S, D, Space, J, K** menjadi analog dan tombol skill di layar HP untuk bermain game mobile (Mobile Legends, PUBG, COD, Genshin) langsung dari PC!

7. **No Root Required:** Menggunakan layanan Aksesibilitas bawaan Android (`AccessibilityService`) sehingga dapat digunakan di semua merk HP Android tanpa perlu root.

---

## 💻 Panduan Menjalankan PC (Windows)

1. Buka folder `SunDroid/pc/` di Windows kamu.
2. Klik ganda file:
   ```cmd
   run_sundroid.bat
   ```
   *(Script otomatis membuat environment Python, menginstall dependensi Pygame & PyAV, lalu membuka SunDroid Control Center).*
3. Di SunDroid Control Center:
   * **Mode USB:** Klik tombol **"Pindai HP via USB"**, lalu klik **"HUBUNGKAN KE HP"**.
   * **Mode Wi-Fi:** Masukkan alamat IP yang tertera di aplikasi HP (atau gunakan tombol **"Cari HP Otomatis"**), lalu klik **"HUBUNGKAN KE HP"**.

---

## 📱 Panduan Build & Install Android

1. Buka folder `SunDroid/android/` di **Android Studio**.
2. Hubungkan HP kamu dengan kabel USB (pastikan USB Debugging aktif).
3. Klik tombol **Run / Play (Shift + F10)** untuk menginstall **SunDroid Host** ke HP.
4. Di HP:
   * Buka aplikasi **SunDroid Host**.
   * Klik tombol **"Aktifkan Izin Aksesibilitas"** lalu aktifkan *SunDroid Host* di menu Aksesibilitas HP.
   * Periksa alamat IP yang muncul di layar (bisa disalin dengan tombol **"Salin IP"**).
   * Klik **"Mulai Remote Host"** dan pilih *Start now*.

---

## 🎮 Tombol Pintasan (Hotkeys) di PC

| Tombol / Aksi | Fungsi |
|---|---|
| **Klik Toolbar On-Screen** | Tombol navigasi virtual (Back, Home, Recents, Power, Vol, Game) |
| **F1** | Aktifkan / Matikan **Mode Gaming Keymapper** (WASD & Mouse) |
| **F2** | Kunci / Nyalakan Layar HP (Power Button) |
| **F3 / F4** | Volume Turun / Naik |
| **F11** | Layar Penuh (Fullscreen) |
| **Klik Kanan** | Tombol Back |
| **Klik Tengah** | Tombol Home |
