import sys
import os
import platform
import shutil
import subprocess
import threading
import json
import time
import webbrowser
import signal
import locale
from pathlib import Path

PLATFORM = "windows" if platform.system() == "Windows" else (
    "linux" if platform.system() == "Linux" else "other")

# ============================================================
#  LINUX OTOMATİK KURULUM VE SİGORTA MEKANİZMASI (BOOTSTRAP)
# ============================================================
if PLATFORM == "linux" and not getattr(sys, "frozen", False):
    # Bu bootstrap (venv kurma, apt install yapma) SADECE ham .pyw script
    # olarak calistirildiginda anlamlidir. PyInstaller ile derlenmis (frozen)
    # haldeyken customtkinter/Pillow/opencv zaten _internal klasorune
    # gomulu oldugu icin bu bloga hic girilmemeli - aksi halde sys.executable
    # derlenmis programin KENDISINI gosterir ve asagidaki subprocess.run
    # satiri kendini sonsuz dongude yeniden calistirmaya calisir.
    BASE_DIR = Path(__file__).resolve().parent
    VENV_DIR = BASE_DIR / "venv"
    VENV_PYTHON = VENV_DIR / "bin" / "python3"

    if sys.executable != str(VENV_PYTHON):

        # shutil.which kullanimi: subprocess+shell=True'daki liste hatasini
        # ortadan kaldirir, dogrudan ve guvenilir calisir.
        sistem_tam = (
            shutil.which("wmctrl") is not None
            and shutil.which("xdotool") is not None
        )
        try:
            subprocess.run([sys.executable, "-c", "import tkinter"],
                            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            sistem_tam = False

        if not sistem_tam or not VENV_PYTHON.exists():
            if "LAUNCHER_TERMINAL" not in os.environ:
                os.environ["LAUNCHER_TERMINAL"] = "1"
                # Her terminalin komut calistirma sozdizimi farkli:
                # gnome-terminal/xfce4-terminal "--" bekler, konsole/xterm "-e" bekler.
                terminal_komutlari = [
                    ["gnome-terminal", "--"],
                    ["xfce4-terminal", "--"],
                    ["konsole", "-e"],
                    ["xterm", "-e"],
                ]
                for onek in terminal_komutlari:
                    term_binary = onek[0]
                    if shutil.which(term_binary) is None:
                        continue
                    try:
                        subprocess.run(onek + [sys.executable] + sys.argv)
                        sys.exit(0)
                    except FileNotFoundError:
                        continue
                # Hicbir terminal bulunamadiysa (cok nadir), mevcut kabukta devam et
                print("[UYARI] Bilinen bir terminal emulatoru bulunamadi, kurulum bu pencerede devam ediyor.")

            print("=====================================================")
            print("  Spider-Man TR Linux Otomatik Bağımlılık Kurulumu   ")
            print("=====================================================")

            if not sistem_tam:
                print("\n[SİSTEM] Eksik sistem araçları (wmctrl, xdotool, tkinter) kuruluyor...")
                print("(Lütfen Linux yönetici şifrenizi giriniz)")
                subprocess.run(["sudo", "apt", "update"])
                subprocess.run(["sudo", "apt", "install", "-y", "python3-tk", "python3-venv", "wmctrl", "xdotool"])

            if not VENV_PYTHON.exists():
                print("\n[KURULUM] Güvenli Python Sanal Ortamı (venv) oluşturuluyor...")
                subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])

            print("\n[KURULUM] Gerekli Python kütüphaneleri yükleniyor (customtkinter, Pillow, cv2...)...")
            subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
            subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "customtkinter", "Pillow", "opencv-python", "mss", "numpy"])
            print("\n[BAŞARILI] Kurulum tamamlandı! Arayüz açılıyor...")
            time.sleep(1)

        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

# ============================================================
#  AĞIR İMPORTLAR (Çökmeyi önlemek için bootstrap sonrasına alındı)
# ============================================================
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import customtkinter as ctk
import game_setup

APP_NAME = "SpiderManTR"

