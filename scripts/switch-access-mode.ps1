param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'baseline', 'cloudflare')]
    [string]$Mode,

    [string]$Namespace = 'default'
)

$ErrorActionPreference = 'Stop'

function Get-CloudflaredDeployment {
    kubectl get deployment cloudflared -n $Namespace --ignore-not-found -o json
}

switch ($Mode) {
    'status' {
        $ingressIp = kubectl get svc ingress-nginx-controller -n $Namespace -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
        $cloudflared = Get-CloudflaredDeployment

        Write-Host "Baseline 1.0.0 web path:" -ForegroundColor Cyan
        Write-Host "  Azure ingress IP: $ingressIp"

        if ([string]::IsNullOrWhiteSpace($cloudflared)) {
            Write-Host "Cloudflare Quick Tunnel:" -ForegroundColor Cyan
            Write-Host "  Deployment cloudflared does not exist in namespace '$Namespace'."
            break
        }

        $deployment = $cloudflared | ConvertFrom-Json
        $replicas = if ($null -ne $deployment.spec.replicas) { $deployment.spec.replicas } else { 0 }
        $available = if ($null -ne $deployment.status.availableReplicas) { $deployment.status.availableReplicas } else { 0 }

        Write-Host "Cloudflare Quick Tunnel:" -ForegroundColor Cyan
        Write-Host "  Desired replicas: $replicas"
        Write-Host "  Available replicas: $available"

        if ($available -gt 0) {
            Write-Host ""
            Write-Host "Latest tunnel log lines:" -ForegroundColor Yellow
            kubectl logs deployment/cloudflared -n $Namespace --tail=30
        }
    }

    'baseline' {
        kubectl scale deployment/cloudflared -n $Namespace --replicas=0
        kubectl rollout status deployment/cloudflared -n $Namespace

        $ingressIp = kubectl get svc ingress-nginx-controller -n $Namespace -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
        Write-Host "Cloudflare Quick Tunnel disabled." -ForegroundColor Green
        Write-Host "Use the baseline 1.0.0 path via Azure ingress IP: $ingressIp" -ForegroundColor Green
    }

    'cloudflare' {
        kubectl scale deployment/cloudflared -n $Namespace --replicas=1
        kubectl rollout status deployment/cloudflared -n $Namespace

        Write-Host "Cloudflare Quick Tunnel enabled." -ForegroundColor Green
        Write-Host "Read the current trycloudflare.com URL from the log output below:" -ForegroundColor Green
        kubectl logs deployment/cloudflared -n $Namespace --tail=50
    }
}