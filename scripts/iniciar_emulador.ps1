param([switch]$SemJanela)
$ErrorActionPreference = 'Stop'
$ecoRoot = Split-Path -Parent $PSScriptRoot
$ecoSdk = Join-Path $env:LOCALAPPDATA 'Android/Sdk'
$ecoAdb = Join-Path $ecoSdk 'platform-tools/adb.exe'
$ecoEmulator = Join-Path $ecoSdk 'emulator/emulator.exe'
$ecoImage = Join-Path $ecoSdk 'system-images/android-34/google_apis/x86_64'
foreach ($ecoPath in @($ecoAdb, $ecoEmulator, $ecoImage)) {
    if (-not (Test-Path -LiteralPath $ecoPath)) { throw "Nao encontrado: $ecoPath. Instale Android 14 Google APIs x86_64 pelo SDK Manager." }
}
$ecoRuntime = Join-Path $ecoRoot '.runtime'
$ecoRegistry = Join-Path $ecoRuntime 'avd-registry'
$ecoAvd = Join-Path $ecoRuntime 'avd-stable'
New-Item -ItemType Directory -Path $ecoRegistry,$ecoAvd -Force | Out-Null
$ecoConfig = Join-Path $ecoAvd 'config.ini'
if (-not (Test-Path -LiteralPath $ecoConfig)) {
    @"
AvdId=EcoPulse_APS_Estavel
avd.ini.encoding=UTF-8
avd.ini.displayname=EcoPulse APS Estavel
PlayStore.enabled=no
abi.type=x86_64
image.sysdir.1=$ecoImage/
tag.id=google_apis
tag.display=Google APIs
hw.cpu.arch=x86_64
hw.cpu.ncore=2
hw.ramSize=2560
hw.gpu.enabled=yes
hw.gpu.mode=host
hw.lcd.width=720
hw.lcd.height=1600
hw.lcd.density=280
hw.keyboard=no
hw.mainKeys=no
hw.gps=yes
hw.camera.back=none
hw.camera.front=none
hw.audioInput=no
hw.audioOutput=no
disk.dataPartition.size=2G
fastboot.forceColdBoot=yes
showDeviceFrame=no
runtime.network.latency=none
runtime.network.speed=full
"@ | Set-Content -LiteralPath $ecoConfig -Encoding utf8
}
@"
avd.ini.encoding=UTF-8
path=$ecoAvd
target=android-34
"@ | Set-Content -LiteralPath (Join-Path $ecoRegistry 'EcoPulse_APS_Estavel.ini') -Encoding utf8
$ecoSerial = $null
foreach ($ecoLine in (& $ecoAdb devices)) {
    if ($ecoLine -match '^(emulator-\d+)\s+device$') {
        $ecoCandidate = $Matches[1]
        $ecoName = (& $ecoAdb -s $ecoCandidate shell getprop ro.boot.qemu.avd_name).Trim()
        if ($ecoName -eq 'EcoPulse_APS_Estavel') { $ecoSerial = $ecoCandidate; break }
    }
}
if (-not $ecoSerial) {
    $ecoSerial = 'emulator-5560'
    if ((& $ecoAdb devices) -match '^emulator-5560\s') { throw 'A porta 5560 ja esta em uso por outro emulador.' }
    $ecoPreviousAvdHome = $env:ANDROID_AVD_HOME
    try {
        $env:ANDROID_AVD_HOME = $ecoRegistry
        $ecoArgs = @('-avd','EcoPulse_APS_Estavel','-port','5560','-no-audio','-no-boot-anim','-no-snapshot','-gpu','host','-feature','-Vulkan','-memory','2560','-cores','2')
        if ($SemJanela) { $ecoArgs += '-no-window' }
        Start-Process -FilePath $ecoEmulator -ArgumentList $ecoArgs -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ecoRuntime 'stable-emulator.log') -RedirectStandardError (Join-Path $ecoRuntime 'stable-emulator-error.log') | Out-Null
    } finally { $env:ANDROID_AVD_HOME = $ecoPreviousAvdHome }
}
Write-Host 'Aguardando Android 14 iniciar. Feche compilacoes ociosas antes de usar o emulador em um PC com 8 GB.'
$ecoDeadline = (Get-Date).AddMinutes(5)
do {
    $ecoBoot = (& $ecoAdb -s $ecoSerial shell getprop sys.boot_completed 2>$null)
    if ($ecoBoot -eq '1') { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $ecoDeadline)
if ($ecoBoot -ne '1') { throw 'Android nao terminou de iniciar em cinco minutos. Consulte .runtime/stable-emulator-error.log.' }
& $ecoAdb -s $ecoSerial shell svc power stayon true | Out-Null
& $ecoAdb -s $ecoSerial shell settings put system screen_off_timeout 2147483647 | Out-Null
& $ecoAdb -s $ecoSerial shell input keyevent KEYCODE_WAKEUP | Out-Null
$ecoApk = Join-Path $ecoRoot 'entregas/EcoPulse-Firebase.apk'
if (-not (Test-Path -LiteralPath $ecoApk)) { $ecoApk = Join-Path $ecoRoot 'entregas/EcoPulse-demo.apk' }
if (-not (Test-Path -LiteralPath $ecoApk)) { throw 'Coloque um dos APKs entregues em entregas antes de iniciar.' }
& $ecoAdb -s $ecoSerial install -r $ecoApk
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o APK no emulador.' }
& $ecoAdb -s $ecoSerial shell am start -n br.edu.ecopulse.ecopulse/.MainActivity
if ($LASTEXITCODE -ne 0) { throw 'Falha ao solicitar abertura do EcoPulse.' }
Write-Host "EcoPulse iniciado em $ecoSerial. Para o backend do PC, configure http://10.0.2.2:8011 no app."
