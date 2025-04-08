import os
import sys
import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox
import json
import time
import psutil
import re
import threading
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import pystray
from PIL import Image, ImageDraw
from plyer import notification
import unicodedata

# Windows startup için pywin32 (win32com) modülünü kullanıyoruz.
try:
    from win32com.client import Dispatch
except ImportError:
    Dispatch = None

# =============================================================================
# AYARLAR ve GLOBAL DEĞİŞKENLER
# =============================================================================

ETS2_MUSIC_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "Euro Truck Simulator 2", "music")
CONFIG_FILE = "config.json"
LOG_FILE = "error.log"

# GUI ve tray referansları
progress_bar_ref = None
root_ref = None
tray_icon_ref = None

# =============================================================================
# BAŞLANGIÇTA UYGULAMAYI OTOMATİK BAŞLATMA (Windows İçin)
# =============================================================================
def add_to_startup():
    """
    Uygulamanın Windows Başlangıç klasörüne kısayol ekler.
    """
    if Dispatch is None:
        log_error("win32com modülü bulunamadı; otostart eklenemiyor.")
        return

    startup_path = os.path.join(os.getenv('APPDATA'), 'Microsoft\\Windows\\Start Menu\\Programs\\Startup')
    shortcut_path = os.path.join(startup_path, "OtoRadio ETS2.lnk")
    target = sys.executable  # Python interpreter yolu
    script = os.path.realpath(__file__)
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target
    # Scripti çalıştıracak argümanları ekliyoruz:
    shortcut.Arguments = f'"{script}"'
    shortcut.WorkingDirectory = os.path.dirname(script)
    shortcut.IconLocation = target
    shortcut.save()
    log_error("Uygulama başlangıç klasörüne eklendi.")

# =============================================================================
# LOG ve DOSYA İŞLEMLERİ
# =============================================================================
def log_error(error_message):
    """Hata mesajlarını log dosyasına yazar."""
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {str(error_message)}\n")

def sanitize_filename(filename):
    """Verilen dosya adını Unicode normalize edip, geçersiz karakterleri kaldırır."""
    filename = unicodedata.normalize('NFKD', filename)
    filename = re.sub(r'[^\w\s-]', '', filename).strip()
    filename = filename.replace(" ", "_")
    return filename

def cleanup_temp_files():
    """ETS2 müzik klasöründeki .part veya .webm uzantılı geçici dosyaları siler."""
    for f in os.listdir(ETS2_MUSIC_FOLDER):
        if f.endswith(".part") or f.endswith(".webm"):
            try:
                os.remove(os.path.join(ETS2_MUSIC_FOLDER, f))
            except Exception as e:
                log_error(f"Geçici dosya silinemedi: {f} - {e}")

# =============================================================================
# İLERLEME GÖSTERME İŞLEVLERİ
# =============================================================================
def update_progress(value):
    global progress_bar_ref
    if progress_bar_ref:
        progress_bar_ref["value"] = int(value)
        root_ref.update_idletasks()

def update_progress_safe(value):
    if root_ref:
        root_ref.after(0, lambda: update_progress(value))

# =============================================================================
# ID3 METADATA İŞLEMLERİ
# =============================================================================
def update_metadata(file_path, title, artist):
    """İndirilen şarkıya ID3 etiketleri ekler."""
    try:
        audio = MP3(file_path, ID3=EasyID3)
        audio["title"] = title
        audio["artist"] = artist
        audio.save()
    except Exception as e:
        log_error(f"{file_path} ID3 etiket hatası: {e}")