def exe_klasoru() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def gomulu_kaynak_klasoru() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "kaynaklar"
    return Path(__file__).resolve().parent / "kaynaklar"

# ============================================================
#  DOĞRUDAN "kaynaklar" ÜZERİNDEN ÇALIŞMA (6GB kopyalama YOK)
# ============================================================
# --onedir modunda "kaynaklar" zaten programin YANINDA kalici olarak
# duruyor (gecici bir yere acilmiyor) - bu yuzden ayrica bir
# "SpiderManTR_Data" kopyasi olusturmaya hic gerek yok. DuckStation,
# BIN'ler ve overlay dogrudan bu klasorden calisir; save'ler de
# (memcards) yine bu klasorun icinde, kalici bir alt klasorde tutulur.
KAYNAKLAR_KLASORU = gomulu_kaynak_klasoru()
DUCKSTATION_KLASORU = KAYNAKLAR_KLASORU / "duckstation"
MEMCARDS_KLASORU = KAYNAKLAR_KLASORU / "memcards"
OYUN_KLASORU = KAYNAKLAR_KLASORU / "oyun"
OVERLAY_KLASORU = KAYNAKLAR_KLASORU / "overlay"
PROVISION_KLASORU = KAYNAKLAR_KLASORU / "provisioning"
ILK_KURULUM_ISARETI = KAYNAKLAR_KLASORU / ".hazirlikTamam"
AYAR_DOSYASI = KAYNAKLAR_KLASORU / "launcher_config.json"


def alt_surec_ortami() -> dict:
    """PyInstaller kutuphanelerini harici Linux programlarina sizdirma."""
    ortam = os.environ.copy()
    if PLATFORM == "linux":
        onceki_ld_yolu = ortam.pop("LD_LIBRARY_PATH_ORIG", None)
        if onceki_ld_yolu:
            ortam["LD_LIBRARY_PATH"] = onceki_ld_yolu
        else:
            ortam.pop("LD_LIBRARY_PATH", None)
    return ortam


def wsl_ortami_mi() -> bool:
    """WSL/WSLg'yi gercek bir Linux masaustu oturumundan ayir."""
    if PLATFORM != "linux":
        return False
    if os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text(
            encoding="utf-8"
        ).lower()
    except OSError:
        return False


def duckstation_ortami() -> dict:
    """DuckStation icin temiz ve overlay ile uyumlu Linux ortami."""
    ortam = alt_surec_ortami()
    if PLATFORM != "linux":
        return ortam

    # Tk/mss tabanli altyazi katmani X11 pencerelerini yakalar. Gercek bir
    # Wayland masaustunde XWayland varsa DuckStation'i X11'e yonlendirerek
    # borderless fullscreen ve overlay'i ayni pencere sisteminde tutariz.
    # WSLg'nin X11 RemoteApp yolu goruntu vermedigi icin WSL bu kuraldan haric.
    wayland_var = bool(ortam.get("WAYLAND_DISPLAY"))
    wayland_oturumu = ortam.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    if (wayland_var or wayland_oturumu) and ortam.get("DISPLAY") and not wsl_ortami_mi():
        ortam["QT_QPA_PLATFORM"] = "xcb"
    return ortam

DIL_BIN_ADLARI = {
    "tr": "spiderman_tr.bin",
    "en": "spiderman_en.bin",
    "de": "spiderman_de.bin",
}

DIL_ALTYAZI_ADLARI = {
    "tr": "altyazilar.json",
    "en": "subtitles_en.json",
    "de": "subtitles_de.json",
}

