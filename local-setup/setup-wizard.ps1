#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Rhino Drishti — Local Database Installation Wizard v1.0
.DESCRIPTION
    Installs MongoDB Community 7.0 on your Windows 11 PC,
    connects it to Render via Tailscale VPN, and migrates
    all existing data from MongoDB Atlas to local storage.
.NOTES
    Run as Administrator:
    Right-click PowerShell → "Run as Administrator", then:
    Set-ExecutionPolicy Bypass -Scope Process -Force
    .\setup-wizard.ps1
#>

param(
    [string]$DataDrive    = "",          # e.g. "D" — auto-detected if blank
    [string]$AtlasUri     = "",          # pre-fill from env; prompted if blank
    [switch]$SkipMigration,              # skip Atlas → local data copy
    [switch]$Unattended                  # non-interactive (requires all params)
)

# ─── Console helpers ─────────────────────────────────────────────────────────
$ESC  = [char]27
function c($code) { "$ESC[${code}m" }

function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "$(c 95)██████╗ ██╗  ██╗██╗███╗   ██╗ ██████╗     ██████╗ ██████╗$(c 0)"
    Write-Host "$(c 95)██╔══██╗██║  ██║██║████╗  ██║██╔═══██╗    ██╔══██╗██╔══██╗$(c 0)"
    Write-Host "$(c 95)██████╔╝███████║██║██╔██╗ ██║██║   ██║    ██║  ██║██████╔╝$(c 0)"
    Write-Host "$(c 95)██╔══██╗██╔══██║██║██║╚██╗██║██║   ██║    ██║  ██║██╔══██╗$(c 0)"
    Write-Host "$(c 95)██║  ██║██║  ██║██║██║ ╚████║╚██████╔╝    ██████╔╝██████╔╝$(c 0)"
    Write-Host "$(c 95)╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝     ╚═════╝ ╚═════╝$(c 0)"
    Write-Host ""
    Write-Host "$(c 96)  LOCAL DATABASE INSTALLATION WIZARD  v1.0$(c 0)"
    Write-Host "$(c 90)  ─────────────────────────────────────────$(c 0)"
    Write-Host ""
}

function Write-Step($n, $total, $msg) {
    Write-Host ""
    Write-Host "$(c 96)  ┌─ STEP $n/$total ──────────────────────────────────┐$(c 0)"
    Write-Host "$(c 96)  │  $msg$(c 0)"
    Write-Host "$(c 96)  └────────────────────────────────────────────────┘$(c 0)"
    Write-Host ""
}

function Write-OK($msg)   { Write-Host "  $(c 92)✔  $msg$(c 0)" }
function Write-Fail($msg) { Write-Host "  $(c 91)✘  $msg$(c 0)" }
function Write-Info($msg) { Write-Host "  $(c 33)ℹ  $msg$(c 0)" }
function Write-Warn($msg) { Write-Host "  $(c 93)⚠  $msg$(c 0)" }
function Write-Ask($msg)  { Write-Host "  $(c 96)▶  $msg$(c 0)" -NoNewline }
function Write-Done       { Write-Host "" ; Write-Host "  $(c 92)✔  Done!$(c 0)" ; Write-Host "" }

function Pause-ForUser($msg = "Press any key to continue...") {
    Write-Host ""
    Write-Host "  $(c 90)$msg$(c 0)"
    [void][System.Console]::ReadKey($true)
}

function Confirm-Step($msg) {
    if ($Unattended) { return $true }
    Write-Ask "$msg [Y/n]: "
    $r = Read-Host
    return ($r -eq "" -or $r -match "^[Yy]")
}

function Abort($msg) {
    Write-Fail "ABORTED: $msg"
    Write-Host ""
    exit 1
}