# =============================================================================
# YOUTUBE PLAYLIST'İNDEKİ ŞARKILARI İNDİRME
# =============================================================================
def download_missing_songs(youtube_playlist, source, update_progress, quality="192"):
    log_error("Starting download_missing_songs")
    
    # Daha önce indirilmiş dosyalardan video ID'lerini alalım.
    existing_ids = set()
    for f in os.listdir(ETS2_MUSIC_FOLDER):
        if f.endswith(".mp3") and "[" in f and "]" in f:
            match = re.search(r'\[([^\[\]]+)\]', f)
            if match:
                existing_ids.add(match.group(1).lower())
    try:
        ydl_opts = {
            "format": "bestaudio/best",
            # Dosya adını sanitize ederek geçersiz karakterleri kaldırıyoruz.
            "outtmpl": os.path.join(ETS2_MUSIC_FOLDER, "%(title).80s [%(id)s].%(ext)s"),
            "quiet": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }],
            # İndirmenin tamamlandığı aşamada metadata güncelleme için hook
            "progress_hooks": [lambda d: download_hook(d)]
        }

        def download_hook(d):
            if d["status"] == "finished":
                filename = d["filename"]
                info = d.get("info_dict", {})
                title = sanitize_filename(info.get("title", "Bilinmiyor"))
                artist = sanitize_filename(info.get("uploader", "Bilinmiyor"))
                if filename.endswith(".mp3"):
                    update_metadata(filename, title, artist)
                    log_error(f"{filename} indirildi ve metadata güncellendi.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_playlist, download=False)
            entries = info.get("entries", [])
            missing_entries = []
            for entry in entries:
                video_id = entry.get("id")
                if video_id and video_id.lower() not in existing_ids:
                    missing_entries.append(entry.get("webpage_url", entry.get("url")))
            log_error(f"Missing songs: {missing_entries}")
            for i, url in enumerate(missing_entries):
                try:
                    ydl.download([url])
                    update_progress_safe((i + 1) / len(missing_entries) * 100)
                except Exception as e:
                    log_error(f"{url} indirilemedi: {e}")
    except Exception as e:
        log_error(f"Playlist alınamadı: {e}")

# =============================================================================
# ETS2 ÇALIYOR MU? (PROCESS KONTROLÜ)
# =============================================================================
def is_ets2_running():
    for process in psutil.process_iter(attrs=["name"]):
        try:
            if "eurotrucks2.exe" in process.info["name"].lower():
                return True
        except Exception:
            continue
    return False

# =============================================================================
# OTOMATİK SENKRONİZASYON
# =============================================================================
def auto_sync(update_progress, bypass_check=False, quality="192"):
    log_error("Starting auto_sync")
    config = load_config()
    synced_once = False
    while True:
        if bypass_check or is_ets2_running():
            if synced_once:
                time.sleep(5)
                continue
            log_error("Sync koşulları sağlandı. İndirme başlıyor...")
            if not config["youtube_playlist"]:
                notification.notify(
                    title="ETS2 OtoRadio",
                    message="Playlist bulunamadı! Lütfen playlist ekleyin.",
                    timeout=10
                )
                break
            download_missing_songs(config["youtube_playlist"], config["source"], update_progress, quality)
            synced_once = True
            time.sleep(60)
        time.sleep(5)

# =============================================================================
# GUI: ANA KULLANICI ARAYÜZÜ
# =============================================================================
def create_gui():
    global progress_bar_ref, root_ref
    config = load_config()
    root = tk.Tk()
    root_ref = root
    root.title("ETS2 Müzik Yöneticisi")
    root.geometry("500x750")

    # Playlist URL girişi
    tk.Label(root, text="YouTube Playlist URL:").pack(pady=5)
    youtube_entry = tk.Entry(root, width=50)
    youtube_entry.pack(pady=5)
    youtube_entry.insert(0, config["youtube_playlist"])

    # İndirme kalitesi seçenekleri
    tk.Label(root, text="Download Quality:").pack(pady=5)
    quality_var = tk.StringVar(value="192")
    tk.Radiobutton(root, text="128 kbps", variable=quality_var, value="128").pack()
    tk.Radiobutton(root, text="192 kbps", variable=quality_var, value="192").pack()
    tk.Radiobutton(root, text="320 kbps", variable=quality_var, value="320").pack()

    # ETS2 kontrolünü bypass etme seçeneği
    bypass_check_var = tk.BooleanVar()
    tk.Checkbutton(root, text="ETS2 açık olmasa da çalıştır", variable=bypass_check_var).pack(pady=5)

    # İlerleme çubuğu
    progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
    progress.pack(pady=10)
    progress_bar_ref = progress

    # Senkronizasyonu başlat butonu
    def start_sync():
        log_error("Senkronizasyon başlatılıyor.")
        save_config(youtube_entry.get(), "YouTube")
        quality = quality_var.get()
        threading.Thread(target=auto_sync, args=(update_progress_safe, bypass_check_var.get(), quality)).start()
    tk.Button(root, text="Senkronizasyonu Başlat", command=start_sync).pack(pady=10)

    # Log görüntüleme butonu
    def view_logs():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as log:
                log_content = log.read()
        except Exception as e:
            log_content = f"Hata: {e}"
        log_window = tk.Toplevel(root)
        log_window.title("Log Viewer")
        log_window.geometry("600x400")
        log_text = tk.Text(log_window)
        log_text.pack(expand=True, fill="both")
        log_text.insert("1.0", log_content)
    tk.Button(root, text="View Logs", command=view_logs).pack(pady=5)

    # Playlist ekleme butonu
    def add_playlist():
        new_playlist_window = tk.Toplevel(root)
        new_playlist_window.title("Add Playlist")
        new_playlist_window.geometry("400x200")
        tk.Label(new_playlist_window, text="YouTube Playlist URL:").pack(pady=5)
        new_youtube_entry = tk.Entry(new_playlist_window, width=50)
        new_youtube_entry.pack(pady=5)
        def save_new_playlist():
            youtube_playlist = new_youtube_entry.get()
            save_config(youtube_playlist, "YouTube")
            new_playlist_window.destroy()
        tk.Button(new_playlist_window, text="Save", command=save_new_playlist).pack(pady=10)
    tk.Button(root, text="Add Playlist", command=add_playlist).pack(pady=5)

    # Yardım butonu
    def show_readme():
        """Display the Help content in a new window."""
        help_window = tk.Toplevel(root_ref)
        help_window.title("Yardım")
        help_window.geometry("600x400")
        help_text = tk.Text(help_window, wrap="word")
        help_text.pack(expand=True, fill="both")
        help_content = (
            "# ETS2 OtoRadio Yardım\n\n"
            "## Uygulama Nasıl Çalışır?\n"
            "1. **YouTube Playlist URL'si Girin**:\n"
            "   - Uygulamayı açtığınızda, ana ekranda bir giriş alanı göreceksiniz.\n"
            "   - YouTube playlist URL'sini bu alana yapıştırın.\n\n"
            "2. **İndirme Kalitesini Seçin**:\n"
            "   - 128 kbps, 192 kbps veya 320 kbps seçeneklerinden birini seçebilirsiniz.\n\n"
            "3. **Senkronizasyonu Başlatın**:\n"
            "   - 'Senkronizasyonu Başlat' butonuna tıklayın.\n"
            "   - Uygulama, playlist'teki şarkıları indirip ETS2 müzik klasörüne ekleyecektir.\n\n"
            "4. **ETS2 ile Otomatik Senkronizasyon**:\n"
            "   - ETS2 çalışırken uygulama otomatik olarak senkronizasyon yapar.\n\n"
            "## Ek Özellikler\n"
            "- **Log Görüntüleme**:\n"
            "  - 'Logları Görüntüle' butonuna tıklayarak uygulama loglarını inceleyebilirsiniz.\n\n"
            "- **Playlist Ekleme**:\n"
            "  - Yeni bir playlist eklemek için 'Playlist Ekle' butonunu kullanabilirsiniz.\n\n"
            "- **Şarkı Yönetimi**:\n"
            "  - İndirilen şarkıları listeleyebilir, silebilir veya metadata bilgilerini görüntüleyebilirsiniz.\n\n"
            "## Sorun Giderme\n"
            "- **Geçersiz Dosya Adı Hatası**:\n"
            "  - Playlist'teki şarkı adları geçersiz karakterler içeriyorsa, uygulama bu karakterleri otomatik olarak temizler.\n\n"
            "- **Bağlantı Hatası**:\n"
            "  - İnternet bağlantınızı kontrol edin ve playlist URL'sinin doğru olduğundan emin olun.\n\n"
            "## İletişim\n"
            "Herhangi bir sorun veya öneri için geliştiriciyle iletişime geçebilirsiniz.\n"
        )
        help_text.insert("1.0", help_content)
        help_text.config(state="disabled")  # Make the text read-only
    tk.Button(root, text="Yardım", command=show_readme).pack(pady=5)

    # =============================================================================
    # Şarkı Listesi Bölümü (GUI'de indirilmiş şarkıları görüntüleme ve yönetme)
    # =============================================================================
    tk.Label(root, text="İndirilen Şarkılar:").pack(pady=(15, 5))
    song_listbox = tk.Listbox(root, width=60, height=12)
    song_listbox.pack(pady=5)

    def refresh_song_list():
        song_listbox.delete(0, tk.END)
        for filename in sorted(os.listdir(ETS2_MUSIC_FOLDER)):
            if filename.endswith(".mp3"):
                song_listbox.insert(tk.END, filename)

    def open_in_explorer():
        selection = song_listbox.curselection()
        if selection:
            filename = song_listbox.get(selection[0])
            full_path = os.path.join(ETS2_MUSIC_FOLDER, filename)
            try:
                os.startfile(full_path)
            except Exception as e:
                log_error(f"Explorer hatası: {filename} - {e}")

    def delete_song():
        selection = song_listbox.curselection()
        if selection:
            filename = song_listbox.get(selection[0])
            full_path = os.path.join(ETS2_MUSIC_FOLDER, filename)
            try:
                os.remove(full_path)
                refresh_song_list()
            except Exception as e:
                log_error(f"Dosya silinemedi: {filename} - {e}")
                messagebox.showerror("Hata", f"{filename} silinemedi!")

    def show_metadata():
        selection = song_listbox.curselection()
        if selection:
            filename = song_listbox.get(selection[0])
            full_path = os.path.join(ETS2_MUSIC_FOLDER, filename)
            try:
                audio = MP3(full_path, ID3=EasyID3)
                title = audio.get("title", ["Bilinmiyor"])[0]
                artist = audio.get("artist", ["Bilinmiyor"])[0]
                messagebox.showinfo("ID3 Bilgileri", f"🎵 Başlık: {title}\n👤 Sanatçı: {artist}")
            except Exception as e:
                log_error(f"ID3 okunamadı: {filename} - {e}")
                messagebox.showerror("Hata", "Metadata okunamadı!")
    
    # Şarkı yönetim butonları
    tk.Button(root, text="Şarkı Listesini Yenile", command=refresh_song_list).pack(pady=5)
    tk.Button(root, text="Seçilen Şarkıyı Aç", command=open_in_explorer).pack(pady=2)
    tk.Button(root, text="Seçilen Şarkıyı Sil", command=delete_song).pack(pady=2)
    tk.Button(root, text="Metadata Göster", command=show_metadata).pack(pady=2)

    refresh_song_list()
    
    # Kapatılırken GUI'yi gizle (tray'den geri açılabilir)
    def on_close():
        root.withdraw()
    root.protocol("WM_DELETE_WINDOW", on_close)
    
    root.mainloop()

# =============================================================================
# TRAY İKONU İŞLEMLERİ
# =============================================================================
def create_image():
    image = Image.new('RGB', (64, 64), (255, 255, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((32, 0, 64, 32), fill=(255, 0, 0))
    dc.rectangle((0, 32, 32, 64), fill=(0, 255, 0))
    return image

def on_quit(icon, item):
    if root_ref:
        root_ref.quit()
    icon.stop()

def on_tray_click(icon, item):
    threading.Thread(target=show_gui).start()

def setup_tray_icon():
    """Set up the system tray icon."""
    global tray_icon_ref
    tray_icon_ref = pystray.Icon("ETS2 OtoRadio")
    tray_icon_ref.icon = create_image()
    tray_icon_ref.menu = pystray.Menu(
        pystray.MenuItem("Aç", on_tray_click),
        pystray.MenuItem("Quit", on_quit)
    )
    try:
        tray_icon_ref.run()
    except Exception as e:
        log_error(f"Tray icon setup failed: {e}")

def show_gui():
    if root_ref:
        root_ref.deiconify()
    else:
        create_gui()

# =============================================================================
# CONFIGURATION İŞLEMLERİ
# =============================================================================
def load_config():
    """Load configuration from the config file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        log_error("Config file not found. Using default configuration.")
        return {"youtube_playlist": "", "source": "YouTube"}
    except json.JSONDecodeError as e:
        log_error(f"Config file is corrupted: {e}")
        return {"youtube_playlist": "", "source": "YouTube"}

def save_config(youtube_playlist, source):
    """Save configuration to the config file."""
    try:
        config = {"youtube_playlist": youtube_playlist, "source": source}
        with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=4, ensure_ascii=False)
    except Exception as e:
        log_error(f"Failed to save config: {e}")

# =============================================================================
# ANA PROGRAM GİRİŞİ
# =============================================================================
if __name__ == "__main__":
    add_to_startup()
    cleanup_temp_files()
    tray_thread = threading.Thread(target=setup_tray_icon)
    tray_thread.daemon = True
    tray_thread.start()
    create_gui()