UI_TEXTS = {
    "default": {"window_title": "Spider-Man 2000 - Launcher", "title": "Spider-Man 2000 - Launcher",
        "prompt": "Dil seçin / Choose your language / Sprache wählen:", "play": "Play",
        "preparing": "Preparing files, please wait...", "ready": "Ready!",
        "wait": "Preparation is ongoing, please wait."},
    "tr": {"window_title": "Spider-Man 2000 - TR", "title": "Spider-Man 2000 - Türkçe Yama",
        "prompt": "Oyun Dilini Seçin:", "play": "Oyunu Başlat",
        "preparing": "İlk kurulum yapılıyor, lütfen bekleyin...", "ready": "Sistem Hazır!",
        "wait": "Hazırlık sürüyor, lütfen birkaç saniye bekleyin."},
    "en": {"window_title": "Spider-Man 2000 - EN", "title": "Spider-Man 2000 - English Subtitles",
        "prompt": "Select Game Language:", "play": "Start Game",
        "preparing": "First time setup in progress, please wait...", "ready": "System Ready!",
        "wait": "Setup is still running, please wait."},
    "de": {"window_title": "Spider-Man 2000 - DE", "title": "Spider-Man 2000 - Deutsche Untertitel",
        "prompt": "Spielsprache wählen:", "play": "Spiel Starten",
        "preparing": "Ersteinrichtung läuft, bitte warten...", "ready": "System Bereit!",
        "wait": "Einrichtung läuft noch, bitte warten."}
}

COMBOBOX_MAP = {"Dil seçin / Choose your language / Sprache wählen": "default", "Türkçe (TR)": "tr", "English (EN)": "en", "Deutsch (DE)": "de"}
REVERSE_MAP = {v: k for k, v in COMBOBOX_MAP.items()}

def ilk_kurulum_gerekli_mi() -> bool:
    return not ILK_KURULUM_ISARETI.exists()

def ilk_kurulumu_yap(ilerleme_callback=None):
    """Artik hicbir kopyalama yapmiyor - sadece 'kaynaklar' klasorunun
    icinde, yerinde birkac hizli hazirlik islemi yapiyor (portable.txt,
    settings.ini duzeltme, memcards klasoru). Bu yuzden ilk calistirma da
    saniyeler icinde bitiyor, 6GB'lik bir kopyalama beklemek gerekmiyor."""
    MEMCARDS_KLASORU.mkdir(parents=True, exist_ok=True)

    def bildir(msg):
        print(f"[HAZIRLIK] {msg}")
        if ilerleme_callback:
            ilerleme_callback(msg)

    bildir("DuckStation hazırlanıyor...")
    (DUCKSTATION_KLASORU / "portable.txt").touch(exist_ok=True)

    if PLATFORM == "linux":
        appimage = DUCKSTATION_KLASORU / "DuckStation-x64.AppImage"
        if appimage.exists() and not os.access(appimage, os.X_OK):
            raise PermissionError(
                f"DuckStation calistirilabilir degil: {appimage}. "
                "Linux paketinin yeniden kurulmasi gerekiyor."
            )

    bildir("Ayarlar düzenleniyor...")
    settings_yolu = DUCKSTATION_KLASORU / "settings.ini"
    _settings_ini_duzelt(settings_yolu)

    ILK_KURULUM_ISARETI.write_text("ok", encoding="utf-8")
    bildir("Hazır!")

def _settings_ini_duzelt(settings_yolu: Path):
    if not settings_yolu.exists():
        return
    satirlar = settings_yolu.read_text(encoding="utf-8").splitlines()
    yeni_satirlar = []
    oyun_klasoru_str = str(OYUN_KLASORU)
    memcards_str = str(MEMCARDS_KLASORU)

    no_desktop_file_var = False
    for satir in satirlar:
        if PLATFORM == "linux" and satir.strip().startswith("NoDesktopFile"):
            yeni_satirlar.append("NoDesktopFile = true")
            no_desktop_file_var = True
            continue
        if satir.strip().startswith("RecursivePaths"):
            yeni_satirlar.append(f"RecursivePaths = {oyun_klasoru_str}")
        elif satir.strip().startswith("StartFullscreen"):
            yeni_satirlar.append("StartFullscreen = true")
        elif satir.strip().startswith("ExclusiveFullscreenControl"):
            yeni_satirlar.append("ExclusiveFullscreenControl = Disabled")
        elif satir.strip().startswith("Directory") and "memcards" in satir.lower():
            yeni_satirlar.append(f"Directory = {memcards_str}")
        elif (PLATFORM == "linux"
              and satir.strip().startswith("Backend")
              and "MediaFoundation" in satir):
            yeni_satirlar.append("Backend = FFmpeg")
        else:
            yeni_satirlar.append(satir)

    if PLATFORM == "linux" and not no_desktop_file_var:
        try:
            main_index = next(
                i for i, satir in enumerate(yeni_satirlar)
                if satir.strip() == "[Main]"
            )
            yeni_satirlar.insert(main_index + 1, "NoDesktopFile = true")
        except StopIteration:
            yeni_satirlar[0:0] = ["[Main]", "NoDesktopFile = true", ""]

    settings_yolu.write_text("\n".join(yeni_satirlar), encoding="utf-8")