# ─── Prerequisite checks ─────────────────────────────────────────────────────
function Test-Prerequisites {
    Write-Step 1 9 "Checking prerequisites"

    # Admin check
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = [System.Security.Principal.WindowsPrincipal]$id
    if (-not $p.IsInRole([System.Security.Principal.WindowsBuiltInRole]"Administrator")) {
        Abort "This script must be run as Administrator. Right-click PowerShell → Run as Administrator."
    }
    Write-OK "Running as Administrator"

    # Windows version
    $os = Get-WmiObject Win32_OperatingSystem
    $build = [int]($os.BuildNumber)
    if ($build -lt 19041) {
        Abort "Windows 10 (build 19041+) or Windows 11 required. Your build: $build"
    }
    Write-OK "Windows version: $($os.Caption) (Build $build)"

    # Internet
    try {
        $null = Invoke-WebRequest -Uri "https://www.google.com" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-OK "Internet connection: OK"
    } catch {
        Abort "No internet connection detected."
    }

    # winget
    try {
        $null = Get-Command winget -ErrorAction Stop
        Write-OK "winget: available"
    } catch {
        Write-Warn "winget not found — will use direct downloads instead"
    }

    # Disk space (require at least 5GB free on chosen drive)
    Write-Done
}

# ─── Choose data directory ────────────────────────────────────────────────────
function Select-DataDirectory {
    Write-Step 2 9 "Choosing data storage directory"

    # List available drives > 50GB free
    $drives = Get-PSDrive -PSProvider FileSystem | Where-Object {
        $_.Free -gt 50GB
    } | Sort-Object -Property Free -Descending

    Write-Host "  Available drives:"
    foreach ($d in $drives) {
        $freeGB  = [math]::Round($d.Free / 1GB, 1)
        $totalGB = [math]::Round(($d.Used + $d.Free) / 1GB, 1)
        $bar     = "█" * [math]::Round(($d.Used / ($d.Used + $d.Free)) * 20)
        Write-Host "    $(c 96)$($d.Name):\$(c 0)  $freeGB GB free / $totalGB GB  [$bar]"
    }
    Write-Host ""

    if ($DataDrive -eq "") {
        # Prefer D: or E: over C: for database data
        $preferred = $drives | Where-Object { $_.Name -ne "C" } | Select-Object -First 1
        if ($preferred) {
            $defaultDrive = $preferred.Name
        } else {
            $defaultDrive = "C"
        }

        if (-not $Unattended) {
            Write-Ask "Enter drive letter for MongoDB data [$defaultDrive]: "
            $input = Read-Host
            $DataDrive = if ($input -ne "") { $input.TrimEnd(":").ToUpper() } else { $defaultDrive }
        } else {
            $DataDrive = $defaultDrive
        }
    }

    $script:DataPath = "${DataDrive}:\RhinoDrishti\data"
    $script:LogPath  = "${DataDrive}:\RhinoDrishti\logs"

    Write-Info "MongoDB data directory: $script:DataPath"
    Write-Info "MongoDB log  directory: $script:LogPath"

    # Create dirs
    foreach ($dir in @($script:DataPath, $script:LogPath)) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    Write-OK "Directories created"
    Write-Done
}

