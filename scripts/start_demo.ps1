<#
.SYNOPSIS
    一键启动学径 StudyPath 演示环境（后端 8000 + 前端 5173）。

.DESCRIPTION
    - 已在运行的端口会被跳过（可重复执行）
    - -Reset 会先停掉占用端口的进程并重建演示库（会丢数据）
    - -Mock 用离线 mock 模型启动（无网络/无密钥时演示不会被降级提示打断）

.EXAMPLE
    .\scripts\start_demo.ps1
    .\scripts\start_demo.ps1 -Reset
    .\scripts\start_demo.ps1 -Mock -NoBrowser
#>
param(
    [switch]$Reset,
    [switch]$Mock,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$dbPath = Join-Path $root "data\dev_ui.db"

function Test-Port($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Wait-Health([int]$seconds = 40) {
    for ($i = 0; $i -lt $seconds; $i++) {
        try {
            $body = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3 -UseBasicParsing).Content
            if ($body -match '"service"\s*:\s*"ok"') { return $body }
        } catch { }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Find-Python {
    # 优先用 PATH 里的 python（能 import fastapi 才算可用）
    foreach ($candidate in @("python", "python3")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        & $cmd.Source -c "import fastapi" 2>$null
        if ($LASTEXITCODE -eq 0) { return $cmd.Source }
    }
    # 回退到本机 DSH 运行时的解释器
    $bundled = "D:\DSH\dsh-home\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundled) { return $bundled }
    throw "找不到可用的 Python（需要 fastapi）。请先 pip install -r backend\requirements.txt"
}

$python = Find-Python
$shell = (Get-Process -Id $PID).Path
$mode = if ($Mock) { "mock" } else { "real" }
Write-Host "Shell  : $shell"
Write-Host "Python : $python"
Write-Host "项目根 : $root`n"

# ---------- 可选：停掉旧进程 ----------
if ($Reset) {
    Write-Host "[1/4] 停止占用 8000 / 5173 的进程 ..."
    foreach ($port in 8000, 5173) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            try { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop } catch { }
        }
    }
    Start-Sleep -Seconds 2
}

# ---------- 可选：重建演示库 ----------
if ($Reset -or -not (Test-Path $dbPath)) {
    Write-Host "[2/4] 重建演示库 ..."
    Push-Location $backend
    try {
        & $python "scripts\seed.py" --db $dbPath
    } finally {
        Pop-Location
    }
}

# ---------- 后端 ----------
if (Test-Port 8000) {
    Write-Host "[3/4] 后端已在 8000 运行，跳过启动"
} else {
    Write-Host "[3/4] 启动后端（8000）..."
    $backendCmd = @"
`$env:PYTHONIOENCODING='utf-8'
`$env:DSH_PROVIDER_MODE='$mode'
Set-Location '$backend'
& '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"@
    Start-Process $shell -ArgumentList "-NoExit", "-Command", $backendCmd | Out-Null
}

$health = Wait-Health 40
if (-not $health) { throw "后端 40 秒内未就绪，请查看后端窗口的报错" }
try { $h = ($health | ConvertFrom-Json).data; Write-Host "      健康检查: service=$($h.service) database=$($h.database) provider=$($h.provider)" } catch { Write-Host "      健康检查: ok" }

# ---------- 前端 ----------
$pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
$pnpmPath = if ($pnpm) { $pnpm.Source } else { Join-Path $env:LOCALAPPDATA "npm-global\pnpm.cmd" }
if (-not (Test-Path $pnpmPath) -and -not $pnpm) { throw "找不到 pnpm，请先安装（npm i -g pnpm）" }

if (Test-Port 5173) {
    Write-Host "[4/4] 前端已在 5173 运行，跳过启动"
} else {
    Write-Host "[4/4] 启动前端（5173）..."
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Host "      node_modules 缺失，先安装依赖 ..."
        Push-Location $frontend
        try { & $pnpmPath install } finally { Pop-Location }
    }
    $frontendCmd = @"
`$env:PYTHONIOENCODING='utf-8'
Set-Location '$frontend'
& '$pnpmPath' dev --port 5173 --strictPort
"@
    Start-Process $shell -ArgumentList "-NoExit", "-Command", $frontendCmd | Out-Null
}

for ($i = 0; $i -lt 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -TimeoutSec 3 -UseBasicParsing
        break
    } catch { Start-Sleep -Seconds 1 }
}

# ---------- 收尾 ----------
$url = "http://127.0.0.1:5173"
Write-Host ""
Write-Host "====== 演示环境就绪 ======" -ForegroundColor Green
Write-Host "  前端: $url"
Write-Host "  接口: http://127.0.0.1:8000/api/health"
Write-Host "  学生: alice / Passw0rd!    （有已确认计划，22 个任务）"
Write-Host "  学生: bob   / Bob12345!    （空计划，适合演示"从零建计划"）"
Write-Host "  管理: admin / Admin123!    （课程内容维护）"
Write-Host "  模型: $mode"
Write-Host ""
Write-Host "演示步骤见 docs\09_过程记录\演示操作脚本_20261116.md"
Write-Host "重置数据: .\scripts\start_demo.ps1 -Reset"

if (-not $NoBrowser) { Start-Process $url }
