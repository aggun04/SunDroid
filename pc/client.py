import sys
import os
import time
import socket
import threading
import subprocess
import numpy as np

# Suppress Pygame greeting
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

try:
    import av
except ImportError:
    av = None

class SunDroidClient:
    def __init__(self, host="127.0.0.1", video_port=7100, control_port=7101):
        self.host = host
        self.video_port = video_port
        self.control_port = control_port
        
        self.running = False
        self.video_socket = None
        self.control_socket = None
        
        self.latest_surface = None
        self.frame_lock = threading.Lock()
        
        # Phone screen properties
        self.phone_width = 1080
        self.phone_height = 2400
        self.aspect_ratio = self.phone_width / self.phone_height
        
        # Window size (scaled for PC display)
        self.win_height = 800
        self.win_width = int(self.win_height * self.aspect_ratio)
        
        # Stats
        self.fps = 0.0
        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.bitrate_kbps = 0.0
        self.bytes_received_sec = 0
        
        # Mouse / Touch State
        self.mouse_pressed = False
        self.is_game_mode = False
        
        # Gaming Keymap (WASD -> Touch swipe / analog emulation)
        self.keymap = {
            pygame.K_w: (0.50, 0.65), # Up
            pygame.K_s: (0.50, 0.85), # Down
            pygame.K_a: (0.40, 0.75), # Left
            pygame.K_d: (0.60, 0.75), # Right
            pygame.K_SPACE: (0.85, 0.80), # Jump/Action 1
            pygame.K_j: (0.80, 0.85),     # Action 2 / Attack
            pygame.K_k: (0.90, 0.75),     # Action 3
        }
        self.active_game_keys = set()

    def connect(self):
        print(f"[*] Menghubungkan ke SunDroid Host di {self.host}...")
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.video_socket.connect((self.host, self.video_port))
            
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.control_socket.connect((self.host, self.control_port))
            
            self.running = True
            print(f"[OK] Terhubung! Video Port: {self.video_port}, Control Port: {self.control_port}")
            return True
        except Exception as e:
            print(f"[ERROR] Gagal terhubung ke {self.host}: {e}")
            self.close()
            return False

    def send_control(self, cmd_str):
        if self.control_socket and self.running:
            try:
                msg = (cmd_str.strip() + "\n").encode('utf-8')
                self.control_socket.sendall(msg)
            except Exception as e:
                print(f"[!] Gagal kirim perintah kontrol: {e}")

    def start_video_stream(self):
        def stream_worker():
            if av is None:
                print("[ERROR] PyAV belum terinstall! Jalankan 'pip install av'.")
                return

            codec = av.CodecContext.create('h264', 'r')
            codec.thread_type = 'AUTO'
            codec.options = {
                'flags': 'low_delay',
                'fflags': 'nobuffer',
                'tune': 'zerolatency'
            }

            CHUNK_SIZE = 16384
            self.last_fps_time = time.time()
            self.fps_counter = 0

            while self.running:
                try:
                    data = self.video_socket.recv(CHUNK_SIZE)
                    if not data:
                        break
                    
                    self.bytes_received_sec += len(data)
                    packets = codec.parse(data)
                    for packet in packets:
                        frames = codec.decode(packet)
                        for frame in frames:
                            rgb_array = frame.to_ndarray(format='rgb24')
                            h, w, _ = rgb_array.shape
                            
                            # Transpose for Pygame surface blitting
                            surf = pygame.surfarray.make_surface(rgb_array.swapaxes(0, 1))
                            
                            with self.frame_lock:
                                self.latest_surface = surf
                                self.phone_width = w
                                self.phone_height = h
                                self.aspect_ratio = w / h

                            self.fps_counter += 1
                            now = time.time()
                            if now - self.last_fps_time >= 1.0:
                                self.fps = round(self.fps_counter / (now - self.last_fps_time), 1)
                                self.bitrate_kbps = round((self.bytes_received_sec * 8) / 1024, 1)
                                self.fps_counter = 0
                                self.bytes_received_sec = 0
                                self.last_fps_time = now

                except Exception as e:
                    if self.running:
                        print(f"[!] Video stream error: {e}")
                    break
            
            print("[*] Video stream thread berhenti.")

        threading.Thread(target=stream_worker, daemon=True).start()

    def run_gui(self):
        pygame.init()
        pygame.display.set_caption("SunDroid - Ultra Low Latency Android Remote")
        
        screen = pygame.display.set_mode((self.win_width, self.win_height), pygame.RESIZABLE)
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("Arial", 14)
        
        while self.running:
            # Handle Pygame Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                
                elif event.type == pygame.VIDEORESIZE:
                    self.win_width = event.w
                    self.win_height = event.h
                    screen = pygame.display.set_mode((self.win_width, self.win_height), pygame.RESIZABLE)

                # Mouse Touch Injection
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: # Left Click -> Touch Down
                        self.mouse_pressed = True
                        xp = max(0.0, min(1.0, event.pos[0] / self.win_width))
                        yp = max(0.0, min(1.0, event.pos[1] / self.win_height))
                        self.send_control(f"T D 0 {xp:.4f} {yp:.4f}")
                    elif event.button == 3: # Right Click -> Android BACK
                        self.send_control("CMD BACK")
                    elif event.button == 2: # Middle Click -> Android HOME
                        self.send_control("CMD HOME")
                    elif event.button == 4: # Scroll Up
                        xp = max(0.0, min(1.0, event.pos[0] / self.win_width))
                        yp = max(0.0, min(1.0, event.pos[1] / self.win_height))
                        self.send_control(f"S {xp:.4f} {yp:.4f} -0.15")
                    elif event.button == 5: # Scroll Down
                        xp = max(0.0, min(1.0, event.pos[0] / self.win_width))
                        yp = max(0.0, min(1.0, event.pos[1] / self.win_height))
                        self.send_control(f"S {xp:.4f} {yp:.4f} 0.15")

                elif event.type == pygame.MOUSEMOTION:
                    if self.mouse_pressed:
                        xp = max(0.0, min(1.0, event.pos[0] / self.win_width))
                        yp = max(0.0, min(1.0, event.pos[1] / self.win_height))
                        self.send_control(f"T M 0 {xp:.4f} {yp:.4f}")

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1: # Left Click Release -> Touch Up
                        self.mouse_pressed = False
                        xp = max(0.0, min(1.0, event.pos[0] / self.win_width))
                        yp = max(0.0, min(1.0, event.pos[1] / self.win_height))
                        self.send_control(f"T U 0 {xp:.4f} {yp:.4f}")

                # Keyboard Injection
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F1:
                        # Toggle Game Mode
                        self.is_game_mode = not self.is_game_mode
                        print(f"[*] Game Keymap Mode: {'ON' if self.is_game_mode else 'OFF'}")
                    elif event.key == pygame.K_F2:
                        self.send_control("CMD POWER")
                    elif event.key == pygame.K_F3:
                        self.send_control("CMD VOL_DOWN")
                    elif event.key == pygame.K_F4:
                        self.send_control("CMD VOL_UP")
                    elif event.key == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                    else:
                        if self.is_game_mode and event.key in self.keymap:
                            xp, yp = self.keymap[event.key]
                            pid = (event.key % 8) + 1 # virtual finger pointer id
                            self.send_control(f"T D {pid} {xp:.4f} {yp:.4f}")
                            self.active_game_keys.add(event.key)
                        elif event.unicode and event.unicode.isprintable():
                            self.send_control(f"TXT {event.unicode}")
                        elif event.key == pygame.K_BACKSPACE:
                            self.send_control("CMD KEY_BACKSPACE")
                        elif event.key == pygame.K_RETURN:
                            self.send_control("CMD KEY_ENTER")

                elif event.type == pygame.KEYUP:
                    if self.is_game_mode and event.key in self.active_game_keys:
                        xp, yp = self.keymap[event.key]
                        pid = (event.key % 8) + 1
                        self.send_control(f"T U {pid} {xp:.4f} {yp:.4f}")
                        self.active_game_keys.remove(event.key)

            # Render Frame
            screen.fill((20, 20, 24))
            
            with self.frame_lock:
                if self.latest_surface:
                    # Calculate correct aspect-ratio scaling
                    sw, sh = self.latest_surface.get_size()
                    scale = min(self.win_width / sw, self.win_height / sh)
                    rw, rh = int(sw * scale), int(sh * scale)
                    scaled_surf = pygame.transform.scale(self.latest_surface, (rw, rh))
                    
                    # Center surface on screen
                    ox = (self.win_width - rw) // 2
                    oy = (self.win_height - rh) // 2
                    screen.blit(scaled_surf, (ox, oy))
                else:
                    loading_txt = font.render("Menghubungkan ke layar HP...", True, (160, 160, 160))
                    screen.blit(loading_txt, (self.win_width // 2 - 80, self.win_height // 2))

            # HUD Overlay (FPS, Bitrate, Help)
            hud_bg = pygame.Surface((self.win_width, 26))
            hud_bg.set_alpha(180)
            hud_bg.fill((10, 10, 15))
            screen.blit(hud_bg, (0, 0))

            hud_text = f"⚡ FPS: {self.fps} | Bitrate: {self.bitrate_kbps} kbps | GameMode [F1]: {'ON' if self.is_game_mode else 'OFF'} | Back: Klik Kanan | Home: Klik Tengah"
            txt_surf = font.render(hud_text, True, (0, 255, 128) if self.fps > 25 else (255, 200, 0))
            screen.blit(txt_surf, (10, 4))

            pygame.display.flip()
            clock.tick(120) # Up to 120 FPS rendering loop

        pygame.quit()
        self.close()

    def close(self):
        self.running = False
        if self.video_socket:
            try:
                self.video_socket.close()
            except Exception:
                pass
        if self.control_socket:
            try:
                self.control_socket.close()
            except Exception:
                pass
        print("[*] SunDroid Client ditutup.")

def setup_adb_ports():
    print("[*] Mengonfigurasi port forwarding USB ADB...")
    try:
        subprocess.run(["adb", "forward", "tcp:7100", "tcp:7100"], check=True)
        subprocess.run(["adb", "forward", "tcp:7101", "tcp:7101"], check=True)
        print("[OK] Port ADB 7100 & 7101 siap digunakan via kabel USB!")
        return True
    except Exception as e:
        print(f"[!] Warning: ADB tidak ditemukan atau HP belum terhubung: {e}")
        return False

if __name__ == "__main__":
    target_ip = "127.0.0.1"
    if len(sys.argv) > 1:
        target_ip = sys.argv[1]
    else:
        # Prompt user or default to USB ADB
        print("==================================================")
        print("       SunDroid PC - Remote Android Satset        ")
        print("==================================================")
        print("1. Mode Kabel USB (ADB) - Rekomendasi Latensi < 10ms")
        print("2. Mode Wi-Fi (Masukkan IP HP)")
        choice = input("Pilih mode [1/2, default 1]: ").strip()
        if choice == "2":
            target_ip = input("Masukkan IP HP (contoh: 192.168.1.15): ").strip()
        else:
            setup_adb_ports()
            target_ip = "127.0.0.1"

    client = SunDroidClient(host=target_ip)
    if client.connect():
        client.start_video_stream()
        client.run_gui()
    else:
        print("[!] Gagal terhubung. Pastikan aplikasi SunDroid di HP sudah aktif!")
        input("Tekan Enter untuk keluar...")