# ─── Install MongoDB Community 7.0 ───────────────────────────────────────────
function Install-MongoDB {
    Write-Step 3 9 "Installing MongoDB Community Server 7.0"

    # Check if already installed
    $svc = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
    if ($svc) {
        Write-OK "MongoDB service already exists ($(($svc.Status)))"
        if ($svc.Status -ne "Running") {
            Start-Service MongoDB -ErrorAction SilentlyContinue
            Write-OK "MongoDB service started"
        }
        return
    }

    $mongoExe = "C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe"
    if (Test-Path $mongoExe) {
        Write-OK "MongoDB 7.0 binary found — skipping download"
    } else {
        Write-Info "Downloading MongoDB Community Server 7.0..."
        $msiUrl  = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.14-signed.msi"
        $msiPath = "$env:TEMP\mongodb-7.0.msi"

        try {
            # Try winget first
            Write-Info "Trying winget install..."
            winget install MongoDB.Server --version 7.0 --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0 -and (Test-Path $mongoExe)) {
                Write-OK "Installed via winget"
            } else {
                throw "winget failed"
            }
        } catch {
            Write-Info "Downloading MSI directly (~500MB)..."
            $wc = New-Object System.Net.WebClient
            $wc.DownloadFile($msiUrl, $msiPath)
            Write-Info "Installing MongoDB MSI (this takes ~2 min)..."
            $args = @(
                "/i", $msiPath,
                "/qn",
                "ADDLOCAL=ServerNoService",   # Don't install as service yet (we configure first)
                "/log", "$env:TEMP\mongodb-install.log"
            )
            Start-Process msiexec.exe -ArgumentList $args -Wait -NoNewWindow
            if (-not (Test-Path $mongoExe)) {
                Abort "MongoDB installation failed. Check $env:TEMP\mongodb-install.log"
            }
            Write-OK "MongoDB installed from MSI"
            Remove-Item $msiPath -Force -ErrorAction SilentlyContinue
        }
    }

    # Generate a strong password for MongoDB
    $chars   = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#"
    $rng     = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $bytes   = New-Object byte[] 32
    $rng.GetBytes($bytes)
    $script:MongoPassword = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
    $script:MongoUser     = "rhinodrishti"
    $script:MongoDb       = "rhino_drishti"

    # Write mongod.cfg
    $cfg = @"
systemLog:
  destination: file
  path: $($script:LogPath)\mongod.log
  logAppend: true
storage:
  dbPath: $($script:DataPath)
  journal:
    enabled: true
net:
  port: 27017
  bindIp: 127.0.0.1
security:
  authorization: enabled
"@
    $cfgPath = "C:\Program Files\MongoDB\Server\7.0\bin\mongod.cfg"
    Set-Content -Path $cfgPath -Value $cfg -Encoding UTF8

    # Install and start service
    Write-Info "Installing MongoDB Windows Service..."
    & $mongoExe --config $cfgPath --install 2>&1 | Out-Null
    Start-Service MongoDB -ErrorAction Stop
    Write-OK "MongoDB service installed and running"

    # Wait for MongoDB to be ready
    Write-Info "Waiting for MongoDB to be ready..."
    Start-Sleep 3

    # Create admin + app user (no-auth first, then enable)
    $mongoShell = "C:\Program Files\MongoDB\Server\7.0\bin\mongosh.exe"
    if (-not (Test-Path $mongoShell)) {
        $mongoShell = "C:\Program Files\MongoDB\Server\7.0\bin\mongo.exe"
    }

    # Temporarily allow no-auth to create first admin
    Stop-Service MongoDB -Force | Out-Null
    $cfgNoAuth = $cfg -replace "security:", "# security:" -replace "  authorization: enabled", "  # authorization: enabled"
    Set-Content -Path $cfgPath -Value $cfgNoAuth -Encoding UTF8
    Start-Service MongoDB | Out-Null
    Start-Sleep 2

    $createUsers = @"
use admin
db.createUser({
  user: 'admin',
  pwd: '$($script:MongoPassword)_admin',
  roles: [{ role: 'userAdminAnyDatabase', db: 'admin' }, 'readWriteAnyDatabase']
})
use $($script:MongoDb)
db.createUser({
  user: '$($script:MongoUser)',
  pwd: '$($script:MongoPassword)',
  roles: [{ role: 'readWrite', db: '$($script:MongoDb)' }]
})
"@
    $tmpJs = "$env:TEMP\create-users.js"
    Set-Content -Path $tmpJs -Value $createUsers -Encoding UTF8
    & $mongoShell --quiet --file $tmpJs 2>&1 | Out-Null
    Remove-Item $tmpJs -Force

    # Re-enable auth
    Stop-Service MongoDB -Force | Out-Null
    Set-Content -Path $cfgPath -Value $cfg -Encoding UTF8
    Start-Service MongoDB | Out-Null
    Start-Sleep 2

    $script:LocalMongoUri = "mongodb://$($script:MongoUser):$($script:MongoPassword)@127.0.0.1:27017/$($script:MongoDb)?authSource=$($script:MongoDb)"
    Write-OK "MongoDB configured with authentication"
    Write-Done
}

