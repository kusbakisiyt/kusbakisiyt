import json
import os
import re
import sys
import platform
import subprocess
import shutil
import threading
import textwrap
import time
import ctypes
import pickle
import concurrent.futures
from ctypes import wintypes
from pathlib import Path
import cv2
import numpy as np
import tkinter as tk
try:
    import mss as mss_module
except ImportError:
    mss_module = None

PLATFORM = "windows" if platform.system() == "Windows" else (
    "linux" if platform.system() == "Linux" else "other")

if PLATFORM == "windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

TARGET_TITLE_PARTS = ["DuckStation", "Spider-Man"]

def _taban_dizin() -> Path:
    # PyInstaller --onefile ile derlenince __file__, calisma sirasinda
    # acilan GECICI klasoru (%TEMP%\_MEIxxxxxx) gosterir; gercek exe'nin
    # yani "kaynaklar\overlay" klasorunu degil. launcher.pyw'deki
    # exe_klasoru() ile ayni mantik: frozen ise sys.executable'in
    # bulundugu GERCEK klasoru kullan.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE_DIR   = _taban_dizin()
SCENES_DIR = BASE_DIR / "sahneler"
SUBS_FILE  = BASE_DIR / (sys.argv[1] if len(sys.argv) > 1 else "altyazilar.json")
CACHE_FILE = BASE_DIR / "sablon_cache.pkl"
ESIK_FILE  = BASE_DIR / "sahne_esikleri.json"
SCENES_DIR.mkdir(exist_ok=True)
# ============================================================
#  AYARLAR
# ============================================================
MIN_TRIGGER_THRESHOLD = 0.30
MIN_MARGIN            = 0.05
IMMEDIATE_THRESHOLD   = 0.50
SUSTAINED_DURATION    = 0.15   # 0.35'ten 0.15'e indirildi - gecikmeyi azaltir
BYPASS_SCENES    = {"switch", "oda", "yolbulma"}
BYPASS_THRESHOLD = 0.34
BYPASS_MARGIN    = 0.05
SWITCH_WINDOW_SEC         = 30.0
SCORPION_WATCH_SEC        = 120.0
SCORPION_STRICT_THRESHOLD = 0.42
SCENE_COOLDOWN       = 20.0
POLL_INTERVAL        = 0.033
DARK_FRAME_LIMIT     = 3
MIN_EDGE_PIXELS_LIVE = 450
STARTUP_SKIP_FRAMES  = 60
FRAME_TRIM_RATIO         = 0.025
AUTO_CROP_THRESHOLD      = 10
AUTO_CROP_PAD            = 8
AUTO_CROP_MIN_AREA_RATIO = 0.15
FRAME_DIFF_SIZE      = (160, 90)
FRAME_DIFF_THRESHOLD = 3.0
WORK_SIZES = {
    "4x3":  (320, 240),
    "16x9": (320, 180),
}

# HIZ ICIN: canli eslestirmede her sahne icin en fazla kac sablon kare
# kullanilsin. Ardisik kareler zaten birbirine cok benzedigi icin
# hepsini tutmak gereksiz yavaslik yaratiyor (yuzlerce sahne x yuzlerce
# kare x 4 varyant). Orijinal fotograflar hic silinmiyor, sadece canli
# eslestirmede kullanilan alt kume esit araliklarla secilip sinirlaniyor.
MAX_FRAMES_PER_SCENE = 30
# ============================================================
#  ELLE AYARLANMIS OZEL ESIKLER
#  Bunlar sahne_esikleri.json'dan OKUNDUKTAN SONRA uygulanir ve
#  kalibrasyon script'i (esik_kalibrasyon.py) tekrar calistirilsa
#  bile kalibrasyon bu degerleri EZMEZ. Yeni bir sahnede benzer
#  "yanlis yerde tetiklenme" sorunu cikarsa, buraya yeni bir satir
#  eklemen yeterli.
# ============================================================
MANUEL_ESIKLER = {
    "lizard": {"threshold": 0.48, "margin": 0.15},
    "neredesin": {"threshold": 0.35, "margin": 0.07},
    "yolbulma": {"threshold": 0.40, "margin": 0.10},
    "ryho": {"threshold": 0.52, "margin": 0.15},
    "helikopter": {"threshold": 0.42, "margin": 0.10}
}
# ============================================================
if PLATFORM == "windows":
    user32 = ctypes.windll.user32
    user32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetClassNameW.restype  = ctypes.c_int

# ============================================================
#  LINUX PENCERE / GEOMETRI ALTYAPISI (wmctrl + xdotool tabanli)
#  KayitStudio.pyw'deki ayni yaklasim - ek bagimlilik yok, sadece
#  paket yoneticisinden kurulan standart araclar kullaniliyor.
# ============================================================
_YASAKLI_BASLIKLAR = [
    "firefox", "mozilla", "chrome", "edge", "brave", "opera",
    "visual studio", "python", "py.exe", "cmd", "powershell",
    "terminal", "discord", "klasor", "folder", "claude", "notepad"
]

def _linux_arac_var_mi(ad):
    from shutil import which
    return which(ad) is not None