def duckstation_yolu() -> Path:
    if PLATFORM == "windows":
        return DUCKSTATION_KLASORU / "duckstation-qt-x64.exe"
    return DUCKSTATION_KLASORU / "DuckStation-x64.AppImage"

def oyunu_baslat(dil: str):
    bin_adi = DIL_BIN_ADLARI.get(dil, "spiderman_en.bin")
    bin_yolu = OYUN_KLASORU / bin_adi
    if not bin_yolu.exists():
        messagebox.showerror(
            APP_NAME,
            "Oyun dosyası bulunamadı.\n"
            "Game file was not found.\n"
            "Die Spieldatei wurde nicht gefunden.\n\n"
            f"{bin_yolu}",
        )
        return

    exe = duckstation_yolu()
    if not exe.exists():
        messagebox.showerror(
            APP_NAME,
            "DuckStation bulunamadı.\n"
            "DuckStation was not found.\n"
            "DuckStation wurde nicht gefunden.\n\n"
            f"{exe}",
        )
        return

    altyazi_json_adi = DIL_ALTYAZI_ADLARI.get(dil, "altyazilar.json")
    if not (OVERLAY_KLASORU / altyazi_json_adi).exists():
        print(f"[UYARI] {altyazi_json_adi} bulunamadi, altyazilar.json ile devam ediliyor.")
        altyazi_json_adi = "altyazilar.json"

    komut = [str(exe), "-fullscreen", "-batch", str(bin_yolu)]
    oyun_prosesi = subprocess.Popen(
        komut,
        cwd=str(DUCKSTATION_KLASORU),
        env=duckstation_ortami(),
    )

    overlay_prosesi = None

    if getattr(sys, "frozen", False):
        # Derlenmis haldeyken: overlay'in KENDI derlenmis exe/binary'sini
        # cagir - kullanicinin makinesinde Python kurulu olmasina GEREK YOK.
        overlay_exe = OVERLAY_KLASORU / (
            "test_kalibreli_linux" if PLATFORM == "linux" else "test_kalibreli.exe"
        )
        if overlay_exe.exists():
            if PLATFORM == "linux" and not os.access(overlay_exe, os.X_OK):
                print(f"[UYARI] Overlay calistirilabilir degil: {overlay_exe}")
            else:
                overlay_prosesi = subprocess.Popen(
                    [str(overlay_exe), altyazi_json_adi],
                    cwd=str(OVERLAY_KLASORU),
                    env=alt_surec_ortami(),
                    start_new_session=(PLATFORM == "linux"),
                )
        else:
            print(f"[UYARI] Overlay programi bulunamadi: {overlay_exe}")
    else:
        # Gelistirme/test asamasinda: script'i mevcut Python yorumlayicisiyla calistir
        overlay_script = OVERLAY_KLASORU / (
            "test_kalibreli_linux.py" if PLATFORM == "linux" else "test_kalibreli.py"
        )
        if overlay_script.exists():
            overlay_prosesi = subprocess.Popen(
                [sys.executable, str(overlay_script), altyazi_json_adi],
                cwd=str(OVERLAY_KLASORU),
                env=alt_surec_ortami(),
                start_new_session=(PLATFORM == "linux"),
            )

    time.sleep(3)

    if PLATFORM == "windows":
        try:
            import ctypes
            from ctypes import wintypes
            EnumWindows = ctypes.windll.user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            GetWindowText = ctypes.windll.user32.GetWindowTextW
            GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
            IsWindowVisible = ctypes.windll.user32.IsWindowVisible
            SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
            ShowWindow = ctypes.windll.user32.ShowWindow

            def foreach_window(hwnd, lParam):
                if IsWindowVisible(hwnd):
                    length = GetWindowTextLength(hwnd)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    GetWindowText(hwnd, buff, length + 1)
                    title = buff.value
                    if "DuckStation" in title or "Spider-Man" in title:
                        ShowWindow(hwnd, 9)
                        SetForegroundWindow(hwnd)
                        return False
                return True

            EnumWindows(EnumWindowsProc(foreach_window), 0)
        except Exception as e:
            print(f"Windows odaklama hatası: {e}")

    elif PLATFORM == "linux":
        try:
            subprocess.run(["wmctrl", "-a", "DuckStation"], check=False, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            try:
                subprocess.run(["xdotool", "search", "--name", "DuckStation", "windowactivate"], check=False, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                pass

        # Wayland/wmctrl pencere tespiti basarisiz olsa bile overlay'i oyunun
        # omrune bagla. Boylece oyun kapaninca PyInstaller ana/cocuk surecleri
        # dahil hicbir altyazi prosesi arka planda kalmaz.
        try:
            oyun_prosesi.wait()
        finally:
            if overlay_prosesi is not None and overlay_prosesi.poll() is None:
                try:
                    os.killpg(overlay_prosesi.pid, signal.SIGTERM)
                    overlay_prosesi.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(overlay_prosesi.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

ctk.set_appearance_mode("Dark")

class DilSecimEkrani(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self._pencereyi_ortala(500, 550)
        self.resizable(False, False)

        self.kurulum_suruyor = False
        self.oyun_hazirlaniyor = False
        self.aktif_dil = self._ayarlari_yukle()

        resim_yolu = OVERLAY_KLASORU / "spiderman_bg.jpg"

        if resim_yolu.exists():
            try:
                spidey_img = ctk.CTkImage(light_image=Image.open(resim_yolu),
                                          dark_image=Image.open(resim_yolu),
                                          size=(500, 281))
                self.img_label = ctk.CTkLabel(self, image=spidey_img, text="")
                self.img_label.pack(pady=(0, 10))
            except Exception as e:
                print(f"Resim yüklenemedi: {e}")
        else:
            print(f"Resim bulunamadı, şuraya bakıldı: {resim_yolu}")

        self.orta_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.orta_frame.pack(fill="both", expand=True)

        self.title_label = ctk.CTkLabel(self.orta_frame, text="",
                                        font=ctk.CTkFont(size=22, weight="bold"), text_color="#E23636")
        self.title_label.pack(pady=(5, 10))

        self.prompt_label = ctk.CTkLabel(self.orta_frame, text="", font=ctk.CTkFont(size=14))
        self.prompt_label.pack(pady=(0, 5))

        secenekler = list(COMBOBOX_MAP.keys())
        self.dil_combobox = ctk.CTkComboBox(self.orta_frame, values=secenekler, command=self._dil_degisti, width=220,
                                            border_color="#1976D2", button_color="#1976D2",
                                            button_hover_color="#1565C0")
        self.dil_combobox.pack(pady=5)
        self.dil_combobox.set(REVERSE_MAP.get(self.aktif_dil, secenekler[0]))

        self.play_btn = ctk.CTkButton(self.orta_frame, text="", font=ctk.CTkFont(size=16, weight="bold"),
                                      height=45, fg_color="#E23636", hover_color="#B71C1C",
                                      command=self._baslat_tiklandi)
        self.play_btn.pack(pady=15)

        self.footer_canvas = tk.Canvas(self, height=60, bg="#212121", highlightthickness=0, borderwidth=0)
        self.footer_canvas.pack(side="bottom", fill="x", expand=False)

        self.durum_text_id = self.footer_canvas.create_text(0, 20, text="", fill="#EEEEEE", font=("Segoe UI", 11))
        self.yt_text_id = self.footer_canvas.create_text(0, 42, text="▶ YouTube: @kusbakisiyt", fill="#EEEEEE", font=("Segoe UI", 11, "bold"))

        self.footer_canvas.tag_bind(self.yt_text_id, "<Button-1>", lambda e: webbrowser.open_new("https://youtube.com/@kusbakisiyt"))
        self.footer_canvas.tag_bind(self.yt_text_id, "<Enter>", lambda e: self._hover_basla())
        self.footer_canvas.tag_bind(self.yt_text_id, "<Leave>", lambda e: self._hover_bitir())

        self.footer_canvas.bind("<Configure>", self._yeniden_boyutlandir)

        self._arayuzu_guncelle()

        if ilk_kurulum_gerekli_mi():
            self.kurulum_suruyor = True
            self.play_btn.configure(state="disabled")
            self._arayuzu_guncelle()
            threading.Thread(target=self._ilk_kurulum_thread, daemon=True).start()

    def _pencereyi_ortala(self, genislik, yukseklik):
        self.update_idletasks()
        ekran_w = self.winfo_screenwidth()
        ekran_h = self.winfo_screenheight()
        x = (ekran_w // 2) - (genislik // 2)
        y = (ekran_h // 2) - (yukseklik // 2)
        self.geometry(f"{genislik}x{yukseklik}+{x}+{y}")

    def _yeniden_boyutlandir(self, event):
        self.footer_canvas.delete("gradient")
        width = event.width
        height = event.height
        if width > 10:
            color1 = (35, 55, 80)
            color2 = (90, 30, 35)
            for i in range(width):
                r = int(color1[0] + (color2[0] - color1[0]) * i / width)
                g = int(color1[1] + (color2[1] - color1[1]) * i / width)
                b = int(color1[2] + (color2[2] - color1[2]) * i / width)
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                self.footer_canvas.create_line(i, 0, i, height, fill=hex_color, tags="gradient")
            self.footer_canvas.tag_lower("gradient")
            self.footer_canvas.coords(self.durum_text_id, width / 2, 20)
            self.footer_canvas.coords(self.yt_text_id, width / 2, 42)

    def _hover_basla(self):
        self.footer_canvas.itemconfig(self.yt_text_id, fill="#FFD54F")
        self.footer_canvas.config(cursor="hand2")

    def _hover_bitir(self):
        self.footer_canvas.itemconfig(self.yt_text_id, fill="#EEEEEE")
        self.footer_canvas.config(cursor="")

    def _ayarlari_yukle(self) -> str:
        if AYAR_DOSYASI.exists():
            try:
                data = json.loads(AYAR_DOSYASI.read_text(encoding="utf-8"))
                return data.get("language", "default")
            except:
                pass
        return "default"

    def _ayarlari_kaydet(self):
        if self.aktif_dil == "default":
            return
        KAYNAKLAR_KLASORU.mkdir(parents=True, exist_ok=True)
        data = {"language": self.aktif_dil}
        AYAR_DOSYASI.write_text(json.dumps(data), encoding="utf-8")

    def _dil_degisti(self, secim):
        dil_kodu = COMBOBOX_MAP.get(secim, "default")
        self.aktif_dil = dil_kodu
        self._ayarlari_kaydet()
        self._arayuzu_guncelle()
        if (
            dil_kodu != "default"
            and not self.kurulum_suruyor
            and not self.oyun_hazirlaniyor
            and not game_setup.game_is_ready(OYUN_KLASORU, dil_kodu)
        ):
            self.after(150, lambda: self._eksik_dili_hazirla(False))

    def _arayuzu_guncelle(self):
        metinler = UI_TEXTS.get(self.aktif_dil, UI_TEXTS["default"])
        self.title(metinler.get("window_title", APP_NAME))
        self.title_label.configure(text=metinler["title"])
        self.prompt_label.configure(text=metinler["prompt"])
        self.play_btn.configure(text=metinler["play"])
        if self.kurulum_suruyor:
            self.footer_canvas.itemconfig(self.durum_text_id, text=metinler["preparing"])
        else:
            if not ilk_kurulum_gerekli_mi():
                self.footer_canvas.itemconfig(self.durum_text_id, text=metinler["ready"])

    def _ilk_kurulum_thread(self):
        def guncelle(msg):
            pass
        ilk_kurulumu_yap(ilerleme_callback=guncelle)
        self.kurulum_suruyor = False
        self.after(0, self._kurulum_bitti)

    def _kurulum_bitti(self):
        self.play_btn.configure(state="normal")
        self._arayuzu_guncelle()

    def _durumu_yaz(self, metin):
        self.footer_canvas.itemconfig(self.durum_text_id, text=metin)

    def _eksik_dili_hazirla(self, hazirlaninca_oynat):
        if self.kurulum_suruyor or self.oyun_hazirlaniyor:
            return
        if self.aktif_dil == "default":
            return
        if game_setup.game_is_ready(OYUN_KLASORU, self.aktif_dil):
            if hazirlaninca_oynat:
                secilen_dil = self.aktif_dil
                self.destroy()
                oyunu_baslat(secilen_dil)
            return

        bios_klasoru = DUCKSTATION_KLASORU / "bios"
        if not game_setup.ensure_bios(self, bios_klasoru):
            return

        secim = game_setup.select_source(
            self,
            self.aktif_dil,
            progress=lambda metin: self._durumu_yaz(metin),
        )
        if secim is None:
            self._arayuzu_guncelle()
            return

        kaynak_bin, kaynak_profili = secim
        hazirlanan_dil = self.aktif_dil
        self.oyun_hazirlaniyor = True
        self.play_btn.configure(state="disabled")
        self.dil_combobox.configure(state="disabled")
        self._durumu_yaz(
            game_setup.TEXT["preparing"].format(
                language=game_setup.LANGUAGE_NAMES[hazirlanan_dil]
            )
        )

        def arka_planda_hazirla():
            sonuc, mesaj = game_setup.prepare_game(
                hazirlanan_dil,
                kaynak_bin,
                kaynak_profili,
                OYUN_KLASORU,
                PROVISION_KLASORU,
                child_environment=alt_surec_ortami(),
                progress=lambda metin: self.after(
                    0, lambda m=metin: self._durumu_yaz(m)
                ),
            )
            self.after(
                0,
                lambda: self._oyun_hazirlama_bitti(
                    sonuc, mesaj, hazirlanan_dil, hazirlaninca_oynat
                ),
            )

        threading.Thread(target=arka_planda_hazirla, daemon=True).start()

    def _oyun_hazirlama_bitti(
        self, basarili, mesaj, hazirlanan_dil, hazirlaninca_oynat
    ):
        self.oyun_hazirlaniyor = False
        self.play_btn.configure(state="normal")
        self.dil_combobox.configure(state="normal")
        self._arayuzu_guncelle()
        if not basarili:
            messagebox.showerror(APP_NAME, mesaj, parent=self)
            return

        messagebox.showinfo(APP_NAME, mesaj, parent=self)
        if game_setup.ask_add_another(self):
            messagebox.showinfo(
                APP_NAME,
                "Listeden Türkçe, English veya Deutsch seçin.\n\n"
                "Select Türkçe, English or Deutsch from the list.\n\n"
                "Wählen Sie Türkçe, English oder Deutsch aus der Liste.",
                parent=self,
            )
            return
        if hazirlaninca_oynat:
            self.destroy()
            oyunu_baslat(hazirlanan_dil)

    def _baslat_tiklandi(self):
        if self.kurulum_suruyor or self.oyun_hazirlaniyor:
            metinler = UI_TEXTS.get(self.aktif_dil, UI_TEXTS["default"])
            messagebox.showinfo(APP_NAME, metinler["wait"])
            return
        if self.aktif_dil == "default":
            messagebox.showwarning(
                APP_NAME,
                "Lütfen önce bir dil seçin!\n"
                "Please select a language first!\n"
                "Bitte wählen Sie zuerst eine Sprache!",
            )
            return
        if not game_setup.game_is_ready(OYUN_KLASORU, self.aktif_dil):
            self._eksik_dili_hazirla(True)
            return
        self.destroy()
        oyunu_baslat(self.aktif_dil)

def main():
    app = DilSecimEkrani()
    app.mainloop()

if __name__ == "__main__":
    main()