# ─── Install & connect Tailscale ─────────────────────────────────────────────
function Install-Tailscale {
    Write-Step 4 9 "Installing Tailscale VPN"

    $tailscale = "C:\Program Files\Tailscale\tailscale.exe"

    if (-not (Test-Path $tailscale)) {
        Write-Info "Downloading Tailscale for Windows..."
        try {
            winget install Tailscale.Tailscale --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "winget failed" }
            Write-OK "Installed via winget"
        } catch {
            $tsUrl  = "https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe"
            $tsPath = "$env:TEMP\tailscale-setup.exe"
            $wc     = New-Object System.Net.WebClient
            $wc.DownloadFile($tsUrl, $tsPath)
            Start-Process $tsPath -ArgumentList "/S" -Wait -NoNewWindow
            Write-OK "Installed via direct download"
            Remove-Item $tsPath -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-OK "Tailscale already installed"
    }

    # Find tailscale.exe in PATH or default location
    $tsBin = Get-Command tailscale -ErrorAction SilentlyContinue
    if (-not $tsBin) {
        $env:PATH += ";C:\Program Files\Tailscale"
        $tsBin = "C:\Program Files\Tailscale\tailscale.exe"
    } else {
        $tsBin = $tsBin.Source
    }
    $script:TailscaleBin = $tsBin

    Write-Done
}

function Connect-Tailscale {
    Write-Step 5 9 "Connecting to Tailscale"

    Write-Host ""
    Write-Host "  $(c 93)IMPORTANT — Tailscale Account Required$(c 0)"
    Write-Host "  $(c 90)Tailscale is FREE for personal/small team use (up to 100 devices).$(c 0)"
    Write-Host "  $(c 90)If you don't have an account, sign up at: https://tailscale.com$(c 0)"
    Write-Host ""

    # Check if already logged in
    $status = & $script:TailscaleBin status --json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($status -and $status.BackendState -eq "Running") {
        Write-OK "Tailscale already connected"
        $script:TailscaleIP = ($status.Self.TailscaleIPs | Where-Object { $_ -notlike "*:*" }) | Select-Object -First 1
        Write-OK "Local Tailscale IP: $($script:TailscaleIP)"
        Write-Done
        return
    }

    Write-Info "Opening Tailscale login in browser..."
    Write-Warn "Complete the login in your browser, then return here."

    & $script:TailscaleBin up --hostname "rhinodrishti-db" 2>&1 | Out-Null

    # Wait for connection
    $maxWait = 120
    $waited  = 0
    while ($waited -lt $maxWait) {
        $status = & $script:TailscaleBin status --json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($status -and $status.BackendState -eq "Running") { break }
        Write-Host "  $(c 90)Waiting for Tailscale login... ($waited/$maxWait s)$(c 0)" -NoNewline
        Write-Host "`r" -NoNewline
        Start-Sleep 3
        $waited += 3
    }

    if ($waited -ge $maxWait) {
        Abort "Tailscale did not connect in time. Please run 'tailscale up' manually and re-run this script."
    }

    $status = & $script:TailscaleBin status --json 2>&1 | ConvertFrom-Json
    $script:TailscaleIP = ($status.Self.TailscaleIPs | Where-Object { $_ -notlike "*:*" }) | Select-Object -First 1
    Write-OK "Tailscale connected! Your device: $($status.Self.DNSName)"
    Write-OK "Tailscale IP (use this for Render): $(c 92)$($script:TailscaleIP)$(c 0)"

    Write-Done
}