def _linux_pencere_bul(parts):
    """wmctrl -lG ile basliga gore pencere arar, (id, title, bbox) doner.
    bbox = (left, top, right, bottom) - wmctrl zaten mutlak ekran
    koordinatlarinda genislik/yukseklik veriyor."""
    if not _linux_arac_var_mi("wmctrl"):
        return (None, "", None)
    try:
        r = subprocess.run(["wmctrl", "-lG"], capture_output=True, text=True, timeout=5)
    except Exception:
        return (None, "", None)
    for satir in r.stdout.splitlines():
        parcalar = satir.split(None, 7)
        if len(parcalar) < 8:
            continue
        win_id, _masaustu, x, y, w, h, _host, title = parcalar
        title_l = title.strip().lower()
        if not any(p.lower() in title_l for p in parts):
            continue
        if any(y_ in title_l for y_ in _YASAKLI_BASLIKLAR):
            continue
        try:
            x, y, w, h = int(x), int(y), int(w), int(h)
        except ValueError:
            continue
        if w <= 0 or h <= 0:
            continue
        return (win_id, title.strip(), (x, y, x + w, y + h))
    return (None, "", None)

def _linux_ekran_boyutu():
    if _linux_arac_var_mi("xdotool"):
        try:
            r = subprocess.run(["xdotool", "getdisplaygeometry"], capture_output=True, text=True, timeout=5)
            w, h = map(int, r.stdout.split())
            return w, h
        except Exception:
            pass
    try:
        r = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=5)
        m = re.search(r"current\s+(\d+)\s*x\s*(\d+)", r.stdout)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 1920, 1080

stop_event     = threading.Event()
window_seen    = threading.Event()
linux_osd_lock = threading.Lock()
linux_osd_process = None


def _linux_osd_kapat():
    global linux_osd_process
    with linux_osd_lock:
        proses = linux_osd_process
        linux_osd_process = None
        if proses is None or proses.poll() is not None:
            return
        try:
            proses.terminate()
            proses.wait(timeout=0.4)
        except subprocess.TimeoutExpired:
            proses.kill()
        except ProcessLookupError:
            pass


def _linux_metni_sar(text, ekran_genisligi):
    if not text:
        return ""
    # XOSD'nin sabit 34px yazitipi otomatik satir kaydirmaz. Cozunurluge
    # gore guvenli bir karakter siniri kullan; kelimeleri ortadan bolme.
    satir_genisligi = max(36, min(84, int(ekran_genisligi / 22)))
    satirlar = []
    for paragraf in str(text).splitlines() or [str(text)]:
        satirlar.extend(textwrap.wrap(
            paragraf,
            width=satir_genisligi,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""])
    return "\n".join(satirlar)


def _linux_osd_goster(text):
    """X11/XWayland uzerinde arka plansiz, konturlu altyazi goster."""
    global linux_osd_process
    with linux_osd_lock:
        onceki = linux_osd_process
        linux_osd_process = None
        if onceki is not None and onceki.poll() is None:
            try:
                onceki.terminate()
                onceki.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                onceki.kill()
            except ProcessLookupError:
                pass

        if not text:
            return

        komut = [
            "osd_cat",
            "--pos=bottom",
            "--align=center",
            "--offset=45",
            "--colour=#FFCC00",
            "--outline=3",
            "--outlinecolour=#010101",
            "--lines=4",
            "--delay=3600",
            "--font=-misc-fixed-bold-r-normal--34-*-*-*-c-*-iso8859-9",
        ]
        try:
            proses = subprocess.Popen(
                komut,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
            )
            proses.stdin.write(str(text).rstrip() + "\n")
            proses.stdin.close()
            linux_osd_process = proses
        except (OSError, BrokenPipeError) as exc:
            print(f"[UYARI] Linux seffaf altyazi katmani baslatilamadi: {exc}", flush=True)
