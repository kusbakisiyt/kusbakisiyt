param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("tr", "en", "de")]
    [string]$Language,

    [Parameter(Mandatory = $true)]
    [string]$SourceBin,

    # Defaults to the folder that contains this script's parent (the project
    # root). Override with -ProjectDir if your checkout lives elsewhere.
    [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot),

    # Folder holding the already-verified target BIN you are diffing against.
    [string]$TargetDir = (Join-Path (Split-Path -Parent $PSScriptRoot) "kaynaklar\oyun")
)

$ErrorActionPreference = "Stop"
$Xdelta = Join-Path $ProjectDir "tools\windows\xdelta3-3.0.11-x86_64.exe"

$profiles = @{
    tr = @{
        SourceAlgorithm = "SHA256"
        SourceHash = "63F4AB72BB64ACB88869D17DBFD511384E16CA136A91B92ADF9F225CD9C38EB8"
        SourceBytes = 730056096
        TargetName = "spiderman_tr.bin"
        TargetHash = "9AB2B3F8F651B84BBFE1BBD81A72BB610B7F925EF86243B3BAA2DF686742157B"
        PatchName = "spiderman_tr_from_redump.xdelta"
    }
    en = @{
        SourceAlgorithm = "SHA256"
        SourceHash = "63F4AB72BB64ACB88869D17DBFD511384E16CA136A91B92ADF9F225CD9C38EB8"
        SourceBytes = 730056096
        TargetName = "spiderman_en.bin"
        TargetHash = "D335F63096B6D0E3467BBD4F7E9144EFA5820686C6D0F9567A1EC4E606EED025"
        PatchName = "spiderman_en_from_redump.xdelta"
    }
    de = @{
        SourceAlgorithm = "SHA1"
        SourceHash = "14C60DA1F82B84C5674D46C26F343F0AA7F3060C"
        SourceBytes = 718507776
        TargetName = "spiderman_de.bin"
        TargetHash = "926B64804123FD50F8AA120A208C2B0F9262C4698B5C5DEF4A9D3A4A6B79D20E"
        PatchName = "spiderman_de_from_redump.xdelta"
    }
}

$profile = $profiles[$Language]
$source = Get-Item -LiteralPath $SourceBin
if ($source.Length -ne $profile.SourceBytes) {
    throw "Kaynak BIN boyutu uyumsuz; kaynak dosya değiştirilmedi."
}
$sourceHash = (Get-FileHash -LiteralPath $source.FullName `
    -Algorithm $profile.SourceAlgorithm).Hash
if ($sourceHash -ne $profile.SourceHash) {
    throw "Kaynak BIN özeti uyumsuz; kaynak dosya değiştirilmedi."
}

$target = Join-Path $TargetDir $profile.TargetName
$targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
if ($targetHash -ne $profile.TargetHash) {
    throw "Çalışan hedef BIN doğrulanamadı."
}

$patch = Join-Path (Join-Path $ProjectDir "patches") $profile.PatchName
$testOutput = Join-Path (Join-Path $ProjectDir "tests") `
    (".verify_" + $profile.TargetName)

& $Xdelta -e -9 -S djw -B 134217728 -f -s `
    $source.FullName $target $patch
if ($LASTEXITCODE -ne 0) {
    throw "xdelta yaması oluşturulamadı."
}

try {
    & $Xdelta -d -f -s $source.FullName $patch $testOutput
    if ($LASTEXITCODE -ne 0) {
        throw "xdelta geri üretim testi başarısız."
    }
    $rebuiltHash = (Get-FileHash -LiteralPath $testOutput -Algorithm SHA256).Hash
    if ($rebuiltHash -ne $profile.TargetHash) {
        throw "Geri üretilen BIN çalışan hedefle birebir aynı değil."
    }
    Write-Output "Doğrulandı: $patch"
} finally {
    if (Test-Path -LiteralPath $testOutput) {
        Remove-Item -LiteralPath $testOutput -Force
    }
}
