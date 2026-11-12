"""
SunDroid PC Client — Reverse Sunshine & Moonlight (Remote Android dari PC)
Fitur Utama:
- Clickable Modern Launcher GUI (USB ADB & Wi-Fi mode, IP memory, Ping test, Subnet scan)
- Tidak pernah menutup aplikasi saat koneksi gagal (tetap standby & memberi solusi diagnostik)
- Layar Streaming Pygame dengan On-Screen Clickable Toolbar (Back, Home, Recents, Power, Vol, Game Mode)
- Toleran terhadap error streaming PyAV / H.264 packet loss
"""

import sys
import os
import time
import json
import socket
import threading
import subprocess

# Suppress Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import numpy as np

try:
    import av
except ImportError:
    av = None

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk = None

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sundroid_config.json")

def load_config():
    default_config = {
        "mode": "wifi",
        "last_ip": "192.168.1.",
        "ip_history": ["192.168.1.", "192.168.43.1"],
        "win_height": 800,
        "fps_target": 60,
        "show_toolbar": True
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def sanitize_host(host_str):
    if not host_str:
        return "127.0.0.1"
    h = host_str.strip()
    if h.startswith("http://"):
        h = h[7:]
    elif h.startswith("https://"):
        h = h[8:]
    h = h.split("/")[0].strip()
    if ":" in h and not h.startswith("["):
        h = h.split(":")[0].strip()
    return h if h else "127.0.0.1"

def test_tcp_port(host, port=7100, timeout=1.5):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def scan_local_subnet_for_host(port=7100, timeout=0.35):
    local_ip = get_local_ip()
    if local_ip == "127.0.0.1":
        return []
    parts = local_ip.split(".")
    prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
    
    found = []
    lock = threading.Lock()

    def check(ip):
        if test_tcp_port(ip, port, timeout):
            with lock:
                found.append(ip)

    threads = []
    for i in range(1, 255):
        ip = f"{prefix}{i}"
        t = threading.Thread(target=check, args=(ip,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout + 0.1)

    return found

def get_adb_command():
    base_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    candidate = os.path.join(base_dir, "adb.exe" if sys.platform == "win32" else "adb")
    if os.path.isfile(candidate):
        return candidate
    return "adb"

def scan_adb_devices():
    adb_cmd = get_adb_command()
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        res = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=3, creationflags=creationflags)
        lines = res.stdout.strip().split("\n")[1:]
        devices = []
        for line in lines:
            line = line.strip()
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    devices.append((parts[0], parts[1]))
        return devices
    except Exception:
        return []

def setup_adb_ports():
    adb_cmd = get_adb_command()
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        subprocess.run([adb_cmd, "forward", "tcp:7100", "tcp:7100"], check=True, creationflags=creationflags, timeout=4)
        subprocess.run([adb_cmd, "forward", "tcp:7101", "tcp:7101"], check=True, creationflags=creationflags, timeout=4)
        return True, "Port ADB 7100 & 7101 berhasil diforward!"
    except Exception as e:
        return False, f"Gagal setup ADB: {e}"


# =====================================================================
# Toolbar Button definition for Pygame On-Screen Controls
# =====================================================================
class NavButton:
    def __init__(self, key, text, symbol, cmd=None, action_fn=None):
        self.key = key
        self.text = text
        self.symbol = symbol
        self.cmd = cmd
        self.action_fn = action_fn
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.is_hovered = False


# =====================================================================
# SunDroid Streaming Client (Pygame & PyAV)
# =====================================================================
class SunDroidClient:
    def __init__(self, host="127.0.0.1", video_port=7100, control_port=7101, win_height=800, show_toolbar=True, fps_target=60):
        self.host = host
        self.video_port = video_port
        self.control_port = control_port
        self.win_height = win_height
        self.show_toolbar = show_toolbar
        self.fps_target = fps_target
        
        self.running = False
        self.video_socket = None
        self.control_socket = None
        
        self.latest_surface = None
        self.frame_lock = threading.Lock()
        
        self.phone_width = 1080
        self.phone_height = 2400
        self.aspect_ratio = self.phone_width / self.phone_height
        
        self.toolbar_height = 46 if self.show_toolbar else 0
        self.win_width = int(self.win_height * self.aspect_ratio)
        
        # Stats
        self.fps = 0.0
        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.bitrate_kbps = 0.0
        self.bytes_received_sec = 0
        
        # State
        self.mouse_pressed = False
        self.is_game_mode = False
        self.is_disconnected = False
        self.reconnect_requested = False
        self.is_fullscreen = False

        # Gaming Keymap (WASD + Action Keys)
        self.keymap = {
            pygame.K_w: (0.50, 0.65), # Up
            pygame.K_s: (0.50, 0.85), # Down
            pygame.K_a: (0.40, 0.75), # Left
            pygame.K_d: (0.60, 0.75), # Right
            pygame.K_SPACE: (0.85, 0.80), # Jump/Action 1
            pygame.K_j: (0.80, 0.85),     # Attack/Action 2
            pygame.K_k: (0.90, 0.75),     # Skill/Action 3
        }
        self.active_game_keys = set()

        # Toolbar Buttons (Clickable on-screen UI)
        self.toolbar_buttons = [
            NavButton("back", "Back", "◀", cmd="CMD BACK"),
            NavButton("home", "Home", "⚪", cmd="CMD HOME"),
            NavButton("recents", "Recent", "▢", cmd="CMD RECENTS"),
            NavButton("power", "Power", "⚡", cmd="CMD POWER"),
            NavButton("voldown", "Vol -", "🔉", cmd="CMD VOL_DOWN"),
            NavButton("volup", "Vol +", "🔊", cmd="CMD VOL_UP"),
            NavButton("game", "Game", "🎮", action_fn=self.toggle_game_mode),
            NavButton("fs", "Full", "⛶", action_fn=self.toggle_fullscreen),
            NavButton("exit", "Keluar", "❌", action_fn=self.request_quit),
        ]

        # Buttons on Disconnected Overlay
        self.btn_reconnect = pygame.Rect(0, 0, 140, 38)
        self.btn_exit_menu = pygame.Rect(0, 0, 140, 38)

    def toggle_game_mode(self):
        self.is_game_mode = not self.is_game_mode

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        pygame.display.toggle_fullscreen()

    def request_quit(self):
        self.running = False

    def connect(self):
        try:
            # 1. Connect Video Socket with short timeout
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.video_socket.settimeout(3.5)
            self.video_socket.connect((self.host, self.video_port))
            self.video_socket.settimeout(2.0) # 2s recv timeout

            # 2. Connect Control Socket
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.control_socket.settimeout(3.5)
            self.control_socket.connect((self.host, self.control_port))
            self.control_socket.settimeout(None)

            self.running = True
            self.is_disconnected = False
            return True, "Terhubung!"
        except Exception as e:
            self.close()
            return False, str(e)

    def send_control(self, cmd_str):
        if self.control_socket and self.running:
            try:
                msg = (cmd_str.strip() + "\n").encode('utf-8')
                self.control_socket.sendall(msg)
            except Exception:
                pass

    def start_video_stream(self):
        def stream_worker():
            if av is None:
                print("[ERROR] Library PyAV belum terinstall! Jalankan 'pip install av'.")
                return

            codec = av.CodecContext.create('h264', 'r')
            codec.thread_type = 'AUTO'
            codec.options = {
                'flags': 'low_delay',
                'fflags': 'nobuffer',
                'tune': 'zerolatency'
            }

            CHUNK_SIZE = 32768
            self.last_fps_time = time.time()
            self.fps_counter = 0

            while self.running:
                try:
                    data = self.video_socket.recv(CHUNK_SIZE)
                    if not data:
                        # Remote closed socket
                        if self.running:
                            self.is_disconnected = True
                        break

                    self.bytes_received_sec += len(data)

                    # Parse packets safely
                    try:
                        packets = codec.parse(data)
                    except Exception:
                        continue

                    for packet in packets:
                        try:
                            frames = codec.decode(packet)
                            for frame in frames:
                                rgb_array = frame.to_ndarray(format='rgb24')
                                h, w, _ = rgb_array.shape

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
                        except Exception:
                            # Tolerant of initial SPS/PPS missing or dropped frames over Wi-Fi
                            continue

                except socket.timeout:
                    # Timeout is normal when phone screen is static
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[*] Stream error: {e}")
                        self.is_disconnected = True
                    break

        threading.Thread(target=stream_worker, daemon=True).start()

    def run_gui(self):
        pygame.init()
        pygame.display.set_caption("SunDroid — Android Remote Control")

        screen = pygame.display.set_mode((self.win_width, self.win_height), pygame.RESIZABLE)
        clock = pygame.time.Clock()

        # Fonts
        font_hud = pygame.font.SysFont("Segoe UI, Arial", 13)
        font_btn = pygame.font.SysFont("Segoe UI, Arial", 12, bold=True)
        font_large = pygame.font.SysFont("Segoe UI, Arial", 16, bold=True)

        while self.running:
            # Calculate rendering geometries
            phone_area_h = self.win_height - self.toolbar_height
            scale = min(self.win_width / max(1, self.phone_width), phone_area_h / max(1, self.phone_height))
            rw, rh = int(self.phone_width * scale), int(self.phone_height * scale)
            ox = (self.win_width - rw) // 2
            oy = (phone_area_h - rh) // 2

            # Layout Toolbar Buttons
            if self.show_toolbar:
                btn_count = len(self.toolbar_buttons)
                avail_w = self.win_width - 12
                btn_w = max(34, min(52, avail_w // btn_count))
                tb_start_x = (self.win_width - (btn_count * btn_w)) // 2
                tb_y = self.win_height - self.toolbar_height + 5
                tb_h = self.toolbar_height - 10

                for i, btn in enumerate(self.toolbar_buttons):
                    btn.rect = pygame.Rect(tb_start_x + i * btn_w + 1, tb_y, btn_w - 2, tb_h)

            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break

                elif event.type == pygame.VIDEORESIZE:
                    self.win_width = max(320, event.w)
                    self.win_height = max(400, event.h)
                    screen = pygame.display.set_mode((self.win_width, self.win_height), pygame.RESIZABLE)

                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos

                    # Update toolbar hover state
                    if self.show_toolbar and my >= phone_area_h:
                        for btn in self.toolbar_buttons:
                            btn.is_hovered = btn.rect.collidepoint(mx, my)
                    else:
                        for btn in self.toolbar_buttons:
                            btn.is_hovered = False

                        # Mouse Drag Touch Injection
                        if self.mouse_pressed and not self.is_disconnected:
                            if rw > 0 and rh > 0:
                                xp = max(0.0, min(1.0, (mx - ox) / rw))
                                yp = max(0.0, min(1.0, (my - oy) / rh))
                                self.send_control(f"T M 0 {xp:.4f} {yp:.4f}")

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # Disconnected Overlay Clicks
                    if self.is_disconnected:
                        if self.btn_reconnect.collidepoint(mx, my):
                            self.reconnect_requested = True
                            self.running = False
                            break
                        elif self.btn_exit_menu.collidepoint(mx, my):
                            self.running = False
                            break
                        continue

                    # Check Toolbar Clicks
                    if self.show_toolbar and my >= phone_area_h:
                        for btn in self.toolbar_buttons:
                            if btn.rect.collidepoint(mx, my):
                                if btn.action_fn:
                                    btn.action_fn()
                                elif btn.cmd:
                                    self.send_control(btn.cmd)
                                break
                    else:
                        # Check Phone Touch Clicks
                        if event.button == 1: # Left Click -> Touch Down
                            if rw > 0 and rh > 0:
                                xp = max(0.0, min(1.0, (mx - ox) / rw))
                                yp = max(0.0, min(1.0, (my - oy) / rh))
                                self.mouse_pressed = True
                                self.send_control(f"T D 0 {xp:.4f} {yp:.4f}")

                        elif event.button == 3: # Right Click -> Back
                            self.send_control("CMD BACK")

                        elif event.button == 2: # Middle Click -> Home
                            self.send_control("CMD HOME")

                        elif event.button == 4: # Scroll Up
                            if rw > 0 and rh > 0:
                                xp = max(0.0, min(1.0, (mx - ox) / rw))
                                yp = max(0.0, min(1.0, (my - oy) / rh))
                                self.send_control(f"S {xp:.4f} {yp:.4f} -0.15")

                        elif event.button == 5: # Scroll Down
                            if rw > 0 and rh > 0:
                                xp = max(0.0, min(1.0, (mx - ox) / rw))
                                yp = max(0.0, min(1.0, (my - oy) / rh))
                                self.send_control(f"S {xp:.4f} {yp:.4f} 0.15")

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 and self.mouse_pressed:
                        self.mouse_pressed = False
                        mx, my = event.pos
                        if rw > 0 and rh > 0:
                            xp = max(0.0, min(1.0, (mx - ox) / rw))
                            yp = max(0.0, min(1.0, (my - oy) / rh))
                            self.send_control(f"T U 0 {xp:.4f} {yp:.4f}")

                # Keyboard Hotkeys & Keymapper
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F1:
                        self.toggle_game_mode()
                    elif event.key == pygame.K_F2:
                        self.send_control("CMD POWER")
                    elif event.key == pygame.K_F3:
                        self.send_control("CMD VOL_DOWN")
                    elif event.key == pygame.K_F4:
                        self.send_control("CMD VOL_UP")
                    elif event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    else:
                        if self.is_game_mode and event.key in self.keymap:
                            xp, yp = self.keymap[event.key]
                            pid = (event.key % 8) + 1
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

            # =========================================================
            # Render Scene
            # =========================================================
            screen.fill((14, 14, 17)) # Dark background

            # 1. Render Video Surface
            with self.frame_lock:
                if self.latest_surface and rw > 0 and rh > 0:
                    scaled_surf = pygame.transform.scale(self.latest_surface, (rw, rh))
                    screen.blit(scaled_surf, (ox, oy))
                else:
                    loading_txt = font_hud.render("Menghubungkan ke layar HP SunDroid...", True, (160, 160, 160))
                    screen.blit(loading_txt, (self.win_width // 2 - 110, phone_area_h // 2 - 10))

            # 2. Render Top HUD Bar
            hud_bg = pygame.Surface((self.win_width, 24))
            hud_bg.set_alpha(190)
            hud_bg.fill((10, 10, 14))
            screen.blit(hud_bg, (0, 0))

            hud_text = f"⚡ FPS: {self.fps} | Bitrate: {self.bitrate_kbps} kbps | Game Mode [F1]: {'ON' if self.is_game_mode else 'OFF'}"
            fps_color = (34, 197, 94) if self.fps > 25 else (245, 158, 11)
            screen.blit(font_hud.render(hud_text, True, fps_color), (10, 3))

            # 3. Render Bottom Clickable Toolbar
            if self.show_toolbar:
                tb_bg = pygame.Surface((self.win_width, self.toolbar_height))
                tb_bg.fill((20, 20, 25))
                screen.blit(tb_bg, (0, phone_area_h))
                # Top border line
                pygame.draw.line(screen, (39, 39, 44), (0, phone_area_h), (self.win_width, phone_area_h), 1)

                for btn in self.toolbar_buttons:
                    # Button background
                    if btn.key == "game" and self.is_game_mode:
                        btn_col = (234, 88, 12) # Active orange
                    elif btn.is_hovered:
                        btn_col = (45, 45, 55) # Hover color
                    else:
                        btn_col = (28, 28, 35) # Normal color

                    pygame.draw.rect(screen, btn_col, btn.rect, border_radius=6)
                    pygame.draw.rect(screen, (50, 50, 60), btn.rect, width=1, border_radius=6)

                    # Text / Icon label
                    label_surf = font_btn.render(btn.symbol, True, (255, 255, 255))
                    screen.blit(label_surf, (btn.rect.centerx - label_surf.get_width() // 2, btn.rect.centery - label_surf.get_height() // 2))

            # 4. Render Disconnected Overlay Dialog (if stream interrupted)
            if self.is_disconnected:
                overlay = pygame.Surface((self.win_width, self.win_height))
                overlay.set_alpha(210)
                overlay.fill((8, 8, 12))
                screen.blit(overlay, (0, 0))

                card_w, card_h = min(360, self.win_width - 40), 180
                card_x = (self.win_width - card_w) // 2
                card_y = (self.win_height - card_h) // 2
                card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

                pygame.draw.rect(screen, (24, 24, 30), card_rect, border_radius=12)
                pygame.draw.rect(screen, (239, 68, 68), card_rect, width=2, border_radius=12)

                t1 = font_large.render("⚠️ Koneksi Terputus ke HP!", True, (239, 68, 68))
                screen.blit(t1, (card_x + (card_w - t1.get_width()) // 2, card_y + 24))

                t2 = font_hud.render("Aplikasi di HP terhenti atau Wi-Fi terputus.", True, (180, 180, 185))
                screen.blit(t2, (card_x + (card_w - t2.get_width()) // 2, card_y + 58))

                # Buttons inside overlay
                bw, bh = 140, 38
                self.btn_reconnect = pygame.Rect(card_x + card_w // 2 - bw - 10, card_y + 110, bw, bh)
                self.btn_exit_menu = pygame.Rect(card_x + card_w // 2 + 10, card_y + 110, bw, bh)

                pygame.draw.rect(screen, (234, 88, 12), self.btn_reconnect, border_radius=8)
                pygame.draw.rect(screen, (39, 39, 44), self.btn_exit_menu, border_radius=8)

                t_recon = font_btn.render("🔄 Sambung Ulang", True, (255, 255, 255))
                screen.blit(t_recon, (self.btn_reconnect.centerx - t_recon.get_width() // 2, self.btn_reconnect.centery - t_recon.get_height() // 2))

                t_exit = font_btn.render("⬅ Menu Utama", True, (220, 220, 220))
                screen.blit(t_exit, (self.btn_exit_menu.centerx - t_exit.get_width() // 2, self.btn_exit_menu.centery - t_exit.get_height() // 2))

            pygame.display.flip()
            clock.tick(self.fps_target)

        pygame.quit()
        self.close()

    def close(self):
        self.running = False
        if self.video_socket:
            try:
                self.video_socket.close()
            except Exception:
                pass
            self.video_socket = None

        if self.control_socket:
            try:
                self.control_socket.close()
            except Exception:
                pass
            self.control_socket = None


# =====================================================================
# Modern Clickable Tkinter Dashboard / Launcher
# =====================================================================
class SunDroidLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SunDroid — Android Remote Control")
        self.root.geometry("540x680")
        self.root.minsize(480, 580)
        self.root.configure(bg="#09090b")

        self.config = load_config()
        self.current_mode = self.config.get("mode", "wifi")
        self.active_client = None

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Colors: Zinc Dark Theme with Sun Orange
        style.configure(".", background="#09090b", foreground="#fafafa", font=("Segoe UI", 10))
        style.configure("TFrame", background="#09090b")
        style.configure("Card.TFrame", background="#18181b", relief="flat")
        
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#ea580c", background="#09090b")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#a1a1aa", background="#09090b")
        style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"), foreground="#fafafa", background="#18181b")
        style.configure("CardDesc.TLabel", font=("Segoe UI", 9), foreground="#a1a1aa", background="#18181b")

        # Custom Buttons
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), background="#ea580c", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#f97316"), ("disabled", "#52525b")])

        style.configure("Secondary.TButton", font=("Segoe UI", 9), background="#27272a", foreground="#fafafa")
        style.map("Secondary.TButton", background=[("active", "#3f3f46")])

        style.configure("TabActive.TButton", font=("Segoe UI", 10, "bold"), background="#ea580c", foreground="#ffffff")
        style.configure("TabInactive.TButton", font=("Segoe UI", 10), background="#18181b", foreground="#a1a1aa")

    def create_widgets(self):
        # 1. Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill="x", padx=20, pady=(16, 10))

        ttk.Label(header_frame, text="☀️ SunDroid Control Center", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header_frame, text="Remote HP Android dari PC — Latensi Super Rendah (< 15ms)", style="SubHeader.TLabel").pack(anchor="w", pady=(2, 0))

        # 2. Mode Selector Segmented Tabs
        tab_frame = ttk.Frame(self.root)
        tab_frame.pack(fill="x", padx=20, pady=(6, 12))

        self.btn_tab_usb = tk.Button(
            tab_frame, text="🔌 Mode USB (Kabel ADB)", font=("Segoe UI", 10, "bold"),
            bg="#ea580c" if self.current_mode == "usb" else "#18181b",
            fg="#ffffff" if self.current_mode == "usb" else "#a1a1aa",
            activebackground="#f97316", activeforeground="#ffffff",
            relief="flat", cursor="hand2", padx=12, pady=8,
            command=lambda: self.switch_mode("usb")
        )
        self.btn_tab_usb.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_tab_wifi = tk.Button(
            tab_frame, text="📡 Mode Wi-Fi (Nirkabel)", font=("Segoe UI", 10, "bold"),
            bg="#ea580c" if self.current_mode == "wifi" else "#18181b",
            fg="#ffffff" if self.current_mode == "wifi" else "#a1a1aa",
            activebackground="#f97316", activeforeground="#ffffff",
            relief="flat", cursor="hand2", padx=12, pady=8,
            command=lambda: self.switch_mode("wifi")
        )
        self.btn_tab_wifi.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # 3. Dynamic Mode Container Frame
        self.mode_container = ttk.Frame(self.root, style="Card.TFrame")
        self.mode_container.pack(fill="x", padx=20, pady=4)

        # 4. Settings Card (Resolution, FPS, Toolbar)
        settings_card = ttk.Frame(self.root, style="Card.TFrame")
        settings_card.pack(fill="x", padx=20, pady=10)

        inner_settings = tk.Frame(settings_card, bg="#18181b", padx=14, pady=10)
        inner_settings.pack(fill="x")

        tk.Label(inner_settings, text="Pengaturan Stream PC:", font=("Segoe UI", 10, "bold"), bg="#18181b", fg="#fafafa").grid(row=0, column=0, sticky="w", pady=(0, 6))

        tk.Label(inner_settings, text="Tinggi Jendela:", bg="#18181b", fg="#a1a1aa", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.var_win_h = tk.StringVar(value=str(self.config.get("win_height", 800)))
        spn_h = ttk.Combobox(inner_settings, textvariable=self.var_win_h, values=["600", "720", "800", "900", "1080"], width=8, state="readonly")
        spn_h.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(inner_settings, text="Target FPS:", bg="#18181b", fg="#a1a1aa", font=("Segoe UI", 9)).grid(row=1, column=2, sticky="w", padx=(16, 8))
        self.var_fps = tk.StringVar(value=str(self.config.get("fps_target", 60)))
        spn_fps = ttk.Combobox(inner_settings, textvariable=self.var_fps, values=["60", "120"], width=8, state="readonly")
        spn_fps.grid(row=1, column=3, sticky="w", pady=2)

        self.var_toolbar = tk.BooleanVar(value=self.config.get("show_toolbar", True))
        chk_tb = tk.Checkbutton(
            inner_settings, text="Tampilkan Tombol Navigasi di Layar Streaming (Back, Home, Power, dll)",
            variable=self.var_toolbar, bg="#18181b", fg="#fafafa", activebackground="#18181b",
            activeforeground="#ea580c", selectcolor="#27272a", font=("Segoe UI", 9)
        )
        chk_tb.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # 5. Live Status & Diagnostic Card
        status_card = ttk.Frame(self.root, style="Card.TFrame")
        status_card.pack(fill="both", expand=True, padx=20, pady=4)

        inner_status = tk.Frame(status_card, bg="#18181b", padx=14, pady=12)
        inner_status.pack(fill="both", expand=True)

        tk.Label(inner_status, text="Status Koneksi:", font=("Segoe UI", 10, "bold"), bg="#18181b", fg="#fafafa").pack(anchor="w")

        self.lbl_status = tk.Label(
            inner_status, text="⚪ Siap Menghubungkan", font=("Segoe UI", 10, "bold"),
            bg="#18181b", fg="#a1a1aa", wraplength=460, justify="left"
        )
        self.lbl_status.pack(anchor="w", pady=(4, 2))

        self.lbl_diagnostic = tk.Label(
            inner_status, text="", font=("Segoe UI", 8),
            bg="#18181b", fg="#f59e0b", wraplength=460, justify="left"
        )
        self.lbl_diagnostic.pack(anchor="w", pady=(2, 0))

        # 6. Main Action Buttons
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill="x", padx=20, pady=(10, 16))

        self.btn_connect = tk.Button(
            action_frame, text="🚀 HUBUNGKAN KE HP", font=("Segoe UI", 12, "bold"),
            bg="#ea580c", fg="#ffffff", activebackground="#f97316", activeforeground="#ffffff",
            relief="flat", cursor="hand2", pady=10,
            command=self.start_connection
        )
        self.btn_connect.pack(fill="x")

        self.render_mode_content()

    def switch_mode(self, mode):
        self.current_mode = mode
        if mode == "usb":
            self.btn_tab_usb.configure(bg="#ea580c", fg="#ffffff")
            self.btn_tab_wifi.configure(bg="#18181b", fg="#a1a1aa")
        else:
            self.btn_tab_usb.configure(bg="#18181b", fg="#a1a1aa")
            self.btn_tab_wifi.configure(bg="#ea580c", fg="#ffffff")
        self.render_mode_content()

    def render_mode_content(self):
        for widget in self.mode_container.winfo_children():
            widget.destroy()

        content = tk.Frame(self.mode_container, bg="#18181b", padx=14, pady=12)
        content.pack(fill="x")

        if self.current_mode == "usb":
            tk.Label(content, text="Mode Kabel USB (ADB)", font=("Segoe UI", 11, "bold"), bg="#18181b", fg="#fafafa").pack(anchor="w")
            tk.Label(
                content, text="Rekomendasi! Latensi < 10ms, stabil 100%, anti interferensi sinyal Wi-Fi.\nPastikan USB Debugging aktif di HP Anda.",
                font=("Segoe UI", 9), bg="#18181b", fg="#a1a1aa", justify="left"
            ).pack(anchor="w", pady=(2, 8))

            row_btns = tk.Frame(content, bg="#18181b")
            row_btns.pack(fill="x", pady=4)

            btn_scan = tk.Button(
                row_btns, text="🔍 Pindai HP via USB (Scan ADB)", font=("Segoe UI", 9),
                bg="#27272a", fg="#fafafa", activebackground="#3f3f46", activeforeground="#ffffff",
                relief="flat", cursor="hand2", padx=8, pady=4, command=self.action_scan_adb
            )
            btn_scan.pack(side="left", padx=(0, 6))

            btn_fwd = tk.Button(
                row_btns, text="⚡ Forward Port (7100 & 7101)", font=("Segoe UI", 9),
                bg="#27272a", fg="#fafafa", activebackground="#3f3f46", activeforeground="#ffffff",
                relief="flat", cursor="hand2", padx=8, pady=4, command=self.action_forward_adb
            )
            btn_fwd.pack(side="left")

            self.lbl_usb_device = tk.Label(content, text="Tekan 'Pindai HP' untuk mengecek koneksi kabel.", font=("Segoe UI", 8), bg="#18181b", fg="#a1a1aa")
            self.lbl_usb_device.pack(anchor="w", pady=(6, 0))

        else: # Wi-Fi Mode
            tk.Label(content, text="Mode Wi-Fi (Nirkabel)", font=("Segoe UI", 11, "bold"), bg="#18181b", fg="#fafafa").pack(anchor="w")
            tk.Label(
                content, text="Koneksi wireless. Masukkan alamat IP yang tertera di aplikasi SunDroid HP Anda.\nPastikan PC dan HP terhubung ke Wi-Fi yang sama atau Hotspot HP.",
                font=("Segoe UI", 9), bg="#18181b", fg="#a1a1aa", justify="left"
            ).pack(anchor="w", pady=(2, 8))

            row_ip = tk.Frame(content, bg="#18181b")
            row_ip.pack(fill="x", pady=2)

            tk.Label(row_ip, text="Alamat IP HP:", font=("Segoe UI", 9, "bold"), bg="#18181b", fg="#fafafa").pack(side="left", padx=(0, 6))

            history = self.config.get("ip_history", ["192.168.1."])
            self.var_ip = tk.StringVar(value=self.config.get("last_ip", "192.168.1."))
            self.ent_ip = ttk.Combobox(row_ip, textvariable=self.var_ip, values=history, width=22)
            self.ent_ip.pack(side="left", fill="x", expand=True)

            # Quick Preset Chips & Diagnostic Tools
            row_tools = tk.Frame(content, bg="#18181b")
            row_tools.pack(fill="x", pady=(6, 0))

            btn_ping = tk.Button(
                row_tools, text="📶 Tes Ping Port HP", font=("Segoe UI", 9),
                bg="#27272a", fg="#fafafa", activebackground="#3f3f46", activeforeground="#ffffff",
                relief="flat", cursor="hand2", padx=8, pady=4, command=self.action_ping_host
            )
            btn_ping.pack(side="left", padx=(0, 6))

            btn_scan_net = tk.Button(
                row_tools, text="🔎 Cari HP Otomatis", font=("Segoe UI", 9),
                bg="#27272a", fg="#fafafa", activebackground="#3f3f46", activeforeground="#ffffff",
                relief="flat", cursor="hand2", padx=8, pady=4, command=self.action_scan_subnet
            )
            btn_scan_net.pack(side="left", padx=(0, 6))

            btn_hotspot = tk.Button(
                row_tools, text="📱 Hotspot IP", font=("Segoe UI", 9),
                bg="#27272a", fg="#a1a1aa", activebackground="#3f3f46", activeforeground="#ffffff",
                relief="flat", cursor="hand2", padx=6, pady=4, command=lambda: self.var_ip.set("192.168.43.1")
            )
            btn_hotspot.pack(side="left")

    def action_scan_adb(self):
        self.lbl_usb_device.config(text="Memindai perangkat ADB...", fg="#f59e0b")
        def worker():
            devices = scan_adb_devices()
            if devices:
                dev_str = ", ".join([f"{d[0]} ({d[1]})" for d in devices])
                self.root.after(0, lambda: self.lbl_usb_device.config(text=f"✅ Ditemukan {len(devices)} HP: {dev_str}", fg="#22c55e"))
            else:
                self.root.after(0, lambda: self.lbl_usb_device.config(
                    text="❌ Tidak ada HP terdeteksi via ADB! Pastikan kabel terhubung & USB Debugging diizinkan.", fg="#ef4444"
                ))
        threading.Thread(target=worker, daemon=True).start()

    def action_forward_adb(self):
        self.lbl_usb_device.config(text="Mengatur port forwarding...", fg="#f59e0b")
        def worker():
            ok, msg = setup_adb_ports()
            color = "#22c55e" if ok else "#ef4444"
            self.root.after(0, lambda: self.lbl_usb_device.config(text=msg, fg=color))
        threading.Thread(target=worker, daemon=True).start()

    def action_ping_host(self):
        ip = sanitize_host(self.var_ip.get())
        self.lbl_status.config(text=f"Mengecek port 7100 di {ip}...", fg="#f59e0b")
        def worker():
            t0 = time.time()
            ok = test_tcp_port(ip, 7100, timeout=1.5)
            dt = int((time.time() - t0) * 1000)
            if ok:
                msg = f"🟢 Port 7100 HP ({ip}) AKTIF & Siap ({dt}ms)!"
                diag = "HP Anda sudah siap terhubung. Silakan klik 'HUBUNGKAN KE HP'."
                col = "#22c55e"
            else:
                msg = f"🔴 Port 7100 di {ip} TIDAK MERESPONS!"
                diag = (
                    "Penyebab umum:\n"
                    "1. Aplikasi di HP belum diklik 'Mulai Remote Host' (tombol masih merah).\n"
                    "2. PC dan HP tidak di Wi-Fi yang sama (atau router memblokir koneksi antar perangkat).\n"
                    "3. Alamat IP salah ketik. Periksa IP di layar HP SunDroid Host Anda."
                )
                col = "#ef4444"
            self.root.after(0, lambda: [
                self.lbl_status.config(text=msg, fg=col),
                self.lbl_diagnostic.config(text=diag)
            ])
        threading.Thread(target=worker, daemon=True).start()

    def action_scan_subnet(self):
        self.lbl_status.config(text="Memindai subnet lokal untuk mencari SunDroid Host...", fg="#f59e0b")
        def worker():
            hosts = scan_local_subnet_for_host(7100)
            if hosts:
                found_ip = hosts[0]
                self.root.after(0, lambda: [
                    self.var_ip.set(found_ip),
                    self.lbl_status.config(text=f"🟢 Ditemukan HP di {found_ip}!", fg="#22c55e"),
                    self.lbl_diagnostic.config(text="Alamat IP otomatis diisi! Silakan klik 'HUBUNGKAN KE HP'.")
                ])
            else:
                self.root.after(0, lambda: [
                    self.lbl_status.config(text="❌ Tidak ada SunDroid Host ditemukan di jaringan ini.", fg="#ef4444"),
                    self.lbl_diagnostic.config(text="Pastikan 'Mulai Remote Host' di HP sudah aktif sebelum memindai.")
                ])
        threading.Thread(target=worker, daemon=True).start()

    def start_connection(self):
        # Save config
        try:
            self.config["win_height"] = int(self.var_win_h.get())
            self.config["fps_target"] = int(self.var_fps.get())
            self.config["show_toolbar"] = self.var_toolbar.get()
            self.config["mode"] = self.current_mode
        except Exception:
            pass

        target_ip = "127.0.0.1"
        if self.current_mode == "wifi":
            raw_ip = self.var_ip.get().strip()
            target_ip = sanitize_host(raw_ip)
            self.config["last_ip"] = target_ip
            hist = self.config.get("ip_history", [])
            if target_ip not in hist:
                hist.insert(0, target_ip)
                self.config["ip_history"] = hist[:6]

        save_config(self.config)

        # UI updates during connection
        self.btn_connect.config(state="disabled", text="⏳ MENGHUBUNGKAN...", bg="#52525b")
        self.lbl_status.config(text=f"🟡 Menghubungkan ke {target_ip} (Port: 7100 & 7101)...", fg="#f59e0b")
        self.lbl_diagnostic.config(text="")

        def connect_thread():
            if self.current_mode == "usb":
                setup_adb_ports()

            client = SunDroidClient(
                host=target_ip,
                video_port=7100,
                control_port=7101,
                win_height=self.config.get("win_height", 800),
                show_toolbar=self.config.get("show_toolbar", True),
                fps_target=self.config.get("fps_target", 60)
            )

            ok, err_msg = client.connect()

            if not ok:
                # Connection failed: NEVER CLOSE THE APPLICATION!
                self.root.after(0, lambda: self.on_connection_failed(target_ip, err_msg))
            else:
                # Connection succeeded: Launch streaming window!
                self.root.after(0, lambda: self.on_connection_success(client))

        threading.Thread(target=connect_thread, daemon=True).start()

    def on_connection_failed(self, host, err):
        # Restore button and stay on launcher
        self.btn_connect.config(state="normal", text="🚀 HUBUNGKAN KE HP", bg="#ea580c")
        self.lbl_status.config(text=f"❌ Gagal Terhubung ke HP ({host})!", fg="#ef4444")

        diagnostic_tips = (
            f"Detail Masalah: {err}\n\n"
            "Solusi Perbaikan:\n"
            "1. Pastikan tombol 'Mulai Remote Host' di aplikasi HP sudah diklik (warna merah / aktif).\n"
            "2. Jika Wi-Fi: Pastikan PC & HP di Wi-Fi yang sama (atau PC sambung ke Hotspot HP).\n"
            "3. Jika USB: Pastikan USB Debugging aktif di HP dan kabel tidak longgar.\n"
            "4. Coba klik '📶 Tes Ping Port HP' di atas untuk memastikan port terbuka."
        )
        self.lbl_diagnostic.config(text=diagnostic_tips)

    def on_connection_success(self, client):
        self.active_client = client
        self.lbl_status.config(text=f"🟢 Terhubung ke HP di {client.host}!", fg="#22c55e")
        self.lbl_diagnostic.config(text="")
        self.btn_connect.config(state="normal", text="🚀 HUBUNGKAN KE HP", bg="#ea580c")

        # Minimize or hide Launcher while streaming
        self.root.iconify()

        def stream_session():
            client.start_video_stream()
            client.run_gui()

            # When Pygame stream exits:
            reconnect = client.reconnect_requested
            self.root.after(0, lambda: self.on_stream_closed(reconnect))

        threading.Thread(target=stream_session, daemon=True).start()

    def on_stream_closed(self, reconnect=False):
        self.active_client = None
        self.root.deiconify()
        self.root.lift()

        if reconnect:
            self.start_connection()
        else:
            self.lbl_status.config(text="⚪ Sesi stream selesai. Siap menghubungkan kembali.", fg="#a1a1aa")

    def mainloop(self):
        self.root.mainloop()


# =====================================================================
# CLI / Headless Fallback Mode
# =====================================================================
def run_cli_fallback(target_ip=None):
    print("==================================================")
    print("       SunDroid PC - Remote Android Satset        ")
    print("==================================================")

    cfg = load_config()

    while True:
        if not target_ip:
            print("\nPilih Mode Koneksi:")
            print("1. Mode Kabel USB (ADB) — Latensi < 10ms")
            print("2. Mode Wi-Fi (Masukkan IP HP)")
            print("3. Keluar")
            try:
                choice = input("Pilihan [1/2/3, default 1]: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if choice == "3":
                break
            elif choice == "2":
                try:
                    ip_in = input(f"Masukkan IP HP [default {cfg.get('last_ip', '192.168.1.15')}]: ").strip()
                    target_ip = ip_in if ip_in else cfg.get('last_ip', '192.168.1.15')
                except (EOFError, KeyboardInterrupt):
                    break
            else:
                setup_adb_ports()
                target_ip = "127.0.0.1"

        target_ip = sanitize_host(target_ip)
        print(f"[*] Menghubungkan ke {target_ip}...")

        client = SunDroidClient(host=target_ip, win_height=cfg.get("win_height", 800), show_toolbar=True)
        ok, err = client.connect()

        if ok:
            print(f"[OK] Terhubung ke {target_ip}!")
            client.start_video_stream()
            client.run_gui()
            if not client.reconnect_requested:
                target_ip = None
        else:
            print(f"\n[!] Gagal terhubung ke {target_ip}: {err}")
            print("Pastikan aplikasi SunDroid di HP sudah 'Mulai Remote Host' dan satu jaringan.")
            print("Aplikasi TIDAK ditutup. Anda dapat mencoba lagi.\n")
            target_ip = None


# =====================================================================
# Application Entry Point
# =====================================================================
if __name__ == "__main__":
    # If specific IP passed via argument (e.g. `python client.py 192.168.1.15`)
    if len(sys.argv) > 1:
        arg_ip = sys.argv[1].strip()
        run_cli_fallback(target_ip=arg_ip)
    elif tk is not None:
        try:
            app = SunDroidLauncher()
            app.mainloop()
        except Exception as e:
            print(f"[!] Warning launcher: {e}. Beralih ke CLI...")
            run_cli_fallback()
    else:
        run_cli_fallback()
