<#
.SYNOPSIS
    停止学径 StudyPath 演示环境（释放 8000 / 5173）。
#>
$ErrorActionPreference = "SilentlyContinue"
foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen
    if (-not $conns) {
        Write-Host "端口 $port 未被占用"
        continue
    }
    foreach ($conn in $conns) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force
            Write-Host "已停止端口 $port 上的进程 $($conn.OwningProcess)"
        } catch {
            Write-Host "停止端口 $port 的进程失败: $($_.Exception.Message)"
        }
    }
}