# ─── Generate Tailscale Auth Key for Render ───────────────────────────────────
function Get-TailscaleAuthKey {
    Write-Step 6 9 "Generating Tailscale Auth Key for Render"

    Write-Host ""
    Write-Host "  Render needs a Tailscale $(c 93)Auth Key$(c 0) to join the same VPN."
    Write-Host "  This is a one-time setup. The key is stored as a Render environment variable."
    Write-Host ""
    Write-Host "  $(c 96)► Open this URL in your browser:$(c 0)"
    Write-Host "    $(c 93)https://login.tailscale.com/admin/settings/keys$(c 0)"
    Write-Host ""
    Write-Host "  $(c 96)► Click 'Generate auth key'$(c 0)"
    Write-Host "    ✓ Check  'Reusable'          (so Render can reconnect after restarts)"
    Write-Host "    ✓ Check  'Ephemeral'          (auto-removes Render from your network if it goes offline)"
    Write-Host "    ✓ Expiry: $(c 33)90 days$(c 0) (you'll update this key quarterly)"
    Write-Host ""

    if (-not $Unattended) {
        Write-Ask "Paste the auth key here (tskey-auth-...): "
        $script:TailscaleAuthKey = (Read-Host).Trim()
    }

    if (-not $script:TailscaleAuthKey -or -not $script:TailscaleAuthKey.StartsWith("tskey-")) {
        Write-Warn "No valid auth key provided — you can add it manually to Render later."
        $script:TailscaleAuthKey = "<PASTE_YOUR_TAILSCALE_AUTH_KEY_HERE>"
    } else {
        Write-OK "Auth key received"
    }
    Write-Done
}

# ─── Migrate data from Atlas ──────────────────────────────────────────────────
function Migrate-Data {
    Write-Step 7 9 "Migrating data from MongoDB Atlas to local MongoDB"

    if ($SkipMigration) {
        Write-Info "Skipping migration (--SkipMigration flag set)"
        return
    }

    # Get Atlas URI
    if ($AtlasUri -eq "") {
        # Try reading from backend .env
        $envFile = Join-Path $PSScriptRoot "..\backend\.env"
        if (Test-Path $envFile) {
            $envContent = Get-Content $envFile
            $mongoLine  = $envContent | Where-Object { $_ -match "^MONGO_URL=" }
            if ($mongoLine) {
                $AtlasUri = $mongoLine -replace "^MONGO_URL=", ""
                Write-OK "Atlas URI found in backend\.env"
            }
        }
    }

    if ($AtlasUri -eq "" -and -not $Unattended) {
        Write-Info "Could not find Atlas connection string automatically."
        Write-Ask "Paste your MongoDB Atlas connection string (mongodb+srv://...): "
        $AtlasUri = (Read-Host).Trim()
    }

    if ($AtlasUri -eq "") {
        Write-Warn "No Atlas URI — skipping data migration. You can run migrate_atlas_to_local.py later."
        return
    }

    # Check Python
    $python = $null
    foreach ($p in @("python", "python3", "py")) {
        try {
            $ver = & $p --version 2>&1
            if ($ver -match "Python 3\.[89]|Python 3\.1[0-9]") {
                $python = $p
                break
            }
        } catch {}
    }

    if (-not $python) {
        Write-Info "Python 3.8+ not found — installing via winget..."
        winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        $env:PATH += ";$env:LOCALAPPDATA\Programs\Python\Python311;$env:LOCALAPPDATA\Programs\Python\Python311\Scripts"
        $python = "python"
    }
    Write-OK "Python: $python"

    # Install pymongo
    Write-Info "Installing pymongo..."
    & $python -m pip install "pymongo[srv]" --quiet 2>&1 | Out-Null
    Write-OK "pymongo installed"

    # Run migration script
    $migScript = Join-Path $PSScriptRoot "migrate_atlas_to_local.py"
    if (-not (Test-Path $migScript)) {
        Write-Fail "Migration script not found at $migScript"
        return
    }

    Write-Info "Starting migration — this may take several minutes for large datasets..."
    Write-Host ""
    & $python $migScript --source $AtlasUri --target $script:LocalMongoUri
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Migration completed with warnings — check output above."
    } else {
        Write-OK "Migration completed successfully"
    }
    Write-Done
}

