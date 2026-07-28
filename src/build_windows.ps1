param(
    [switch]$SkipInstaller,
    [switch]$ReuseBinaries,
    # Defaults to the folder that contains this script's parent (the project
    # root). Override with -ProjectDir "D:\path\to\project" if you keep the
    # checkout somewhere else.
    [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot),
    # Folder that holds the staged runtime assets (overlay data, DuckStation
    # build, etc.) before packaging. Override with -SourceAssets if yours
    # lives elsewhere.
    [string]$SourceAssets = (Join-Path (Split-Path -Parent $PSScriptRoot) "kaynaklar"),
    # Branding is intentionally kept outside the MIT-licensed source.
    [string]$IconPath = (Join-Path (Split-Path -Parent $PSScriptRoot) "assets\spiderman_ico.ico")
)

$ErrorActionPreference = "Stop"

$CodeDir = Join-Path $ProjectDir "src"
$BuildDir = Join-Path $ProjectDir "build\windows"
$AssetsDir = Join-Path $BuildDir "assets"
$LauncherDist = Join-Path $BuildDir "launcher-dist"
$LauncherWork = Join-Path $BuildDir "launcher-work"
$OverlayDist = Join-Path $BuildDir "overlay-dist"
$OverlayWork = Join-Path $BuildDir "overlay-work"
$ProvisionDir = Join-Path $AssetsDir "provisioning"
$InnoCompiler = Join-Path $ProjectDir "tools\InnoSetup6\ISCC.exe"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $BuildDir "pyinstaller-config"
$env:TEMP = Join-Path $BuildDir "tmp"
$env:TMP = $env:TEMP

if (-not (Test-Path -LiteralPath (Join-Path $CodeDir "launcher.pyw"))) {
    throw "launcher.pyw bulunamadı."
}
if (-not (Test-Path -LiteralPath (Join-Path $CodeDir "test_kalibreli.py"))) {
    throw "test_kalibreli.py bulunamadı."
}
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    throw "Inno Setup derleyicisi bulunamadı."
}
if (-not (Test-Path -LiteralPath $IconPath)) {
    throw "Marka simgesi bulunamadı. Kendi kullanım izniniz olan ICO dosyasını assets\spiderman_ico.ico konumuna ekleyin veya -IconPath kullanın."
}

# Recreate the project-local asset stage so excluded development files and
# superseded patches cannot survive from an earlier build.
if (Test-Path -LiteralPath $AssetsDir) {
    $resolvedAssets = [IO.Path]::GetFullPath($AssetsDir)
    $allowedRoot = [IO.Path]::GetFullPath(
        (Join-Path $ProjectDir "build\windows")
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedAssets.StartsWith(
        $allowedRoot, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Guvenli olmayan sahne temizleme yolu: $resolvedAssets"
    }
    Remove-Item -LiteralPath $resolvedAssets -Recurse -Force
}

foreach ($directory in @(
    $BuildDir, $AssetsDir, $LauncherDist, $LauncherWork,
    $OverlayDist, $OverlayWork, $env:PYINSTALLER_CONFIG_DIR, $env:TEMP
)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

# Assets are staged without any game BIN or BIOS.  Robocopy success codes are
# 0-7; 8 and above indicate an actual failure.
robocopy $SourceAssets $AssetsDir /MIR /R:1 /W:1 /XF *.bin *.BIN `
    /XD __pycache__ build dist (Join-Path $SourceAssets "duckstation\bios") `
    /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "Kaynak dosyalar hazırlanamadı (robocopy: $LASTEXITCODE)."
}

foreach ($unwanted in @(
    (Join-Path $AssetsDir ".hazirlikTamam"),
    (Join-Path $AssetsDir ".kurulumtamam"),
    (Join-Path $AssetsDir "launcher_config.json")
)) {
    if (Test-Path -LiteralPath $unwanted) {
        Remove-Item -LiteralPath $unwanted -Force
    }
}

New-Item -ItemType Directory -Path (Join-Path $AssetsDir "oyun") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $AssetsDir "duckstation\bios") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ProvisionDir "patches") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ProvisionDir "tools\windows") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ProvisionDir "licenses") -Force | Out-Null

