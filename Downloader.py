import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import yt_dlp
import os
import sys
import subprocess
import unicodedata
import glob
import time

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def sanitize_filename(name):
    name = unicodedata.normalize('NFKD', name)
    name = "".join(c for c in name if c.isprintable())
    forbidden = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for ch in forbidden:
        name = name.replace(ch, "")
    return name.strip()

def get_ffmpeg_location():
    # Path to ffmpeg.exe in same dir as app, if bundled by PyInstaller
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_path = os.path.join(base_path, 'ffmpeg.exe')
    return ffmpeg_path

ffmpeg_path = get_ffmpeg_location()

class SnapTubeDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SnapTube Downloader - Modern GUI")
        self.geometry("650x500")
        self.minsize(450, 370)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # URL entry
        self.url_label = ctk.CTkLabel(self, text="Enter Video/Playlist URL:")
        self.url_label.pack(pady=(20, 0))
        self.url_entry = ctk.CTkEntry(self, width=500)
        self.url_entry.pack(pady=(0, 12))

        # Download type label
        self.type_label = ctk.CTkLabel(self, text="Select Download Type:")
        self.type_label.pack(pady=(5, 0))

        # Download type selection
        radio_frame = ctk.CTkFrame(self)
        radio_frame.pack(pady=6)
        self.dl_type = ctk.StringVar(value="video")
        self.video_radio = ctk.CTkRadioButton(radio_frame, text="Video", variable=self.dl_type, value="video", font=ctk.CTkFont(size=14))
        self.audio_radio = ctk.CTkRadioButton(radio_frame, text="Audio", variable=self.dl_type, value="audio", font=ctk.CTkFont(size=14))
        self.video_playlist_radio = ctk.CTkRadioButton(radio_frame, text="Video Playlist", variable=self.dl_type, value="video_playlist", font=ctk.CTkFont(size=14))
        self.audio_playlist_radio = ctk.CTkRadioButton(radio_frame, text="Audio Playlist", variable=self.dl_type, value="audio_playlist", font=ctk.CTkFont(size=14))
        self.video_radio.pack(side="left", padx=20, pady=10)
        self.audio_radio.pack(side="left", padx=20, pady=10)
        self.video_playlist_radio.pack(side="left", padx=20, pady=10)
        self.audio_playlist_radio.pack(side="left", padx=20, pady=10)

        # Quality selection
        self.fetch_btn = ctk.CTkButton(self, text="Fetch Qualities", command=self.fetch_qualities)
        self.fetch_btn.pack(pady=(20, 8))
        self.quality_combo = ctk.CTkComboBox(self, values=["Select quality"], state="disabled", width=350)
        self.quality_combo.pack()
        self.quality_map = {}

        # Spinner loading indicator
        self.loading_bar = ctk.CTkProgressBar(self, width=180, mode="indeterminate")
        self.loading_bar.pack(pady=(8, 0))
        self.loading_bar.pack_forget()

        # Folder selection
        folder_frame = ctk.CTkFrame(self)
        folder_frame.pack(pady=(15, 0))
        self.folder_label = ctk.CTkLabel(folder_frame, text="Download Folder:")
        self.folder_label.pack(side="left", padx=(8, 3))
        self.folder_entry = ctk.CTkEntry(folder_frame, width=285)
        self.folder_entry.pack(side="left", padx=5)
        self.folder_entry.insert(0, os.getcwd())
        self.browse_btn = ctk.CTkButton(folder_frame, text="Browse", command=self.browse_folder, width=70)
        self.browse_btn.pack(side="left", padx=(8, 2))

        # Download button and progress/status
        self.download_btn = ctk.CTkButton(self, text="Download", command=self.start_download)
        self.download_btn.pack(pady=(24, 5))
        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.pack(pady=(10, 0))
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.status_label.pack(pady=(8, 0))

    def on_close(self):
        self.destroy()

    def reset_ui(self):
        self.url_entry.delete(0, 'end')
        self.quality_combo.set("Select quality")
        self.quality_combo.configure(state="disabled")
        self.progress.set(0)  # Reset progress bar
        self.status_label.configure(text="Ready", text_color="gray")


    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_entry.delete(0, 'end')
            self.folder_entry.insert(0, folder_selected)

    def fetch_qualities(self):
        url = self.url_entry.get().strip()
        dltype = self.dl_type.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return
        self.quality_combo.set("Loading...")
        self.quality_combo.configure(state="disabled")
        self.quality_map.clear()
        self.loading_bar.pack(pady=(8, 0))
        self.loading_bar.start()
        threading.Thread(target=self._fetch_qualities_thread, args=(url, dltype)).start()

    def _fetch_qualities_thread(self, url, dltype):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'ignoreerrors': True}) as ydl:
                # For all playlist types, fetch first video info for qualities
                is_playlist = dltype in ("video_playlist", "audio_playlist")
                if is_playlist:
                    info = ydl.extract_info(url, download=False)
                    if 'entries' not in info or not info['entries']:
                        raise Exception("No entries found in playlist.")
                    first_video = info['entries'][0]
                    target = first_video
                else:
                    info = ydl.extract_info(url, download=False)
                    target = info

                if dltype in ("audio", "audio_playlist"):
                    formats = [f for f in target['formats'] if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('abr')]
                    display_list = [f"{f.get('abr')} kbps {f['ext']}" for f in formats]
                    format_map = {f"{f.get('abr')} kbps {f['ext']}": f['format_id'] for f in formats}
                else:  # "video" or "video_playlist"
                    formats = [
                        f for f in target['formats']
                        if f.get('height') and f.get('vcodec') != 'none'
                    ]
                    seen = set()
                    display_list = []
                    format_map = {}
                    for f in formats:
                        h = f.get('height')
                        if h and h not in seen:
                            seen.add(h)
                            label = f"{h}p {f['ext']}"
                            display_list.append(label)
                            # Always use bestvideo+bestaudio merging for playlists too
                            format_map[label] = f"bestvideo[height={h}]+bestaudio/best"
                if not display_list:
                    self.after(0, lambda: self._quality_error())
                    self.after(0, lambda: self.loading_bar.stop())
                    self.after(0, lambda: self.loading_bar.pack_forget())
                    return
                self.quality_map = format_map
                self.after(0, lambda: self.quality_combo.configure(values=display_list, state="readonly"))
                self.after(0, lambda: self.quality_combo.set(display_list[0]))
                self.after(0, lambda: self.loading_bar.stop())
                self.after(0, lambda: self.loading_bar.pack_forget())
        except Exception as e:
            self.after(0, lambda: self._quality_error(str(e)))
            self.after(0, lambda: self.loading_bar.stop())
            self.after(0, lambda: self.loading_bar.pack_forget())

    def _quality_error(self, msg="No qualities found for this URL/type!"):
        self.quality_combo.set("Select quality")
        self.quality_combo.configure(state="disabled")
        self.status_label.configure(text=msg, text_color="red")

    def start_download(self):
        url = self.url_entry.get().strip()
        dltype = self.dl_type.get()
        folder = self.folder_entry.get().strip() or os.getcwd()
        quality_display = self.quality_combo.get()
        if not url or not quality_display or quality_display == "Select quality" or quality_display == "Loading...":
            messagebox.showerror("Error", "Please fill in all fields and fetch qualities.")
            return
        format_id = self.quality_map.get(quality_display)
        if not format_id:
            messagebox.showerror("Error", "Please select a valid quality.")
            return
        self.progress.set(0)
        self.status_label.configure(text="Starting download...", text_color="orange")
        self.download_btn.configure(state="disabled")
        threading.Thread(target=self._download_thread, args=(url, dltype, folder, format_id)).start()

    def _download_thread(self, url, dltype, folder, format_id):
        last_filename = [None]
        opened = [False]
        is_playlist = dltype in ("video_playlist", "audio_playlist")

        playlist_folder = folder
        if is_playlist:
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'ignoreerrors': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                playlist_title = info.get('title', 'playlist')
                playlist_title = sanitize_filename(playlist_title)
                playlist_folder = os.path.join(folder, playlist_title)
                os.makedirs(playlist_folder, exist_ok=True)
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(text=f"❌ Playlist Info Error: {e}", text_color="red"))
                self.after(0, lambda: self.download_btn.configure(state="normal"))
                return

        def progress_hook(d):
            if d['status'] == 'downloading' and d.get('total_bytes'):
                frac = d['downloaded_bytes'] / d['total_bytes']
                self.after(0, lambda: self.progress.set(frac))
                self.after(0, lambda: self.status_label.configure(
                    text=f"Downloading... {d['_percent_str']} {d['_speed_str']}", text_color="blue"))
            elif d['status'] == 'finished':
                self.after(0, lambda: self.progress.set(1))
                self.after(0, lambda: self.status_label.configure(text="Processing...", text_color="orange"))


        def post_hook(d):
            if d['status'] == 'finished':
                actual_file = d.get('filepath') or d.get('filename')
                if not actual_file or not os.path.isfile(actual_file):
                    exts = []
                    if dltype in ("audio", "audio_playlist"):
                        exts = ['*.mp3', '*.m4a', '*.ogg', '*.webm']
                    else:
                        exts = ['*.mp4', '*.webm', '*.mkv', '*.mov']
                    files = []
                    for ext in exts:
                        files.extend(glob.glob(os.path.join(playlist_folder, ext)))
                    if files:
                        actual_file = max(files, key=os.path.getctime)
                last_filename[0] = actual_file
                print(f"[DEBUG] Post-hook file detected: {actual_file}")

                # === CLEANUP for audio/audio_playlist ===
                if dltype in ("audio", "audio_playlist"):
                    # Wait a bit to ensure all files written
                    time.sleep(1)
                    basefolder = os.path.dirname(actual_file)
                    for ext in ['*.m4a', '*.webm', '*.ogg']:
                        for f in glob.glob(os.path.join(basefolder, ext)):
                            # Only remove if it's not the mp3 file
                            try:
                                os.remove(f)
                            except Exception as err:
                                print("Couldn't remove temp file:", f, err)

                if not opened[0]:
                    opened[0] = True
                    # If playlist, don't open file, just reset
                    if dltype in ("audio_playlist", "video_playlist"):
                        self.after(0, lambda: self.status_label.configure(text="✅ Download complete!", text_color="green"))
                        self.after(1000, self.reset_ui)
                        self.after(0, lambda: self.download_btn.configure(state="normal"))
                    else:
                        self.after(0, lambda: self.status_label.configure(text="✅ Download complete! Playing...", text_color="green"))
                        self.after(1200, lambda: self.try_open_downloaded_file(last_filename[0], dltype))
                        self.after(2000, self.reset_ui)
                        self.after(0, lambda: self.download_btn.configure(state="normal"))


        # Compose output template for files
        outtmpl_path = os.path.join(
            playlist_folder if is_playlist else folder,
            '%(title).80s-%(id)s.%(ext)s'
        )

        ydl_opts = {
            'format': format_id,
            'outtmpl': outtmpl_path,
            'ffmpeg_location': ffmpeg_path,
            'progress_hooks': [progress_hook],
            'postprocessor_hooks': [post_hook],
        }
        if dltype in ("audio", "audio_playlist"):
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        if is_playlist:
            ydl_opts['ignoreerrors'] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"❌ Error: {e}", text_color="red"))
            self.after(0, lambda: self.download_btn.configure(state="normal"))

    def try_open_downloaded_file(self, filepath, dltype):
        if not filepath or not os.path.isfile(filepath):
            messagebox.showwarning("Open File", "Could not find the downloaded file.")
            return
        try:
            self.open_file(filepath)
        except Exception as e:
            messagebox.showwarning("Open File", f"Could not open file: {e}")

    def open_file(self, filepath):
        print(f"Trying to open file: {filepath}")
        try:
            if sys.platform.startswith('darwin'):
                subprocess.Popen(['open', filepath])
            elif os.name == 'nt':
                os.startfile(filepath)
            elif os.name == 'posix':
                subprocess.Popen(['xdg-open', filepath])
            else:
                messagebox.showinfo("Open File", f"File saved at: {filepath}")
        except Exception as e:
            messagebox.showwarning("Open File", f"Could not open file: {e}")

    def open_folder(self, folderpath):
        try:
            if sys.platform.startswith('darwin'):
                subprocess.Popen(['open', folderpath])
            elif os.name == 'nt':
                os.startfile(folderpath)
            elif os.name == 'posix':
                subprocess.Popen(['xdg-open', folderpath])
        except Exception as e:
            messagebox.showinfo("Open Folder", f"Downloaded to: {folderpath}")

if __name__ == "__main__":
    app = SnapTubeDownloader()
    app.mainloop()
