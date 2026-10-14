import os, math, threading, io, random, urllib.request, subprocess, urllib.parse, re, json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance
import yt_dlp

try:
    import librosa
    import numpy as np
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

os.environ["TK_SILENCE_DEPRECATION"] = "1"

def get_ffmpeg_path():
    for p in ["/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.exists(p): return p
    try:
        return subprocess.check_output(["which", "ffmpeg"]).decode("utf-8").strip()
    except Exception:
        return None

def get_ffplay_path():
    for p in ["/usr/local/bin/ffplay", "/opt/homebrew/bin/ffplay"]:
        if os.path.exists(p): return p
    try:
        return subprocess.check_output(["which", "ffplay"]).decode("utf-8").strip()
    except Exception:
        return None

def calculate_bpm_from_audio(y, sr):
    if len(y) == 0: return None
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        bpm_val = float(tempo[0]) if isinstance(tempo, (list, tuple, np.ndarray)) else float(tempo)
        if bpm_val > 0:
            return int(round(bpm_val))
        return None
    except Exception as e:
        print(f"BPM calculation error: {e}")
        return None

def detect_stream_bpm(video_url):
    if not HAS_LIBROSA: return None
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin: return None

    try:
        ydl_opts = {"format": "bestaudio/best", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url") if info else None

        if not stream_url: return None

        cmd = [
            ffmpeg_bin, "-ss", "00:00:10", "-t", "30",
            "-i", stream_url,
            "-f", "s16le", "-ac", "1", "-ar", "22050",
            "-loglevel", "quiet", "-"
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_audio, _ = proc.communicate(timeout=10)

        if not raw_audio or len(raw_audio) < 1000:
            return None

        audio_data = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
        return calculate_bpm_from_audio(audio_data, 22050)

    except Exception as e:
        print(f"Pre-analysis stream BPM error: {e}")
        return None

def detect_file_bpm(file_path):
    if not HAS_LIBROSA or not os.path.exists(file_path): return None
    try:
        y, sr = librosa.load(file_path, duration=60.0, sr=22050)
        return calculate_bpm_from_audio(y, sr)
    except Exception as e:
        print(f"File BPM error: {e}")
        return None

BG_CHASSIS = "#0A0A0A"
PAN_RED = "#D6001C"
PAN_GREEN = "#008751"
PAN_DARK_GREEN = "#004B2D"
ACCENT_WHITE = "#FFFFFF"
LCD_BG = "#000000"           
LCD_TEXT = "#00FF66"         
CARD_BG = "#161616"
ROW_RED = "#D6001C"
ROW_BLACK = "#121212"
ROW_SELECT = "#004B2D"

# Direct SoundCloud API Handler for Instant Performance
SC_CLIENT_ID = None

def get_sc_client_id():
    global SC_CLIENT_ID
    if SC_CLIENT_ID: return SC_CLIENT_ID
    try:
        req = urllib.request.Request("https://soundcloud.com", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
        js_urls = re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html)
        for js_url in js_urls[-3:]:
            try:
                js_content = urllib.request.urlopen(urllib.request.Request(js_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=5).read().decode("utf-8")
                client_id = re.search(r'client_id[:=]"([a-zA-Z0-9]{32})"', js_content)
                if client_id:
                    SC_CLIENT_ID = client_id.group(1)
                    return SC_CLIENT_ID
            except Exception:
                continue
    except Exception:
        pass
    SC_CLIENT_ID = "iZIs9mchVcX52lh2L2491L6v1XnuPqTj" # Fallback public client ID
    return SC_CLIENT_ID

def fetch_sc_direct_playlist(url):
    client_id = get_sc_client_id()
    resolve_url = f"https://api-v2.soundcloud.com/resolve?url={urllib.parse.quote(url)}&client_id={client_id}"
    req = urllib.request.Request(resolve_url, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, timeout=8)
    data = json.loads(res.read().decode("utf-8"))

    tracks_data = []
    
    if data.get("kind") == "playlist":
        raw_tracks = data.get("tracks", [])
        missing_ids = [str(t["id"]) for t in raw_tracks if "title" not in t and "id" in t]
        
        # Batch fetch full track details if playlist contained unhydrated stubs
        hydrated_map = {}
        if missing_ids:
            for i in range(0, len(missing_ids), 50):
                batch = missing_ids[i:i+50]
                batch_url = f"https://api-v2.soundcloud.com/tracks?ids={','.join(batch)}&client_id={client_id}"
                b_req = urllib.request.Request(batch_url, headers={"User-Agent": "Mozilla/5.0"})
                b_data = json.loads(urllib.request.urlopen(b_req, timeout=8).read().decode("utf-8"))
                for t in b_data:
                    hydrated_map[t["id"]] = t

        for t in raw_tracks:
            t_obj = hydrated_map.get(t.get("id"), t)
            if "title" in t_obj:
                title = t_obj.get("title", "Unknown")
                user = t_obj.get("user", {}).get("username", "")
                full_title = f"{user} - {title}" if user and user.lower() not in title.lower() else title
                
                artwork = t_obj.get("artwork_url") or t_obj.get("user", {}).get("avatar_url")
                if artwork:
                    artwork = artwork.replace("-large", "-t500x500").replace("-badge", "-t500x500")

                tracks_data.append({
                    "url": t_obj.get("permalink_url") or url,
                    "title": full_title,
                    "thumbnail": artwork,
                    "bpm": None
                })
    elif data.get("kind") == "track":
        title = data.get("title", "Unknown")
        user = data.get("user", {}).get("username", "")
        full_title = f"{user} - {title}" if user and user.lower() not in title.lower() else title
        artwork = data.get("artwork_url") or data.get("user", {}).get("avatar_url")
        if artwork: artwork = artwork.replace("-large", "-t500x500")
        
        tracks_data.append({
            "url": data.get("permalink_url") or url,
            "title": full_title,
            "thumbnail": artwork,
            "bpm": None
        })

    return tracks_data

class LickMobApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LICK MOB - USB MP3 PLAYER CONVERTER & COVERFLOW")
        self.geometry("1060x940")
        self.minsize(960, 780)
        self.configure(bg=BG_CHASSIS)

        self.playlist_data = []
        self.track_rows = []
        self.active_idx = 0
        self.last_clicked_idx = None

        self.target_scroll_pos = 0.0
        self.current_scroll_pos = 0.0

        self.download_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self.preview_process = None
        self.is_playing_preview = False
        self.preview_lock = threading.Lock()
        self.current_playing_url = None

        self.pil_cache = {}        
        self.cover_tk_cache = {}   
        self.lcd_art_image = None

        self.drag_start_y = None
        self.selection_rect = None

        self.setup_styles()
        self.create_widgets()
        self.animate_vector_canvas()
        self.smooth_scroll_loop()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=BG_CHASSIS)
        self.style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        self.style.configure("SubHeader.TLabel", background=CARD_BG, foreground=PAN_GREEN, font=("Courier", 10, "bold"))
        self.style.configure("Status.TLabel", background=LCD_BG, foreground=LCD_TEXT, font=("Courier", 10, "bold"))
        self.style.configure("Green.TButton", font=("Impact", 12), background=PAN_GREEN, foreground=ACCENT_WHITE, borderwidth=1, relief="raised")
        self.style.map("Green.TButton", background=[("active", PAN_DARK_GREEN)])
        self.style.configure("Red.TButton", font=("Impact", 13), background=PAN_RED, foreground=ACCENT_WHITE, borderwidth=1, relief="raised")
        self.style.map("Red.TButton", background=[("active", "#990014")])
        self.style.configure("Dark.TButton", font=("Helvetica", 9, "bold"), background="#2A2A2A", foreground=ACCENT_WHITE, borderwidth=1)
        self.style.map("Dark.TButton", background=[("active", "#3D3D3D")])
        self.style.configure("Metro.TEntry", fieldbackground="#0A0A0A", foreground=LCD_TEXT, borderwidth=1, padding=5)
        self.style.configure("Custom.Horizontal.TProgressbar", troughcolor="#0A0A0A", background=PAN_RED, thickness=10)

    def draw_star(self, canvas, cx, cy, R, r, fill_color):
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            radius = R if i % 2 == 0 else r
            points.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
        return canvas.create_polygon(points, fill=fill_color, outline="")

    def draw_flag_canton_stars(self, canvas, start_x, start_y, width, height):
        for row in range(9):
            is_even = (row % 2 == 0)
            cols = 6 if is_even else 5
            row_y = start_y + (row + 1) * (height / 10)
            for col in range(cols):
                col_x = start_x + (col + (0.8 if is_even else 1.3)) * (width / 6.5)
                self.draw_star(canvas, col_x, row_y, 15.0, 6.5, BG_CHASSIS)

    def create_widgets(self):
        self.header_canvas = tk.Canvas(self, bg=BG_CHASSIS, height=170, highlightthickness=0)
        self.header_canvas.pack(fill="x", side="top")
        self.draw_static_header_base()

        self.top_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        self.top_card.pack(fill="x", padx=20, pady=6)
        ttk.Label(self.top_card, text="[USB PLAYLIST INPUT URL (YOUTUBE / SOUNDCLOUD)]", style="SubHeader.TLabel").pack(anchor="w", pady=(0, 4))
        input_box = ttk.Frame(self.top_card, style="Card.TFrame")
        input_box.pack(fill="x", expand=True)
        self.url_entry = ttk.Entry(input_box, style="Metro.TEntry", font=("Courier", 10))
        self.url_entry.insert(0, "https://soundcloud.com/ or https://youtube.com/")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.fetch_btn = ttk.Button(input_box, text="FETCH TRACKS", style="Green.TButton", command=self.start_fetch_thread)
        self.fetch_btn.pack(side="right", ipadx=12, ipady=4)

        self.action_bar = ttk.Frame(self)
        self.action_bar.pack(fill="x", padx=20, pady=4)
        ttk.Button(self.action_bar, text="SELECT ALL", style="Dark.TButton", command=self.select_all_tracks).pack(side="left")
        ttk.Button(self.action_bar, text="DESELECT ALL", style="Dark.TButton", command=self.deselect_all_tracks).pack(side="left", padx=8)
        ttk.Button(self.action_bar, text="DIR FOLDER", style="Dark.TButton", command=self.choose_folder).pack(side="left", padx=8)

        self.download_btn = ttk.Button(self.action_bar, text="RIP TO MP3 (192kbps) ★", style="Red.TButton", command=self.start_download_thread, state="disabled")
        self.download_btn.pack(side="right", ipadx=12, ipady=4)

        self.workspace_frame = tk.Frame(self, bg=BG_CHASSIS)
        self.workspace_frame.pack(fill="both", expand=True, padx=20, pady=6)

        coverflow_container = tk.Frame(self.workspace_frame, bg=PAN_RED, bd=2, relief="groove")
        coverflow_container.pack(fill="x", side="top", pady=(0, 10))

        self.flow_canvas = tk.Canvas(coverflow_container, bg="#050505", height=230, highlightthickness=0)
        self.flow_canvas.pack(fill="x", expand=True)

        self.flow_canvas.bind("<MouseWheel>", self.on_flow_scroll)
        self.flow_canvas.bind("<Button-4>", lambda e: self.step_scroll(-1))
        self.flow_canvas.bind("<Button-5>", lambda e: self.step_scroll(1))
        self.flow_canvas.bind("<Button-1>", self.on_flow_click)
        self.bind("<Left>", lambda e: self.step_scroll(-1))
        self.bind("<Right>", lambda e: self.step_scroll(1))

        self.transport_canvas = tk.Canvas(coverflow_container, bg="#0A0A0A", height=68, highlightthickness=0)
        self.transport_canvas.pack(fill="x", side="bottom")
        
        self.transport_canvas.bind("<Button-1>", self.on_transport_click)
        self.transport_canvas.bind("<Configure>", lambda e: self.render_transport_bar())

        list_container = tk.Frame(self.workspace_frame, bg=PAN_RED, bd=2, relief="groove")
        list_container.pack(fill="both", expand=True)

        list_header_bar = tk.Frame(list_container, bg=PAN_GREEN, height=24)
        list_header_bar.pack(fill="x", side="top")
        tk.Label(list_header_bar, text=" ★  TRACK INDEX", bg=PAN_GREEN, fg=ACCENT_WHITE, font=("Impact", 10), anchor="w").pack(side="left", padx=10, pady=2)

        self.list_canvas = tk.Canvas(list_container, bg=ROW_BLACK, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.list_canvas.yview)
        self.scroll_content = tk.Frame(self.list_canvas, bg=ROW_BLACK)
        
        self.scroll_content.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.canvas_window = self.list_canvas.create_window((0, 0), window=self.scroll_content, anchor="nw")
        
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfig(self.canvas_window, width=e.width))
        self.list_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.bind_widget_scroll(self.list_canvas)
        self.bind_widget_scroll(self.scroll_content)
        self.bind_widget_scroll(list_container)

        self.list_canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.list_canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.list_canvas.bind("<ButtonRelease-1>", self.on_drag_stop)

        lcd_footer_frame = tk.Frame(self, bg=LCD_BG, bd=2, relief="sunken")
        lcd_footer_frame.pack(fill="x", padx=20, pady=(2, 4))
        self.status_label = ttk.Label(lcd_footer_frame, text=f"DISK LOCATION: {self.download_folder}", style="Status.TLabel")
        self.status_label.pack(fill="x", padx=10, pady=2)
        self.progress_bar = ttk.Progressbar(self, style="Custom.Horizontal.TProgressbar", mode="determinate")
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 10))

        self.render_transport_bar()

    def draw_static_header_base(self):
        c = self.header_canvas
        c.delete("static_h")
        c.create_rectangle(0, 0, 1060, 170, fill=BG_CHASSIS, outline="", tags="static_h")
        
        c.create_rectangle(10, 50, 55, 110, fill=PAN_GREEN, outline=PAN_DARK_GREEN, width=2, tags="static_h")
        c.create_rectangle(55, 38, 85, 122, fill=PAN_DARK_GREEN, outline=BG_CHASSIS, width=2, tags="static_h")
        
        body_x1, body_x2 = 85, 1040
        c.create_rectangle(body_x1, 10, body_x2, 160, fill=PAN_RED, outline=BG_CHASSIS, width=3, tags="static_h")

        array_x1 = 340
        array_x2 = body_x2 - 10
        array_y1 = 15
        array_y2 = 155
        num_stripes = 7
        stripe_h = (array_y2 - array_y1) / num_stripes

        for i in range(num_stripes):
            ry1 = array_y1 + (i * stripe_h)
            ry2 = ry1 + stripe_h
            color = PAN_RED if i % 2 == 0 else BG_CHASSIS
            c.create_rectangle(array_x1, ry1, array_x2, ry2, fill=color, outline="", tags="static_h")

        c.create_rectangle(90, 15, 340, 155, fill=PAN_GREEN, outline=PAN_DARK_GREEN, width=2, tags="static_h")
        self.draw_flag_canton_stars(c, 90, 15, 250, 140)
        
        c.create_text(215, 62, text="LICK MOB", font=("Georgia", 26, "bold"), fill=ACCENT_WHITE, anchor="center", tags="static_h")
        c.create_text(215, 102, text="YT / SOUNDCLOUD CONVERTER", font=("Impact", 11), fill=LCD_TEXT, anchor="center", tags="static_h")

        c.create_rectangle(386, 21, 984, 149, fill=BG_CHASSIS, outline=PAN_GREEN, width=2, tags="static_h")
        c.create_rectangle(390, 25, 980, 145, fill=LCD_BG, outline=LCD_TEXT, width=2, tags="static_h")

    def render_transport_bar(self):
        c = self.transport_canvas
        c.delete("t_ui")

        w = c.winfo_width() or 1000
        cy = 34
        cx = w // 2

        c.create_line(0, 0, w, 0, fill=PAN_RED, width=2, tags="t_ui")

        pw, ph = 230, 36
        x1, y1 = cx - pw // 2, cy - ph // 2
        x2, y2 = cx + pw // 2, cy + ph // 2
        r = ph // 2

        c.create_oval(x1, y1, x1 + 2*r, y2, fill="#121212", outline=PAN_GREEN, width=1.5, tags="t_ui")
        c.create_oval(x2 - 2*r, y1, x2, y2, fill="#121212", outline=PAN_GREEN, width=1.5, tags="t_ui")
        c.create_rectangle(x1 + r, y1, x2 - r, y2, fill="#121212", outline="", tags="t_ui")

        c.create_line(x1 + r, y1, x2 - r, y1, fill=PAN_GREEN, width=1.5, tags="t_ui")
        c.create_line(x1 + r, y2, x2 - r, y2, fill=PAN_GREEN, width=1.5, tags="t_ui")

        c.create_oval(x1 + 3, y1 + 2, x1 + 2*r - 3, cy, fill="#222222", outline="", tags="t_ui")
        c.create_oval(x2 - 2*r + 3, y1 + 2, x2 - 3, cy, fill="#222222", outline="", tags="t_ui")
        c.create_rectangle(x1 + r, y1 + 2, x2 - r, cy, fill="#222222", outline="", tags="t_ui")

        c.create_rectangle(cx - 72, cy - 7, cx - 69, cy + 7, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_prev"))
        c.create_polygon(cx - 53, cy - 8, cx - 67, cy, cx - 53, cy + 8, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_prev"))
        c.create_polygon(cx - 40, cy - 8, cx - 54, cy, cx - 40, cy + 8, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_prev"))

        c.create_polygon(cx + 40, cy - 8, cx + 54, cy, cx + 40, cy + 8, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_next"))
        c.create_polygon(cx + 53, cy - 8, cx + 67, cy, cx + 53, cy + 8, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_next"))
        c.create_rectangle(cx + 69, cy - 7, cx + 72, cy + 7, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_next"))

        orb_r = 26
        orb_color = PAN_RED if self.is_playing_preview else PAN_GREEN
        glow_color = "#FF3344" if self.is_playing_preview else LCD_TEXT

        c.create_oval(cx - orb_r - 2, cy - orb_r - 2, cx + orb_r + 2, cy + orb_r + 2, fill=PAN_DARK_GREEN if not self.is_playing_preview else "#770000", outline=glow_color, width=2, tags=("t_ui", "btn_play"))
        c.create_oval(cx - orb_r, cy - orb_r, cx + orb_r, cy + orb_r, fill=orb_color, outline=ACCENT_WHITE, width=1.5, tags=("t_ui", "btn_play"))
        
        c.create_oval(cx - orb_r + 3, cy - orb_r + 2, cx + orb_r - 3, cy + 1, fill="#FF6677" if self.is_playing_preview else "#00A862", outline="", tags=("t_ui", "btn_play"))

        if not self.is_playing_preview:
            c.create_polygon(cx - 6, cy - 10, cx + 12, cy, cx - 6, cy + 10, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_play"))
        else:
            s = 9
            c.create_rectangle(cx - s, cy - s, cx + s, cy + s, fill=ACCENT_WHITE, outline="", tags=("t_ui", "btn_play"))

    def on_transport_click(self, event):
        c = self.transport_canvas
        clicked = c.find_withtag("current")
        if not clicked: return

        tags = c.gettags(clicked[0])
        if "btn_play" in tags:
            self.toggle_preview_audio()
        elif "btn_prev" in tags:
            self.step_scroll(-1)
        elif "btn_next" in tags:
            self.step_scroll(1)

    def on_list_trackpad_scroll(self, event):
        if event.delta != 0:
            scroll_units = -1 if event.delta > 0 else 1
            if abs(event.delta) > 10:
                scroll_units = int(-1 * (event.delta / 30))
            self.list_canvas.yview_scroll(scroll_units, "units")

    def bind_widget_scroll(self, widget):
        widget.bind("<MouseWheel>", self.on_list_trackpad_scroll)
        widget.bind("<Button-4>", lambda e: self.list_canvas.yview_scroll(-3, "units"))
        widget.bind("<Button-5>", lambda e: self.list_canvas.yview_scroll(3, "units"))

    def animate_vector_canvas(self):
        c = self.header_canvas
        c.delete("anim")

        if self.lcd_art_image:
            c.create_image(445, 85, image=self.lcd_art_image, tags="anim")
            c.create_rectangle(398, 38, 492, 132, outline=LCD_TEXT, width=2, tags="anim")
        else:
            c.create_rectangle(398, 38, 492, 132, fill="#0A0A0A", outline=LCD_TEXT, width=1, tags="anim")
            c.create_oval(415, 55, 475, 115, fill="#000000", outline=LCD_TEXT, width=1, tags="anim")
            c.create_oval(438, 78, 452, 92, fill=PAN_RED, outline="", tags="anim")

        c.create_text(505, 43, text="[USB 2.0] MP3-192K", font=("Courier", 10, "bold"), fill=LCD_TEXT, anchor="w", tags="anim")
        c.create_text(965, 43, text="VOL: 100%", font=("Courier", 10, "bold"), fill=LCD_TEXT, anchor="e", tags="anim")
        
        selected_item = self.track_rows[self.active_idx]["item"] if self.track_rows else None
        track_title = selected_item["title"] if selected_item else "NO TRACK SELECTED"
        if len(track_title) > 28:
            track_title = track_title[:26] + "..."
        c.create_text(505, 80, text=track_title, font=("Georgia", 16, "bold"), fill=ACCENT_WHITE, anchor="w", tags="anim")
        
        status_txt = "PLAYING PREVIEW..." if self.is_playing_preview else "READY / IDLE"
        c.create_text(505, 118, text=status_txt, font=("Impact", 13), fill=LCD_TEXT, anchor="w", tags="anim")

        eq_x = 900
        eq_y = 115
        for b in range(8):
            bar_h = random.randint(10, 32) if self.is_playing_preview else 2
            c.create_rectangle(
                eq_x + (b * 8), eq_y - bar_h,
                eq_x + (b * 8) + 5, eq_y,
                fill=LCD_TEXT, outline="", tags="anim"
            )

        self.after(50, self.animate_vector_canvas)

    def generate_placeholder_pil(self, title):
        img = Image.new("RGBA", (220, 220), (20, 20, 20, 255))
        for r in range(100, 25, -10):
            color = (40, 40, 40, 255) if r % 2 == 0 else (15, 15, 15, 255)
            from PIL import ImageDraw
            d = ImageDraw.Draw(img)
            d.ellipse([110 - r, 110 - r, 110 + r, 110 + r], outline=color, width=2)
        d.ellipse([75, 75, 145, 145], fill=(214, 0, 28, 255), outline=(255, 255, 255, 255), width=2)
        return img

    def transform_cover_perspective(self, base_pil, side, scale=1.0):
        w, h = 180, 180
        img = base_pil.resize((w, h), Image.Resampling.LANCZOS).convert("RGBA")

        if side != 0:
            skew_factor = 0.30
            nw_h = int(h * (1.0 - skew_factor))
            offset_y = (h - nw_h) // 2

            if side < 0:
                pts = (0, 0, 0, h, int(w * 0.45), h - offset_y, int(w * 0.45), offset_y)
            else:
                pts = (int(w * 0.55), offset_y, int(w * 0.55), h - offset_y, w, h, w, 0)

            img = img.transform((w, h), Image.Transform.QUAD, pts, Image.Resampling.BILINEAR)

            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(0.55)

        if scale < 0.99:
            nw, nh = max(10, int(w * scale)), max(10, int(h * scale))
            img = img.resize((nw, nh), Image.Resampling.BILINEAR)

        ref_h = int(img.height * 0.38)
        reflection = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM).crop((0, img.height - ref_h, img.width, img.height))
        
        alpha_mask = Image.new("L", (img.width, ref_h), 0)
        for y in range(ref_h):
            alpha_val = int(70 * (1.0 - (y / ref_h)))
            for x in range(img.width):
                alpha_mask.putpixel((x, y), alpha_val)
        reflection.putalpha(alpha_mask)

        combined = Image.new("RGBA", (img.width, img.height + ref_h + 8), (0, 0, 0, 0))
        combined.paste(img, (0, 0), img)
        combined.paste(reflection, (0, img.height + 4), reflection)

        return combined

    def smooth_scroll_loop(self):
        diff = self.target_scroll_pos - self.current_scroll_pos
        if abs(diff) > 0.001:
            self.current_scroll_pos += diff * 0.28
            self.render_coverflow()
        elif abs(diff) > 0:
            self.current_scroll_pos = self.target_scroll_pos
            self.render_coverflow()

        self.after(25, self.smooth_scroll_loop)

    def render_coverflow(self):
        c = self.flow_canvas
        c.delete("flow")
        
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 100 or ch < 100: return

        center_x = cw // 2
        center_y = ch // 2 - 15

        c.create_line(0, center_y + 90, cw, center_y + 90, fill="#1A1A1A", width=2, tags="flow")

        total = len(self.track_rows)
        if total == 0:
            c.create_text(center_x, center_y, text="NO TRACKS LOADED\nEnter YouTube or SoundCloud URL and click [FETCH TRACKS]", font=("Impact", 14), fill="#444444", tags="flow")
            return

        indices = list(range(total))
        indices.sort(key=lambda i: -abs(i - self.current_scroll_pos))

        for i in indices:
            offset = i - self.current_scroll_pos
            abs_offset = abs(offset)

            if abs_offset > 4.5: continue

            side = 0
            if offset < -0.15: side = -1
            elif offset > 0.15: side = 1

            spacing = 135 if side == 0 else 85
            x = center_x + int(offset * spacing) + (side * 50)
            scale = max(0.5, 1.0 - (abs_offset * 0.14)) if side != 0 else 1.0
            y = center_y + int(abs_offset * 10)

            item = self.track_rows[i]["item"]
            pil_base = self.pil_cache.get(item["url"], self.generate_placeholder_pil(item["title"]))

            cache_key = (item["url"], side, round(scale, 2))
            if cache_key not in self.cover_tk_cache:
                transformed = self.transform_cover_perspective(pil_base, side, scale)
                self.cover_tk_cache[cache_key] = ImageTk.PhotoImage(transformed)

            tk_img = self.cover_tk_cache[cache_key]
            c.create_image(x, y, image=tk_img, anchor="center", tags=("flow", f"cover_{i}"))

            if i == self.active_idx and side == 0:
                c.create_text(center_x, center_y + 120, text=item["title"], font=("Georgia", 12, "bold"), fill=ACCENT_WHITE, tags="flow")

    def on_flow_scroll(self, event):
        delta = -1 if event.delta > 0 else 1
        self.step_scroll(delta)

    def step_scroll(self, delta):
        if not self.track_rows: return
        new_idx = max(0, min(len(self.track_rows) - 1, self.active_idx + delta))
        if new_idx != self.active_idx:
            self.select_track_index(new_idx, start_preview=True)

    def on_flow_click(self, event):
        c = self.flow_canvas
        clicked = c.find_withtag("current")
        if not clicked: return
        
        tags = c.gettags(clicked[0])
        for tag in tags:
            if tag.startswith("cover_"):
                idx = int(tag.split("_")[1])
                if idx == self.active_idx:
                    self.toggle_preview_audio()
                else:
                    self.select_track_index(idx, start_preview=True)
                break

    def select_track_index(self, idx, start_preview=False):
        if idx < 0 or idx >= len(self.track_rows): return

        if self.active_idx < len(self.track_rows):
            prev_row = self.track_rows[self.active_idx]
            prev_row["frame"].configure(bg=prev_row["bg"])
            prev_row["label"].configure(bg=prev_row["bg"])
            prev_row["checkbox"].configure(bg=prev_row["bg"], activebackground=prev_row["bg"])

        self.active_idx = idx
        self.target_scroll_pos = float(idx)
        curr_row = self.track_rows[idx]

        curr_row["frame"].configure(bg=ROW_SELECT)
        curr_row["label"].configure(bg=ROW_SELECT)
        curr_row["checkbox"].configure(bg=ROW_SELECT, activebackground=ROW_SELECT)

        self.ensure_row_visible(curr_row["frame"])

        item = curr_row["item"]
        pil_base = self.pil_cache.get(item["url"], self.generate_placeholder_pil(item["title"]))
        lcd_img = pil_base.resize((90, 90), Image.Resampling.LANCZOS)
        self.lcd_art_image = ImageTk.PhotoImage(lcd_img)

        self.render_coverflow()

        if start_preview:
            self.start_preview_audio()

    def ensure_row_visible(self, row_frame):
        self.update_idletasks()
        try:
            row_y = row_frame.winfo_y()
            content_h = self.scroll_content.winfo_height()
            if content_h > 0:
                self.list_canvas.yview_moveto(max(0.0, min(1.0, row_y / content_h)))
        except Exception:
            pass

    def on_track_click(self, event, idx):
        is_shift = (event.state & 0x0001) != 0

        if is_shift and self.last_clicked_idx is not None:
            start = min(self.last_clicked_idx, idx)
            end = max(self.last_clicked_idx, idx)
            for i in range(start, end + 1):
                self.track_rows[i]["var"].set(True)
            self.render_coverflow()
        else:
            if self.active_idx == idx and self.is_playing_preview:
                self.stop_audio_preview()
            else:
                self.select_track_index(idx, start_preview=True)

        self.last_clicked_idx = idx

    def on_drag_start(self, event):
        self.drag_start_y = event.y
        if self.selection_rect:
            self.list_canvas.delete(self.selection_rect)

    def on_drag_motion(self, event):
        if self.drag_start_y is None: return
        y1, y2 = min(self.drag_start_y, event.y), max(self.drag_start_y, event.y)
        
        if not self.selection_rect:
            self.selection_rect = self.list_canvas.create_rectangle(0, y1, self.list_canvas.winfo_width(), y2, outline=LCD_TEXT, fill="#008751", stipple="gray25")
        else:
            self.list_canvas.coords(self.selection_rect, 0, y1, self.list_canvas.winfo_width(), y2)

        for row in self.track_rows:
            rf = row["frame"]
            ry1 = rf.winfo_y()
            ry2 = ry1 + rf.winfo_height()
            if (ry1 >= y1 and ry1 <= y2) or (ry2 >= y1 and ry2 <= y2):
                row["var"].set(True)

    def on_drag_stop(self, event):
        if self.selection_rect:
            self.list_canvas.delete(self.selection_rect)
            self.selection_rect = None
        self.drag_start_y = None

    def select_all_tracks(self):
        for row_dict in self.track_rows: row_dict["var"].set(True)
        self.render_coverflow()

    def deselect_all_tracks(self):
        for row_dict in self.track_rows: row_dict["var"].set(False)
        self.render_coverflow()

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.status_label.configure(text=f"DISK LOCATION: {self.download_folder}")

    def start_fetch_thread(self):
        url = self.url_entry.get().strip()
        if not url or ("http://" not in url and "https://" not in url):
            messagebox.showwarning("Invalid Link", "Please enter a valid YouTube or SoundCloud URL.")
            return
        self.fetch_btn.configure(state="disabled")
        self.status_label.configure(text="STATUS: Parsing playlist / set info...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)
        threading.Thread(target=self.fetch_playlist, args=(url,), daemon=True).start()

    def fetch_playlist(self, raw_url):
        try:
            clean_url = raw_url.strip()
            
            # Fast-path for SoundCloud via direct API v2
            if "soundcloud.com" in clean_url.lower():
                try:
                    self.playlist_data = fetch_sc_direct_playlist(clean_url)
                    self.after(0, self.populate_tracks)
                    return
                except Exception as sc_err:
                    print(f"Direct SC API failed, falling back to yt-dlp: {sc_err}")

            # Fallback / YouTube handling via yt-dlp
            ydl_opts = {
                "extract_flat": True,
                "skip_download": True,
                "quiet": True,
                "no_warnings": True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                entries = info.get("entries", [info]) if info else []
                
                self.playlist_data = []
                for entry in entries:
                    if entry:
                        v_id = entry.get("id") or entry.get("url")
                        thumbs = entry.get("thumbnails") or []
                        thumb_url = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg"
                        self.playlist_data.append({
                            "url": f"https://www.youtube.com/watch?v={v_id}" if "youtube" in clean_url or "youtu.be" in clean_url else clean_url,
                            "title": entry.get("title", "Unknown Track"),
                            "thumbnail": thumb_url,
                            "bpm": None
                        })

            self.after(0, self.populate_tracks)
        except Exception as e:
            self.after(0, lambda: self.handle_fetch_error(str(e)))

    def populate_tracks(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", value=0)
        self.fetch_btn.configure(state="normal")
        
        for widget in self.scroll_content.winfo_children(): widget.destroy()
        self.track_rows.clear()
        self.pil_cache.clear()
        self.cover_tk_cache.clear()
        self.active_idx = 0
        self.last_clicked_idx = None

        for idx, item in enumerate(self.playlist_data):
            bg_color = ROW_RED if idx % 2 == 0 else ROW_BLACK
            
            row_frame = tk.Frame(self.scroll_content, bg=bg_color)
            row_frame.pack(fill="x", expand=True)
            
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(
                row_frame, variable=var, bg=bg_color, activebackground=bg_color,
                selectcolor=BG_CHASSIS
            )
            cb.pack(side="left", padx=(10, 5), pady=5)

            title_label = tk.Label(
                row_frame, text=f"{item['title']}  [Analyzing BPM...]",
                bg=bg_color, fg=ACCENT_WHITE, font=("Helvetica", 10, "bold"), anchor="w"
            )
            title_label.pack(side="left", fill="x", expand=True, pady=5)

            row_dict = {
                "idx": idx,
                "item": item,
                "frame": row_frame,
                "label": title_label,
                "checkbox": cb,
                "var": var,
                "bg": bg_color
            }
            self.track_rows.append(row_dict)

            row_frame.bind("<Button-1>", lambda e, index=idx: self.on_track_click(e, index))
            title_label.bind("<Button-1>", lambda e, index=idx: self.on_track_click(e, index))

            self.bind_widget_scroll(row_frame)
            self.bind_widget_scroll(title_label)
            self.bind_widget_scroll(cb)

            threading.Thread(target=self.bg_fetch_artwork_and_bpm, args=(item, title_label), daemon=True).start()

        self.download_btn.configure(state="normal")
        self.status_label.configure(text=f"STATUS: Loaded {len(self.track_rows)} tracks.")
        if self.track_rows:
            self.select_track_index(0, start_preview=False)

    def bg_fetch_artwork_and_bpm(self, item, label_widget):
        if item.get("thumbnail"):
            try:
                req = urllib.request.Request(item["thumbnail"], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    img = Image.open(io.BytesIO(response.read())).convert("RGBA")
                    w, h = img.size
                    m = min(w, h)
                    cropped = img.crop(((w-m)/2, (h-m)/2, (w+m)/2, (h+m)/2))
                    self.pil_cache[item["url"]] = cropped
            except Exception:
                pass

        self.after(0, self.render_coverflow)

        bpm_val = detect_stream_bpm(item["url"])
        if bpm_val:
            item["bpm"] = bpm_val
            self.after(0, lambda: label_widget.configure(text=f"{item['title']}  [{bpm_val} BPM]"))
            self.after(0, self.render_coverflow)
        else:
            self.after(0, lambda: label_widget.configure(text=item["title"]))

    def stop_audio_preview(self):
        with self.preview_lock:
            if self.preview_process:
                try:
                    self.preview_process.kill()
                    self.preview_process.wait()
                except Exception:
                    pass
                self.preview_process = None
            self.is_playing_preview = False
            self.current_playing_url = None
        self.after(0, self.render_transport_bar)

    def start_preview_audio(self):
        if not self.track_rows: return
        item = self.track_rows[self.active_idx]["item"]
        target_url = item["url"]
        self.stop_audio_preview()
        self.is_playing_preview = True
        self.current_playing_url = target_url
        self.after(0, self.render_transport_bar)
        threading.Thread(target=self.stream_preview_worker, args=(target_url,), daemon=True).start()

    def toggle_preview_audio(self):
        if self.is_playing_preview: 
            self.stop_audio_preview()
        else:
            self.start_preview_audio()

    def stream_preview_worker(self, video_url):
        ffplay_bin = get_ffplay_path()
        if not ffplay_bin:
            self.after(0, self.stop_audio_preview)
            return

        try:
            with yt_dlp.YoutubeDL({"format": "bestaudio/best", "quiet": True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                stream_url = info.get("url") if info else None
            
            with self.preview_lock:
                if not self.is_playing_preview or self.current_playing_url != video_url or not stream_url:
                    return

                self.preview_process = subprocess.Popen(
                    [ffplay_bin, "-nodisp", "-autoexit", "-t", "30", stream_url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

            self.preview_process.wait()

        except Exception as e:
            print(f"Preview worker error: {e}")

        with self.preview_lock:
            if self.current_playing_url == video_url:
                self.after(0, self.stop_audio_preview)

    def handle_fetch_error(self, err_msg):
        self.progress_bar.stop()
        self.fetch_btn.configure(state="normal")
        messagebox.showerror("Error", f"Failed to load playlist:\n{err_msg}")

    def start_download_thread(self):
        selected_rows = [row for row in self.track_rows if row["var"].get()]
        if selected_rows:
            self.download_btn.configure(state="disabled")
            threading.Thread(target=self.download_tracks, args=(selected_rows,), daemon=True).start()

    def download_tracks(self, selected_rows):
        total = len(selected_rows)
        ffmpeg_bin = get_ffmpeg_path()
        for idx, row in enumerate(selected_rows, start=1):
            track = row["item"]
            self.after(0, lambda i=idx, t=track["title"]: self.status_label.configure(text=f"STATUS: [{i}/{total}] Downloading: {t}"))
            
            opts = {
                "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                "outtmpl": os.path.join(self.download_folder, "%(title)s.%(ext)s"),
                "quiet": True
            }
            if ffmpeg_bin: opts["ffmpeg_location"] = ffmpeg_bin
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([track["url"]])
                out_path = os.path.join(self.download_folder, f"{track['title']}.mp3")
                file_bpm = detect_file_bpm(out_path)
                if file_bpm:
                    track["bpm"] = file_bpm
                    lbl_widget = row["label"]
                    self.after(0, lambda l=lbl_widget, t=track["title"], b=file_bpm: l.configure(text=f"{t}  [{b} BPM]"))
                    self.after(0, self.render_coverflow)
                        
            except Exception as e: print(e)
            self.after(0, lambda p=(idx / total) * 100: self.progress_bar.configure(value=p))
        self.after(0, self.finish_download)

    def finish_download(self):
        self.download_btn.configure(state="normal")
        self.fetch_btn.configure(state="normal")
        messagebox.showinfo("Complete", "All selected tracks converted!")

if __name__ == "__main__":
    app = LickMobApp()
    app.mainloop()
