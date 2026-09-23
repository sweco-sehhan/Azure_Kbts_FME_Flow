# FME Flow AKS deployment operations

This document preserves the original operational commands and deployment details that were previously kept in the main README. The purpose is to keep the project overview in the README while storing the more implementation-heavy commands in a dedicated operations guide.

## Azure CLI: create resource group, ACR and AKS

```powershell
# Create resource group
az group create -n myResourceGroup -l <location>

# Create Azure Container Registry
az acr create -n myAcrName -g myResourceGroup --sku Basic --admin-enabled true

# Create AKS and attach ACR
az aks create -g myResourceGroup -n myAksCluster --node-count 3 --enable-addons monitoring --generate-ssh-keys --attach-acr myAcrName

# Get kubectl credentials
az aks get-credentials -g myResourceGroup -n myAksCluster
```

## Docker: build and push image to ACR

```powershell
az acr login -n myAcrName
docker build -t myAcrName.azurecr.io/fmeflow:latest .
docker push myAcrName.azurecr.io/fmeflow:latest
```

## Kubernetes: deploy manifests

```bash
kubectl apply -f k8s/
kubectl rollout status deployment/fmeflow
```

## Using :latest during development

If you want Kubernetes to always pull the newest image, keep the deployment configured with `imagePullPolicy: Always`.

```powershell
az acr login -n myacr
docker build -t myacr.azurecr.io/fmeflow:latest .
docker push myacr.azurecr.io/fmeflow:latest
```

Then restart or force a rollout:

```bash
kubectl rollout restart deployment/fmeflow
kubectl rollout status deployment/fmeflow

# or explicitly set the image
kubectl set image deployment/fmeflow fmeflow=myacr.azurecr.io/fmeflow:latest --record
kubectl rollout status deployment/fmeflow
```

## Docker registry secret (private ACR)

If the ACR is private, create a secret for image pulls:

```powershell
kubectl create secret docker-registry acr-secret \
  --docker-server=myacr.azurecr.io \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email>
```

## Notes and caveats

- Using `:latest` is convenient during development, but it is not ideal for production because it is not reproducible and makes rollbacks more difficult.
- For production, prefer semantic version tags or pinned digests.
- Replace image names, secret values, and configuration settings with your real production values before deployment.

## Operational reminders

- Use `kubectl apply -f k8s/` after updating manifests.
- Use `kubectl rollout status deployment/fmeflow` to confirm the rollout.
- Use `kubectl get pods -A` and `kubectl logs <pod>` when troubleshooting.
- Keep the Azure-hosted web access and the on-prem reverse tunnel as separate concerns.

## On-prem reverse tunnel

The validated on-prem reverse tunnel for the current test environment is now run as a Windows Task Scheduler job on the on-prem server:

```powershell
ssh -N -i C:\Users\SEHHAN_BD\.ssh\id_ed25519 -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes tunnel@4.165.180.65 -R 0.0.0.0:9090:127.0.0.1:8080
```

This command keeps the tunnel open from the on-prem host to Azure and exposes the on-prem local service on port `8080` to the AKS-side service name `onprem-tunnel:9090`.

For reference, the earlier manual PowerShell command was:

```powershell
ssh.exe -N -i id_ed25519 -R 0.0.0.0:9090:127.0.0.1:8080 tunnel@4.165.180.65
```

Operational notes:

- FME Flow in AKS connects to `http://onprem-tunnel:9090`.
- Because the tunnel is started by Task Scheduler, it is no longer tied to an interactive logon session.
- If the user logs out of Windows, the scheduled task can continue running as long as the task is configured to run whether the user is logged on or not.
- `StrictHostKeyChecking=accept-new` only accepts a previously unknown host key on first contact. It does not silently overwrite a changed host key; if the host key changes later, SSH still fails closed until `known_hosts` is updated.
- `ServerAliveInterval=30` and `ServerAliveCountMax=3` help SSH notice a broken connection and exit instead of hanging indefinitely.
- `ExitOnForwardFailure=yes` makes the process fail fast if the reverse forward cannot be established.

If you need a future auto-recovery solution with a Windows service instead of Task Scheduler, the same tunnel can be wrapped as a service and configured to restart automatically:

```powershell
sc create SSHTunnel binPath= "ssh -N -i C:\ProgramData\ssh\id_ed25519 -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes tunnel@4.165.180.65 -R 0.0.0.0:9090:127.0.0.1:8080" start= auto
sc stop SSHTunnel
sc start SSHTunnel
sc failure SSHTunnel reset= 86400 actions= restart/60000/restart/60000/restart/60000
```

Operational meaning of the service recovery settings:

- `reset= 86400` clears the failure counter after 24 hours of healthy runtime.
- `actions= restart/60000/restart/60000/restart/60000` tells Windows to restart the service after 60 seconds for the first, second, and subsequent failures.
- This recovery only triggers when the service process exits; the SSH keepalive options above are what make the process notice broken connectivity and terminate cleanly.

If the service uses a host key that can change on the SSH server side, the on-prem client may still need its stale `known_hosts` entry removed before reconnecting. The `accept-new` flag does not bypass host key mismatch failures.

## Running baseline and Cloudflare in parallel

Yes. The baseline 1.0.0 path and the optional Cloudflare Quick Tunnel path can coexist because they are separate entry points to the same FME Flow web service.

- Baseline 1.0.0 path: Azure ingress and public IP through `ingress-nginx-controller`
- Optional Cloudflare path: `cloudflared` deployment in AKS exposing a temporary `trycloudflare.com` URL
- On-prem reverse tunnel: unchanged and independent of both web-access paths

Operationally, you have two choices:

- Run both in parallel and decide per user which URL to share.
- Temporarily disable `cloudflared` and fall back to the baseline Azure ingress path only.

The helper script [scripts/switch-access-mode.ps1](scripts/switch-access-mode.ps1) supports three modes:

```powershell
./scripts/switch-access-mode.ps1 -Mode status
./scripts/switch-access-mode.ps1 -Mode baseline
./scripts/switch-access-mode.ps1 -Mode cloudflare
```

To print only the current Quick Tunnel URL:

```powershell
./scripts/get-cloudflare-url.ps1
```

Behavior:

- `status` shows the Azure ingress IP and the current `cloudflared` state.
- `baseline` scales `cloudflared` to zero replicas and leaves the original 1.0.0 ingress path active.
- `cloudflare` scales `cloudflared` to one replica and prints the latest `trycloudflare.com` log output.