Copy-Item -Path (Join-Path $ProjectDir "patches\*") `
    -Destination (Join-Path $ProvisionDir "patches") -Force
Copy-Item -LiteralPath (Join-Path $ProjectDir "tools\windows\xdelta3-3.0.11-x86_64.exe") `
    -Destination (Join-Path $ProvisionDir "tools\windows\xdelta3.exe") -Force
Copy-Item -Path (Join-Path $ProjectDir "licenses\*") `
    -Destination (Join-Path $ProvisionDir "licenses") -Force

Copy-Item -LiteralPath (Join-Path $CodeDir "test_kalibreli.py") `
    -Destination (Join-Path $AssetsDir "overlay\test_kalibreli.py") -Force
Copy-Item -LiteralPath (Join-Path $CodeDir "test_kalibreli_linux.py") `
    -Destination (Join-Path $AssetsDir "overlay\test_kalibreli_linux.py") -Force

if (-not $ReuseBinaries) {
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name test_kalibreli `
    --collect-all cv2 --collect-all numpy --collect-all mss `
    --distpath $OverlayDist --workpath $OverlayWork `
    --specpath (Join-Path $BuildDir "overlay-spec") `
    (Join-Path $CodeDir "test_kalibreli.py")
if ($LASTEXITCODE -ne 0) {
    throw "Windows altyazı katmanı derlenemedi."
}
Copy-Item -LiteralPath (Join-Path $OverlayDist "test_kalibreli.exe") `
    -Destination (Join-Path $AssetsDir "overlay\test_kalibreli.exe") -Force

python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name SpiderManTR --icon $IconPath `
    --collect-all customtkinter --collect-all PIL `
    --distpath $LauncherDist --workpath $LauncherWork `
    --specpath (Join-Path $BuildDir "launcher-spec") `
    (Join-Path $CodeDir "launcher.pyw")
if ($LASTEXITCODE -ne 0) {
    throw "Windows launcher derlenemedi."
}
} else {
    if (-not (Test-Path -LiteralPath (Join-Path $OverlayDist "test_kalibreli.exe"))) {
        throw "Yeniden kullanilacak Windows altyazi binary'si bulunamadi."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $LauncherDist "SpiderManTR\SpiderManTR.exe"))) {
        throw "Yeniden kullanilacak Windows launcher binary'si bulunamadi."
    }
    Copy-Item -LiteralPath (Join-Path $OverlayDist "test_kalibreli.exe") `
        -Destination (Join-Path $AssetsDir "overlay\test_kalibreli.exe") -Force
}

$forbidden = Get-ChildItem -LiteralPath $AssetsDir -Recurse -File |
    Where-Object {
        $_.Extension -ieq ".bin" -or
        $_.FullName -match "\\duckstation\\bios\\"
    }
if ($forbidden) {
    $forbidden | ForEach-Object { Write-Error $_.FullName }
    throw "Paket sahnesinde oyun BIN veya BIOS bulundu."
}

if (-not $SkipInstaller) {
    foreach ($requiredPatch in @(
        "spiderman_tr_from_redump.xdelta",
        "spiderman_en_from_redump.xdelta",
        "spiderman_de_from_redump.xdelta"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir "patches\$requiredPatch"))) {
            throw "Zorunlu yama eksik: $requiredPatch"
        }
    }
    & $InnoCompiler (Join-Path $CodeDir "SpiderManTR_xdelta.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Windows kurulum paketi oluşturulamadı."
    }
    Write-Output "Windows paketi hazır: $(Join-Path $ProjectDir 'outputs')"
} else {
    Write-Output "Windows derleme sahnesi hazır; kurulum oluşturma atlandı."
}