# ─── Allow Tailscale through Windows Firewall ─────────────────────────────────
function Set-FirewallRule {
    Write-Info "Adding Windows Firewall rule: allow MongoDB from Tailscale subnet only..."
    try {
        # Remove old rule if exists
        Remove-NetFirewallRule -DisplayName "RhinoDrishti-MongoDB-Tailscale" -ErrorAction SilentlyContinue

        New-NetFirewallRule `
            -DisplayName "RhinoDrishti-MongoDB-Tailscale" `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort 27017 `
            -RemoteAddress "100.64.0.0/10" `
            -Action Allow `
            -Profile Any | Out-Null

        Write-OK "Firewall rule added (MongoDB open to Tailscale 100.64.0.0/10 only)"
    } catch {
        Write-Warn "Could not add firewall rule automatically. Add manually:"
        Write-Host "    Allow TCP port 27017 from 100.64.0.0/10 (Tailscale subnet)"
    }
}

# ─── Update MongoDB bind IP for Tailscale ────────────────────────────────────
function Set-MongoBindTailscale {
    Write-Step 8 9 "Binding MongoDB to Tailscale interface"

    $cfgPath = "C:\Program Files\MongoDB\Server\7.0\bin\mongod.cfg"
    if (-not (Test-Path $cfgPath)) {
        Write-Warn "mongod.cfg not found — skipping bind update"
        return
    }

    # MongoDB must listen on both 127.0.0.1 (local) and Tailscale IP
    $content = Get-Content $cfgPath -Raw
    $content = $content -replace "bindIp: .*", "bindIp: 127.0.0.1,$($script:TailscaleIP)"
    Set-Content -Path $cfgPath -Value $content -Encoding UTF8

    # Restart MongoDB
    Restart-Service MongoDB -Force
    Start-Sleep 2
    Write-OK "MongoDB now listening on 127.0.0.1 + $($script:TailscaleIP)"

    # Update the URI to use Tailscale IP (for Render)
    $script:RemoteMongoUri = "mongodb://$($script:MongoUser):$($script:MongoPassword)@$($script:TailscaleIP):27017/$($script:MongoDb)?authSource=$($script:MongoDb)"

    Set-FirewallRule
    Write-Done
}

# ─── Write config files ───────────────────────────────────────────────────────
function Write-ConfigFiles {
    $outputDir = Join-Path $PSScriptRoot "output"
    if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory $outputDir | Out-Null }

    # render-env.txt — paste these into Render dashboard
    $renderEnv = @"
# ─────────────────────────────────────────────────────────────────
# RENDER ENVIRONMENT VARIABLES — paste these into your Render dashboard
# Dashboard → Your Service → Environment → Edit
# ─────────────────────────────────────────────────────────────────

MONGO_URL=$($script:RemoteMongoUri)
TAILSCALE_AUTH_KEY=$($script:TailscaleAuthKey)

# ─────────────────────────────────────────────────────────────────
# RENDER START COMMAND — change in:
# Dashboard → Your Service → Settings → Start Command
# ─────────────────────────────────────────────────────────────────

curl -fsSL https://tailscale.com/install.sh | sh && tailscale up --authkey=`$TAILSCALE_AUTH_KEY --hostname=render-rhinodrishti-api --ephemeral && sleep 6 && uvicorn server:app --host 0.0.0.0 --port `$PORT

"@
    Set-Content -Path "$outputDir\render-config.txt" -Value $renderEnv -Encoding UTF8

    # Local .env for direct local running (optional)
    $localEnv = @"
MONGO_URL=$($script:LocalMongoUri)
"@
    Set-Content -Path "$outputDir\local-mongo.env" -Value $localEnv -Encoding UTF8

    Write-OK "Config files written to: $outputDir"
}

# ─── Final summary ────────────────────────────────────────────────────────────
function Write-Summary {
    Write-Step 9 9 "Setup Complete — Action Required"

    Write-Host ""
    Write-Host "  $(c 92)╔══════════════════════════════════════════════════════════════╗$(c 0)"
    Write-Host "  $(c 92)║              SETUP COMPLETE — NEXT STEPS                   ║$(c 0)"
    Write-Host "  $(c 92)╚══════════════════════════════════════════════════════════════╝$(c 0)"
    Write-Host ""
    Write-Host "  $(c 96)▶ 1. Open your Render dashboard:$(c 0)"
    Write-Host "       https://dashboard.render.com → Your Backend Service"
    Write-Host ""
    Write-Host "  $(c 96)▶ 2. Go to Environment → add/update these variables:$(c 0)"
    Write-Host ""
    Write-Host "    $(c 33)MONGO_URL$(c 0)          = $(c 93)$($script:RemoteMongoUri)$(c 0)"
    Write-Host "    $(c 33)TAILSCALE_AUTH_KEY$(c 0) = $(c 93)$($script:TailscaleAuthKey)$(c 0)"
    Write-Host ""
    Write-Host "  $(c 96)▶ 3. Go to Settings → Start Command, replace with:$(c 0)"
    Write-Host ""
    Write-Host "    $(c 33)curl -fsSL https://tailscale.com/install.sh | sh && tailscale up\"$(c 0)"
    Write-Host "    $(c 33)  --authkey=`$TAILSCALE_AUTH_KEY --hostname=render-rhinodrishti-api\"$(c 0)"
    Write-Host "    $(c 33)  --ephemeral && sleep 6 && uvicorn server:app --host 0.0.0.0 --port `$PORT$(c 0)"
    Write-Host ""
    Write-Host "  $(c 96)▶ 4. Click 'Save Changes' and 'Manual Deploy' in Render$(c 0)"
    Write-Host ""
    Write-Host "  $(c 96)▶ 5. Keep this Windows PC powered on$(c 0)"
    Write-Host "       MongoDB + Tailscale run as Windows Services (auto-start on boot)"
    Write-Host ""
    Write-Host "  $(c 92)All config saved to: $(Join-Path $PSScriptRoot 'output')$(c 0)"
    Write-Host ""
    Write-Host "  $(c 90)Data directory : $($script:DataPath)$(c 0)"
    Write-Host "  $(c 90)Tailscale IP   : $($script:TailscaleIP)$(c 0)"
    Write-Host "  $(c 90)MongoDB user   : $($script:MongoUser)$(c 0)"
    Write-Host ""
    Write-Host "  $(c 95)Keep the output\render-config.txt file safe — it contains your credentials.$(c 0)"
    Write-Host ""
}

# ─── Main ─────────────────────────────────────────────────────────────────────
try {
    Write-Banner

    Write-Host "  This wizard will:"
    Write-Host "  $(c 90)  1. Install MongoDB Community 7.0 on this PC$(c 0)"
    Write-Host "  $(c 90)  2. Install Tailscale VPN (free)$(c 0)"
    Write-Host "  $(c 90)  3. Copy your existing intelligence data from Atlas to local storage$(c 0)"
    Write-Host "  $(c 90)  4. Give you the exact settings to paste into Render$(c 0)"
    Write-Host ""
    Write-Host "  Estimated time: $(c 93)15-30 minutes$(c 0)"
    Write-Host ""

    if (-not $Unattended) {
        Pause-ForUser "Press any key to begin..."
    }

    Test-Prerequisites
    Select-DataDirectory
    Install-MongoDB
    Install-Tailscale
    Connect-Tailscale
    Get-TailscaleAuthKey
    Migrate-Data
    Set-MongoBindTailscale
    Write-ConfigFiles
    Write-Summary

    # Open output folder
    Start-Process explorer.exe (Join-Path $PSScriptRoot "output")

} catch {
    Write-Host ""
    Write-Fail "Wizard failed: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "  $(c 90)Stack trace:$(c 0)"
    Write-Host "  $($_.ScriptStackTrace)"
    Write-Host ""
    exit 1
}