subtitle_token = 0
scene_state    = {}
scene_lock     = threading.Lock()
SCENE_THRESHOLDS = {}   # esik_kalibrasyon.py ciktisiyla monitor() basinda doldurulur
class RECT(ctypes.Structure):
    _fields_ = [
        ("left",   ctypes.c_long),
        ("top",    ctypes.c_long),
        ("right",  ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]
# ============================================================
#  WINDOWS ONCELİK / TIMER OPTİMİZASYONU
# ============================================================
def set_process_priority():
    """Prosesi yuksek onceliğe alir (Windows: HIGH_PRIORITY_CLASS, Linux: nice)."""
    if PLATFORM == "windows":
        try:
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(handle, 0x00000080)  # HIGH
            print("[OK] Proses onceligi: HIGH")
        except Exception as e:
            print(f"[UYARI] Proses onceligi ayarlanamadi: {e}")
    else:
        try:
            os.nice(-10)
            print("[OK] Proses onceligi (nice -10) ayarlandi")
        except PermissionError:
            print("[BILGI] Proses onceligi icin yeterli izin yok (sudo gerekmiyor, dusuk oncelikle devam ediliyor).")
        except Exception as e:
            print(f"[UYARI] Proses onceligi ayarlanamadi: {e}")

def set_thread_priority_highest():
    """Çağıran thread'i en yuksek onceliğe alir (Windows: THREAD_PRIORITY_HIGHEST, Linux: SCHED_RR)."""
    if PLATFORM == "windows":
        try:
            handle = ctypes.windll.kernel32.GetCurrentThread()
            ctypes.windll.kernel32.SetThreadPriority(handle, 2)  # HIGHEST
            print("[OK] Monitor thread onceligi: HIGHEST")
        except Exception as e:
            print(f"[UYARI] Thread onceligi ayarlanamadi: {e}")
    else:
        try:
            param = os.sched_param(1)
            os.sched_setscheduler(0, os.SCHED_RR, param)
            print("[OK] Monitor thread onceligi: SCHED_RR")
        except PermissionError:
            print("[BILGI] Gercek-zamanli zamanlama icin yeterli izin yok, normal oncelikle devam ediliyor.")
        except Exception as e:
            print(f"[UYARI] Thread onceligi ayarlanamadi: {e}")

def set_timer_resolution():
    """Windows timer granularitesini 15ms'den 1ms'ye indirir. Linux'ta zaten
    kernel timer cozunurlugu bu seviyede oldugu icin islem yapilmiyor."""
    if PLATFORM != "windows":
        return
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
        print("[OK] Windows timer cozunurlugu: 1ms")
    except Exception as e:
        print(f"[UYARI] Timer cozunurlugu ayarlanamadi: {e}")

def reset_timer_resolution():
    if PLATFORM != "windows":
        return
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass

# ============================================================
def norm_key(s):
    return str(s).strip().lower()
def detect_bucket_from_hw(w, h):
    if w <= 0 or h <= 0:
        return "16x9"
    ratio = w / float(h)
    return "4x3" if abs(ratio - (4/3)) <= abs(ratio - (16/9)) else "16x9"
def bucket_from_path(path: Path):
    parts = [p.lower() for p in path.parts]
    for p in parts:
        if p in {"4x3", "4:3"} or "4x3" in p or "4:3" in p:
            return "4x3"
        if p in {"16x9", "16:9"} or "16x9" in p or "16:9" in p:
            return "16x9"
    return None
def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    return buf.value if user32.GetClassNameW(hwnd, buf, 256) else ""
_LINUX_BBOX_CACHE = {}

def find_window_by_titles(parts):
    """Windows'ta (hwnd, title) doner. Linux'ta (win_id, title) doner ve
    bbox'u ayni taramada bulup _LINUX_BBOX_CACHE'e yazar (capture() bu
    cache'i okur, boylece frame basina ikinci bir wmctrl cagrisi gerekmez)."""
    if PLATFORM == "windows":
        found = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def proc(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            ln = user32.GetWindowTextLengthW(hwnd)
            if ln <= 0:
                return True
            buf = ctypes.create_unicode_buffer(ln + 1)
            user32.GetWindowTextW(hwnd, buf, ln + 1)
            title = buf.value.lower()
            if not any(p.lower() in title for p in parts):
                return True
            class_name = get_class_name(hwnd).lower()
            if class_name in {"cabinetwclass", "explorewclass", "workerw", "progman"}:
                return True
            if any(y in title for y in _YASAKLI_BASLIKLAR):
                return True
            found.append((hwnd, buf.value))
            return False
        user32.EnumWindows(WNDENUMPROC(proc), 0)
        return found[0] if found else (0, "")
    else:
        win_id, title, bbox = _linux_pencere_bul(parts)
        if win_id is not None and bbox is not None:
            _LINUX_BBOX_CACHE[win_id] = bbox
        return (win_id, title)

def target_window_alive():
    win_ref, _ = find_window_by_titles(TARGET_TITLE_PARTS)
    if PLATFORM == "windows":
        return win_ref != 0, win_ref
    return win_ref is not None, win_ref

def get_bbox(win_ref):
    if PLATFORM == "windows":
        r = RECT()
        if not user32.GetClientRect(win_ref, ctypes.byref(r)):
            return None
        lt = wintypes.POINT(r.left, r.top)
        rb = wintypes.POINT(r.right, r.bottom)
        user32.ClientToScreen(win_ref, ctypes.byref(lt))
        user32.ClientToScreen(win_ref, ctypes.byref(rb))
        return (lt.x, lt.y, rb.x, rb.y)
    else:
        return _LINUX_BBOX_CACHE.get(win_ref)

def capture(win_ref, sct=None):
    bbox = get_bbox(win_ref)
    if not bbox:
        return None
    l, t, r, b = bbox
    w, h = r - l, b - t
    if w <= 0 or h <= 0:
        return None
    try:
        if sct:
            shot = sct.grab({"left": l, "top": t, "width": w, "height": h})
            return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
        if PLATFORM == "windows":
            from PIL import ImageGrab
            return cv2.cvtColor(np.array(ImageGrab.grab(bbox=bbox)), cv2.COLOR_RGB2BGR)
        return None
    except Exception:
        return None
def trim_frame(img):
    if img is None:
        return None
    h, w = img.shape[:2]
    dx = int(w * FRAME_TRIM_RATIO)
    dy = int(h * FRAME_TRIM_RATIO)
    if dx <= 0 and dy <= 0:
        return img
    return img[dy:max(dy+1, h-dy), dx:max(dx+1, w-dx)]
def auto_crop_content(img):
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(gray, AUTO_CROP_THRESHOLD, 255, cv2.THRESH_BINARY)
    coords = cv2.findNonZero(mask)
    if coords is None:
        return img
    x, y, w, h = cv2.boundingRect(coords)
    if w * h < img.shape[0] * img.shape[1] * AUTO_CROP_MIN_AREA_RATIO:
        return img
    x1 = max(0, x - AUTO_CROP_PAD)
    y1 = max(0, y - AUTO_CROP_PAD)
    x2 = min(img.shape[1], x + w + AUTO_CROP_PAD)
    y2 = min(img.shape[0], y + h + AUTO_CROP_PAD)
    if x2 <= x1 or y2 <= y1:
        return img
    return img[y1:y2, x1:x2]
def center_crop_to_ratio(img, target_ratio):
    h, w = img.shape[:2]
    if h <= 0 or w <= 0:
        return None
    src_ratio = w / float(h)
    if abs(src_ratio - target_ratio) < 0.001:
        return img
    if src_ratio > target_ratio:
        new_w = max(1, min(int(h * target_ratio), w))
        x = max(0, (w - new_w) // 2)
        return img[:, x:x + new_w]
    else:
        new_h = max(1, min(int(w / target_ratio), h))
        y = max(0, (h - new_h) // 2)
        return img[y:y + new_h, :]
def preprocess_variant(img, bucket, mode):
    if img is None:
        return None
    h, w = img.shape[:2]
    if w > 640:
        scale = 640.0 / w
        img = cv2.resize(img, (640, int(h * scale)), interpolation=cv2.INTER_AREA)
    img = trim_frame(img)
    if img is None:
        return None
    img = auto_crop_content(img)
    if img is None:
        return None
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    target_w, target_h = WORK_SIZES[bucket]
    if mode == "crop":
        img = center_crop_to_ratio(img, target_w / float(target_h))
        if img is None:
            return None
    img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(img, (5, 5), 0)
    blurred = cv2.equalizeHist(blurred)
    edges   = cv2.Canny(blurred, 20, 70)
    edges   = cv2.dilate(edges, None, iterations=2)
    return edges
def parse_scene_name_and_index(stem):
    stem = norm_key(stem)
    if "_" in stem:
        base, last = stem.rsplit("_", 1)
        if last.isdigit():
            return base, int(last)
    return stem, 0
def _process_single_template(f):
    img = cv2.imread(str(f), cv2.IMREAD_COLOR)
    if img is None:
        return None
    bucket = bucket_from_path(f)
    if bucket is None:
        h, w = img.shape[:2]
        bucket = detect_bucket_from_hw(w, h)
    scene_name, idx = parse_scene_name_and_index(f.stem)
    crop_edges = preprocess_variant(img, bucket, "crop")
    warp_edges = preprocess_variant(img, bucket, "warp")
    if crop_edges is not None and np.count_nonzero(crop_edges) < 1200:
        return None
    return (bucket, scene_name, idx, {"crop": crop_edges, "warp": warp_edges})
def downsample_bank(bank, max_count):
    """Her sahne icin, canli eslestirmede kullanilacak sablon sayisini
    esit araliklarla sinirlar. Orijinal cache/dosyalar etkilenmez, sadece
    dondurulen bank kucultulur - hesaplama yuku bu sayede dusurulur."""
    for bucket in bank:
        for scene_name, frame_list in bank[bucket].items():
            if len(frame_list) > max_count:
                idxs = np.linspace(0, len(frame_list) - 1, max_count).astype(int)
                bank[bucket][scene_name] = [frame_list[i] for i in idxs]
    return bank
def load_templates():
    dosyalar = [
        f for f in SCENES_DIR.rglob("*")
        if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    guncel_dosya_sayisi = len(dosyalar)
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                cache_data = pickle.load(f)
            if cache_data.get("dosya_sayisi") == guncel_dosya_sayisi:
                print(f"[OK] Onbellekten {guncel_dosya_sayisi} sablon yuklendi!")
                bank = cache_data["bank"]
                bank = downsample_bank(bank, MAX_FRAMES_PER_SCENE)
                for bucket in bank:
                    for sn in bank[bucket]:
                        print(f"  {bucket} -> {sn} ({len(bank[bucket][sn])} frame, canlida kullanilan) [CACHED]")
                return bank
            else:
                print("[BILGI] Sahneler degisti, onbellek guncelleniyor...")
        except Exception:
            print("[UYARI] Onbellek bozuk, yeniden olusturuluyor...")
    bank = {"4x3": {}, "16x9": {}}
    print(f"[BILGI] {guncel_dosya_sayisi} sablon isleniyor, lutfen bekleyin...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        sonuclar = list(executor.map(_process_single_template, dosyalar))
    count = 0
    for sonuc in sonuclar:
        if sonuc is not None:
            bucket, scene_name, idx, data = sonuc
            bank[bucket].setdefault(scene_name, []).append((idx, data))
            count += 1
    for bucket in bank:
        for sn in bank[bucket]:
            bank[bucket][sn].sort(key=lambda x: x[0])
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({"dosya_sayisi": guncel_dosya_sayisi, "bank": bank}, f)
        print("[OK] Sablonlar onbellege kaydedildi!")
    except Exception as e:
        print(f"[UYARI] Onbellege kaydedilemedi: {e}")
    print(f"[OK] Toplam sablon: {count}")
    bank = downsample_bank(bank, MAX_FRAMES_PER_SCENE)
    return bank

def load_scene_thresholds():
    """esik_kalibrasyon.py tarafindan uretilen sahne_esikleri.json'u yukler.
    Dosya yoksa bos dict doner, sistem eski (global) esiklerle calismaya devam eder."""
    if not ESIK_FILE.exists():
        print("[BILGI] sahne_esikleri.json bulunamadi, global esikler kullanilacak.")
        return {}
    try:
        with ESIK_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data = {norm_key(k): v for k, v in data.items()}
        print(f"[OK] {len(data)} sahne icin kalibre edilmis esik yuklendi.")
        return data
    except Exception as e:
        print(f"[UYARI] sahne_esikleri.json okunamadi: {e}")
        return {}

def get_threshold(scene, is_bypass):
    default = BYPASS_THRESHOLD if is_bypass else MIN_TRIGGER_THRESHOLD
    cal = SCENE_THRESHOLDS.get(scene)
    if cal and "threshold" in cal:
        return cal["threshold"]
    return default

def get_margin(scene, is_bypass):
    default = BYPASS_MARGIN if is_bypass else MIN_MARGIN
    cal = SCENE_THRESHOLDS.get(scene)
    if cal and "margin" in cal:
        return cal["margin"]
    return default

def load_subs():
    if not SUBS_FILE.exists():
        with SUBS_FILE.open("w", encoding="utf-8") as f:
            json.dump(
                {"sahne": {"tetik_offset": 0.0, "satirlar": [[0.0, "Ornek"]]}},
                f, ensure_ascii=False, indent=2
            )
    with SUBS_FILE.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return {norm_key(k): v for k, v in data.items()}

def match_score(a, b):
    if a is None or b is None:
        return -1.0
    if a.shape != b.shape:
        a = cv2.resize(a, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_AREA)
    result = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
    _, val, _, _ = cv2.minMaxLoc(result)
    return float(val)

# HIZ ICIN: her karede yuzlerce sahne x sablon x varyant kombinasyonu
# TEK THREAD'de sirayla hesaplaniyordu - bu, kare basina onemli bir
# CPU yuku yaratiyordu (genel gecikmenin buyuk kismi buradan geliyordu).
# cv2.matchTemplate GIL'i serbest biraktigi icin, bu hesaplamayi thread
# havuzuna dagitmak gercek bir hizlanma sagliyor (cok cekirdekli CPU'larda).
# Dogruluk hic degismiyor - hala HER sablonla karsilastiriliyor, sadece
# paralel yapiliyor.
_MATCH_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

def _best_score_for_scene(frame_list, mode, live_edges):
    best_local = -1.0
    for _, ref in frame_list:
        val = match_score(live_edges, ref.get(mode))
        if val > best_local:
            best_local = val
    return best_local

def choose_best_live_variant(raw_frame, templates_bank, ignored_scenes=None, force_scan=False):
    if ignored_scenes is None:
        ignored_scenes = set()
    h, w = raw_frame.shape[:2]
    gray = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
    if not force_scan:
        if np.mean(gray) < DARK_FRAME_LIMIT:
            return {"score": 0.0, "second_score": 0.0, "scene": "Yok", "raw_w": w, "raw_h": h}
    test_edges = preprocess_variant(raw_frame, "16x9", "warp")
    if not force_scan:
        if test_edges is not None and np.count_nonzero(test_edges) < MIN_EDGE_PIXELS_LIVE:
            return {"score": 0.0, "second_score": 0.0, "scene": "Yok", "raw_w": w, "raw_h": h}
    variants = []
    if templates_bank.get("4x3"):
        variants.append(("4x3", "crop", preprocess_variant(raw_frame, "4x3", "crop")))
        variants.append(("4x3", "warp", preprocess_variant(raw_frame, "4x3", "warp")))
    if templates_bank.get("16x9"):
        variants.append(("16x9", "crop", preprocess_variant(raw_frame, "16x9", "crop")))
        variants.append(("16x9", "warp", preprocess_variant(raw_frame, "16x9", "warp")))
    scene_max = {}
    for bucket, mode, live_edges in variants:
        if live_edges is None:
            continue
        bank = templates_bank.get(bucket, {})
        items = [(sn, fl) for sn, fl in bank.items() if sn not in ignored_scenes]
        if not items:
            continue
        futures = {
            _MATCH_POOL.submit(_best_score_for_scene, fl, mode, live_edges): sn
            for sn, fl in items
        }
        for fut in concurrent.futures.as_completed(futures):
            sn = futures[fut]
            best_local = fut.result()
            if best_local > scene_max.get(sn, -1.0):
                scene_max[sn] = best_local
    if not scene_max:
        return {"score": 0.0, "second_score": 0.0, "scene": "Yok", "raw_w": w, "raw_h": h}
    sorted_scenes = sorted(scene_max.items(), key=lambda x: x[1], reverse=True)
    best_scene, best_score = sorted_scenes[0]
    second_score = sorted_scenes[1][1] if len(sorted_scenes) > 1 else 0.0
    return {
        "score":        best_score,
        "second_score": second_score,
        "scene":        best_scene,
        "raw_w":        w,
        "raw_h":        h,
        "all_scores":   scene_max,
    }

def set_text(root, canvas_widget, text):
    if stop_event.is_set():
        return
    if PLATFORM == "linux":
        if shutil.which("osd_cat"):
            _linux_osd_goster(_linux_metni_sar(text, root.winfo_screenwidth()))
        elif text:
            print("[HATA] osd_cat bulunamadi; siyah bar olusmamasi icin altyazi penceresi acilmadi.")
        return
    def _do():
        if stop_event.is_set() or not root.winfo_exists():
            return
        try:
            canvas_widget.delete("all")
            if text:
                w = canvas_widget.winfo_width()
                h = canvas_widget.winfo_height()
                if w < 10:
                    w = root.winfo_screenwidth()
                    h = 120
                x, y = w / 2, h / 2
                font_config = ("Arial", 28, "bold")
                wrap_width  = w - 200
                offsets = [(-2,-2),(0,-2),(2,-2),(-2,0),(2,0),(-2,2),(0,2),(2,2)]
                for ox, oy in offsets:
                    canvas_widget.create_text(
                        x + ox, y + oy, text=text, font=font_config,
                        fill="#010101", justify="center", width=wrap_width
                    )
                canvas_widget.create_text(
                    x, y, text=text, font=font_config,
                    fill="#FFCC00", justify="center", width=wrap_width
                )
        except tk.TclError:
            return
        try:
            root.lift()
            root.attributes("-topmost", True)
        except Exception:
            pass
    root.after(0, _do)

def force_topmost(root):
    if stop_event.is_set() or not root.winfo_exists():
        return
    try:
        root.attributes("-topmost", True)
        root.lift()
        if PLATFORM == "windows":
            hwnd = root.winfo_id()
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
        # Linux'ta tkinter'in -topmost attribute'u pencere yoneticisine
        # ayni istegi ileten standart yol; ek bir X11 cagrisi gerekmiyor.
    except Exception:
        pass
    root.after(300, lambda: force_topmost(root))

def shutdown(root, message=""):
    if message:
        print(message, flush=True)
    stop_event.set()
    if PLATFORM == "linux":
        _linux_osd_kapat()
    reset_timer_resolution()
    try:
        root.quit()
    except Exception:
        pass
    try:
        if root and root.winfo_exists():
            root.after(0, root.destroy)
    except Exception:
        pass
    os._exit(0)

def on_close(root):
    shutdown(root, "\n[OK] Program kapatiliyor.")

def ui_watchdog(root):
    if stop_event.is_set():
        return
    alive, _ = target_window_alive()
    if alive:
        window_seen.set()
    else:
        if window_seen.is_set():
            shutdown(root, "\n[OK] Oyun veya Emulator kapandi, Python kapaniyor.")
            return
    try:
        root.after(400, lambda: ui_watchdog(root))
    except Exception:
        shutdown(root, "\n[OK] Tk kapanamadi, cikiliyor.")

def play_timeline(root, canvas, satirlar, tetik_offset, token, scene_name):
    global subtitle_token
    start = time.perf_counter() - tetik_offset
    try:
        for item in satirlar:
            if stop_event.is_set() or token != subtitle_token:
                return
            target = start + float(item[0])
            while time.perf_counter() < target:
                if stop_event.is_set() or token != subtitle_token:
                    return
                time.sleep(0.004)
            set_text(root, canvas, str(item[1]))
        time.sleep(1.5)
        if token == subtitle_token and not stop_event.is_set():
            set_text(root, canvas, "")
    finally:
        with scene_lock:
            if scene_name in scene_state:
                scene_state[scene_name]["playing"] = False

def trigger_scene(root, canvas, name, db):
    global subtitle_token
    if name not in db:
        print(f"\n[UYARI] '{name}' JSON'da yok!")
        return
    now = time.perf_counter()
    with scene_lock:
        st = scene_state.setdefault(name, {"playing": False, "last_played": 0.0})
        if st["playing"] or (now - st["last_played"]) < SCENE_COOLDOWN:
            return
        st["playing"]     = True
        st["last_played"] = now
        subtitle_token   += 1
        token = subtitle_token
    sahne = db[name]
    threading.Thread(
        target=play_timeline,
        args=(root, canvas, sahne.get("satirlar", []),
              float(sahne.get("tetik_offset", 0.0)), token, name),
        daemon=True
    ).start()

def monitor(root, canvas):
    global SCENE_THRESHOLDS
    set_thread_priority_highest()
    print("=" * 60)
    print("   SPIDER-MAN PS1 TURKCE YAMA - YOUTUBE: @kusbakisiyt  ")
    print("=" * 60)
    templates_bank = load_templates()
    db = load_subs()
    SCENE_THRESHOLDS = load_scene_thresholds()
    # ELLE AYARLANMIS OZEL DEGERLER - kalibrasyon bunlari EZMEZ.
    SCENE_THRESHOLDS.update(MANUEL_ESIKLER)
    print(f"[OK] Esik: {MIN_TRIGGER_THRESHOLD} | Margin: {MIN_MARGIN} | Sureklilik: {SUSTAINED_DURATION}s | Turbo: {IMMEDIATE_THRESHOLD}")
    print(f"[OK] Bypass sahneler: {BYPASS_SCENES}")
    if MANUEL_ESIKLER:
        print(f"[OK] Manuel esikler uygulandi: {list(MANUEL_ESIKLER.keys())}")
    sct = mss_module.MSS() if mss_module else None
    startup         = 0
    startup_cleared = False
    sustained_start = {}
    prev_gray_small = None
    switch_armed_until   = 0.0
    ignored_scenes       = {"switch"}
    scorpion_watch_until = 0.0
    # PENCERE KONTROLU ONBELLEGI: Linux'ta target_window_alive() her
    # cagrildiginda YENI BIR PROSES (wmctrl) baslatiyor - bu, her poll
    # dongusunde (saniyede ~30 kez) yapilirsa, proses baslatma maliyeti
    # tum sistemi gercek zamandan geride birakiyor (genel gecikmenin
    # asil kaynagi buydu). Pencere pozisyonu oyun sirasinda neredeyse
    # hic degismedigi icin, bu kontrolu saniyede bir kez yapip aradaki
    # karelerde son bilinen sonucu (ve zaten var olan _LINUX_BBOX_CACHE
    # icindeki bbox'i) tekrar kullaniyoruz.
    WINDOW_CHECK_INTERVAL = 1.0
    _win_check_next = 0.0
    _win_alive_cached = False
    _win_ref_cached = None
    try:
        while not stop_event.is_set():
            _now_wc = time.perf_counter()
            if _now_wc >= _win_check_next:
                _win_alive_cached, _win_ref_cached = target_window_alive()
                _win_check_next = _now_wc + WINDOW_CHECK_INTERVAL
            alive, ds_hwnd = _win_alive_cached, _win_ref_cached
            if alive:
                window_seen.set()
            else:
                if window_seen.is_set():
                    shutdown(root, "\n[OK] Oyun veya Emulator kapandi, Python kapaniyor.")
                    return
                time.sleep(1)
                continue
            raw = capture(ds_hwnd, sct)
            if raw is None:
                time.sleep(POLL_INTERVAL)
                continue
            if startup < STARTUP_SKIP_FRAMES:
                startup += 1
                time.sleep(POLL_INTERVAL)
                continue
            if not startup_cleared:
                with scene_lock:
                    scene_state.clear()
                startup_cleared = True
            gray_small = cv2.resize(
                cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY),
                FRAME_DIFF_SIZE
            )
            now_pre = time.perf_counter()
            if switch_armed_until > 0.0 and now_pre > switch_armed_until:
                ignored_scenes.add("switch")
                switch_armed_until = 0.0
            in_scorpion_watch = (scorpion_watch_until > 0.0 and now_pre < scorpion_watch_until)
            if scorpion_watch_until > 0.0 and now_pre >= scorpion_watch_until:
                scorpion_watch_until = 0.0
            if prev_gray_small is not None and not in_scorpion_watch:
                diff = np.mean(cv2.absdiff(gray_small, prev_gray_small))
                if diff < FRAME_DIFF_THRESHOLD:
                    time.sleep(POLL_INTERVAL)
                    continue
            prev_gray_small = gray_small
            best = choose_best_live_variant(
                raw, templates_bank,
                ignored_scenes=ignored_scenes,
                force_scan=in_scorpion_watch
            )
            now    = time.perf_counter()
            scene  = best["scene"]
            score  = best["score"]
            second = best["second_score"]
            margin = score - second

            all_scores = best.get("all_scores", {})
            candidates = []
            for scene_name, own_score in all_scores.items():
                if scene_name in ignored_scenes:
                    continue
                if scene_name == "scorpion" and not in_scorpion_watch and own_score < SCORPION_STRICT_THRESHOLD:
                    continue
                rakip = max(
                    (v for k, v in all_scores.items() if k != scene_name),
                    default=0.0
                )
                fark = own_score - rakip
                is_bypass_c   = scene_name in BYPASS_SCENES
                req_threshold = get_threshold(scene_name, is_bypass_c)
                req_margin    = get_margin(scene_name, is_bypass_c)
                if own_score >= req_threshold and fark >= req_margin:
                    candidates.append((scene_name, own_score, fark))
            candidates.sort(key=lambda x: x[1], reverse=True)

            passing_names = {c[0] for c in candidates}
            for sn in list(sustained_start.keys()):
                if sn not in passing_names:
                    sustained_start.pop(sn, None)

            if candidates:
                fire_scene, fire_score, fire_margin = candidates[0]
                is_bypass = fire_scene in BYPASS_SCENES

                if fire_scene == "oda":
                    switch_armed_until = now + SWITCH_WINDOW_SEC
                    ignored_scenes.discard("switch")
                    print(f"\n[SISTEM] ODA -> SWITCH {SWITCH_WINDOW_SEC}s aktif")
                if fire_scene == "switch":
                    if now <= switch_armed_until:
                        print("\n[SISTEM] SWITCH tetikleniyor.")
                        switch_armed_until = 0.0
                        ignored_scenes.add("switch")
                    else:
                        sustained_start.pop(fire_scene, None)
                        time.sleep(POLL_INTERVAL)
                        continue
                if fire_scene == "imha" and scorpion_watch_until <= now:
                    scorpion_watch_until = now + SCORPION_WATCH_SEC
                    print("\n[SISTEM] IMHA -> Scorpion bekleniyor.")
                if fire_scene == "scorpion":
                    scorpion_watch_until = 0.0

                is_turbo = fire_score >= IMMEDIATE_THRESHOLD and fire_scene not in ("ryho", "yolbulma")
                if is_turbo or is_bypass:
                    with scene_lock:
                        st = scene_state.setdefault(fire_scene, {"playing": False, "last_played": 0.0})
                    if not st["playing"] and (now - st["last_played"]) >= SCENE_COOLDOWN:
                        tag = "TURBO" if is_turbo else "BYPASS"
                        print(f"\n[{tag}] Skor: {fire_score:.3f} | Fark: {fire_margin:.3f} | Sahne: {fire_scene}")
                        trigger_scene(root, canvas, fire_scene, db)
                    sustained_start.pop(fire_scene, None)
                else:
                    if fire_scene not in sustained_start:
                        sustained_start[fire_scene] = now
                    elapsed = now - sustained_start[fire_scene]
                    if elapsed >= SUSTAINED_DURATION:
                        with scene_lock:
                            st = scene_state.setdefault(fire_scene, {"playing": False, "last_played": 0.0})
                        if not st["playing"] and (now - st["last_played"]) >= SCENE_COOLDOWN:
                            print(f"\n[NORMAL] Skor: {fire_score:.3f} | Fark: {fire_margin:.3f} | Sahne: {fire_scene}")
                            trigger_scene(root, canvas, fire_scene, db)
                        sustained_start.pop(fire_scene, None)
            sus = f"{now - sustained_start.get(scene, now):.2f}s" if scene in sustained_start else "-"
            print(
                f"[LIVE] {score:.3f} (2nd:{second:.3f} m:{margin:.3f}) "
                f"sus={sus:<6} | {scene}    ",
                end="\r", flush=True
            )
            time.sleep(POLL_INTERVAL)
    finally:
        if sct:
            sct.close()

def _linux_on_kontrol():
    """Eksik araclari ve Wayland durumunu baslangicta bir kere bildirir."""
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        print(
            "[UYARI] Wayland oturumu tespit edildi. Ekran yakalama (mss) ve "
            "pencere konumu tespiti (wmctrl) Wayland'da guvenilir calismayabilir.\n"
            "         Mumkunse oturum acma ekraninda 'Ubuntu on Xorg' / 'X11' secenegini kullan."
        )
    eksik = [a for a in ("wmctrl",) if not _linux_arac_var_mi(a)]
    if eksik:
        print(f"[HATA] Su araclar eksik: {', '.join(eksik)}. Kurulum: sudo apt install {' '.join(eksik)}")

def main():
    if PLATFORM == "linux":
        _linux_on_kontrol()
    set_process_priority()
    set_timer_resolution()
    cv2.setUseOptimized(True)
    root = tk.Tk()

    # --- EKRAN SUNUCUSU TESPİTİ (Wayland / X11) ---
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    is_wayland = "wayland" in session_type

    if PLATFORM == "windows":
        # === WINDOWS (Orijinal, Bozulmadı) ===
        root.overrideredirect(True)
        root.wm_attributes("-topmost", True)
        root.attributes("-transparentcolor", "black")
    else:
        # Linux'ta Tk katmani ekrana hic cizilmez. XOSD eksik olsa bile siyah
        # altyazi bari geri donemez; paket xosd-bin'i zorunlu bagimlilik olarak kurar.
        root.withdraw()
        if not shutil.which("osd_cat"):
            print("[HATA] osd_cat bulunamadi; Linux altyazilari devre disi.")

    root.configure(bg="black")
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    if PLATFORM != "linux":
        root.geometry(f"{sw}x120+0+{sh - 150}")

    # --- LINUX İÇİN SAYDAMLIK UYGULAMASI ---
    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    if PLATFORM != "linux":
        canvas.pack(fill="both", expand=True)
    t = threading.Thread(target=monitor, args=(root, canvas), daemon=True)
    t.start()
    force_topmost(root)
    ui_watchdog(root)
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))
    try:
        root.mainloop()
    except KeyboardInterrupt:
        shutdown(root, "\n[OK] Kullanici tarafindan kapatildi.")
if __name__ == "__main__":
    main()
