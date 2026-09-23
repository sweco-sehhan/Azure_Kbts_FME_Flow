param(
    [string]$Namespace = 'default'
)

$ErrorActionPreference = 'Stop'

$logs = kubectl logs deployment/cloudflared -n $Namespace --tail=200
$url = $logs | Select-String -Pattern 'https://[-a-z0-9]+\.trycloudflare\.com' -AllMatches |
    ForEach-Object { $_.Matches } |
    ForEach-Object { $_.Value } |
    Select-Object -Last 1

if ([string]::IsNullOrWhiteSpace($url)) {
    Write-Error "No trycloudflare.com URL found in recent cloudflared logs."
    exit 1
}

Write-Output $url