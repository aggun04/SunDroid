# ☀️ SunDroid — Reverse Sunshine & Moonlight (Remote HP dari PC)

**SunDroid** adalah solusi *remote control* dan *screen mirroring* Android-ke-PC ultra-low latency (< 15–20ms) yang memungkinkan kamu mengendalikan HP Android kamu secara langsung dari PC Windows menggunakan mouse, keyboard, dan stik gamepad layaknya Sunshine & Moonlight secara terbalik.

---

## ⚡ Fitur Utama

1. **Hardware H.264 Encoder (Zero-Copy):**
   * Menggunakan chip GPU Android (`MediaCodec`) untuk streaming 60 FPS / 120 FPS tanpa membuat HP panas dan baterai tetap awet.
2. **Kontrol Penuh Mouse & Keyboard:**
   * **Klik Kiri:** Sentuh layar (Tap) & Geser (Drag).
   * **Klik Kanan:** Tombol **BACK** Android.
   * **Klik Tengah:** Tombol **HOME** Android.
   * **Scroll Roda Mouse:** Swipe / Gulir layar atas & bawah.
   * **Ketik Keyboard:** Ketikan teks dari PC langsung masuk ke HP.
3. **Mode Game Keymapper (`F1`):**
   * Ubah tombol **W, A, S, D, Space, J, K** menjadi analog dan tombol skill di layar HP untuk bermain game mobile (Mobile Legends, PUBG, COD, Genshin) langsung dari PC!
4. **Koneksi Dual-Mode:**
   * **Mode USB (ADB):** Latensi ~10ms (nyaris tanpa delay), stabil 100%, anti-interferensi sinyal.
   * **Mode Wi-Fi:** Wireless praktis tanpa kabel.
5. **No Root Required:** Menggunakan layanan Aksesibilitas bawaan Android (`AccessibilityService`) sehingga dapat digunakan di semua merk HP Android tanpa perlu root.

---

## 💻 Panduan Menjalankan PC (Windows)

1. Buka folder `sundroid/pc/` di Windows kamu.
2. Klik ganda file:
   ```cmd
   run_sundroid.bat
   ```
   *(Script otomatis membuat environment Python, menginstall dependensi Pygame & PyAV, dan membuka layar SunDroid).*
3. Pilih opsi koneksi:
   * **1 (USB):** Otomatis mengatur port forwarding ADB `7100` & `7101`.
   * **2 (Wi-Fi):** Masukkan alamat IP yang tertera di layar HP kamu.

---

## 📱 Panduan Build & Install Android

1. Buka folder `sundroid/android/` di **Android Studio**.
2. Hubungkan HP kamu dengan kabel USB (pastikan USB Debugging aktif).
3. Klik tombol **Run / Play (Shift + F10)** untuk menginstall **SunDroid Host** ke HP.
4. Di HP:
   * Buka aplikasi **SunDroid Host**.
   * Klik tombol **"Aktifkan Izin Aksesibilitas"** lalu aktifkan *SunDroid Host* di menu Aksesibilitas HP.
   * Klik **"Mulai Remote Host"** dan pilih *Start now*.

---

## 🎮 Tombol Pintasan (Hotkeys) di PC

| Tombol | Fungsi |
|---|---|
| **F1** | Aktifkan / Matikan **Mode Gaming Keymapper** (WASD & Mouse) |
| **F2** | Kunci / Nyalakan Layar HP (Power Button) |
| **F3 / F4** | Volume Turun / Naik |
| **F11** | Layar Penuh (Fullscreen) |
| **Klik Kanan** | Tombol Back |
| **Klik Tengah** | Tombol Home |
