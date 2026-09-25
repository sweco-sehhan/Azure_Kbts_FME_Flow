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

## Snapshot and rollback coordination

Use this section right before the upgrade window so the rollback path is explicit and documented.

### Azure check performed on 2026-09-23

The following discovery steps were used to identify the snapshot targets in Azure:

```powershell
az account show --output table
az resource list -g devoted-oarfish-rg --query "[].{name:name,type:type,location:location}" -o table
az resource list -g MC_devoted-oarfish-rg_devoted-oarfish-aks_swedencentral --query "[].{name:name,type:type,location:location}" -o table
az disk show -g MC_devoted-oarfish-rg_devoted-oarfish-aks_swedencentral -n pvc-468f3977-2a49-4f45-9b05-7085094ecfb2 -o json
az disk show -g MC_devoted-oarfish-rg_devoted-oarfish-aks_swedencentral -n pvc-a1b154a9-379b-4e57-8d2b-5f5a32cf1d41 -o json
```

Discovered snapshot targets:

- Subscription: `30002416 - FME-support`
- AKS resource group: `devoted-oarfish-rg`
- AKS node resource group: `MC_devoted-oarfish-rg_devoted-oarfish-aks_swedencentral`
- FME Flow PVC disk: `pvc-468f3977-2a49-4f45-9b05-7085094ecfb2`
- PostgreSQL PVC disk: `pvc-a1b154a9-379b-4e57-8d2b-5f5a32cf1d41`

The disks are tagged as:

- `kubernetes.io-created-for-pvc-name = fmeflow-data`
- `kubernetes.io-created-for-pvc-name = fmeflow-postgresql`

Snapshots created from those disks:

- `fmeflow-data-20260923`
- `fmeflow-postgresql-20260923`

### 1. Capture the PVCs that need protection

The exported chart state shows these PVC names in the current release:

- `fmeflow-pvc` for FME Flow data
- `fmeflow-postgresql` for PostgreSQL data

```powershell
$namespace = "default"
kubectl get pvc -n $namespace
kubectl get pv
```

Use the commands below to confirm the bound PV for each PVC.

```powershell
$fmeflowPvc = "fmeflow-pvc"
$fmeflowPv = kubectl get pvc $fmeflowPvc -n $namespace -o jsonpath="{.spec.volumeName}"
kubectl get pv $fmeflowPv -o jsonpath="{.spec.csi.volumeHandle}"
```

Repeat the same pattern for PostgreSQL.

```powershell
$postgresPvc = "fmeflow-postgresql"
$postgresPv = kubectl get pvc $postgresPvc -n $namespace -o jsonpath="{.spec.volumeName}"
kubectl get pv $postgresPv -o jsonpath="{.spec.csi.volumeHandle}"
```

### 2. Create the snapshots

If the PV is backed by an Azure Disk CSI volume, use the volume handle as the source for an Azure snapshot.

```powershell
$snapshotName = "fmeflow-data-20260923"
$resourceGroup = "<rg-with-the-disk>"
$diskId = kubectl get pv $fmeflowPv -o jsonpath="{.spec.csi.volumeHandle}"
az snapshot create -g $resourceGroup -n $snapshotName --source $diskId
```

Repeat for the PostgreSQL disk with a separate snapshot name.

```powershell
$snapshotName = "fmeflow-postgres-20260923"
$resourceGroup = "<rg-with-the-disk>"
$diskId = kubectl get pv $postgresPv -o jsonpath="{.spec.csi.volumeHandle}"
az snapshot create -g $resourceGroup -n $snapshotName --source $diskId
```

If the storage class is not Azure Disk CSI, use the equivalent platform-specific snapshot or backup mechanism and record the artifact IDs in the change notes.

### 3. Record rollback coordination

Before starting the upgrade, write down:

- rollback owner
- rollback decision time
- snapshot names or IDs
- current release name and namespace
- current image tag and chart version

### 4. Decide rollback scope up front

- AKS-only rollback means reverting the FME Flow release while leaving on-prem REMS untouched.
- Full rollback means reverting AKS and, if needed, restoring on-prem REMS to the last known good build.
- Do not mix rollback decisions with the upgrade decision point; set the decision time before you begin.

## FME Flow 2026.3 upgrade commands

Use this command set once the preflight items in [upgrade-2026-3-checklist.md](upgrade-2026-3-checklist.md) are complete.

### How the 2026.3 image tag was verified

The target tag was verified against Docker Hub before the rollout.

```powershell
Invoke-RestMethod "https://registry.hub.docker.com/v2/repositories/safesoftware/fmeflow-core/tags?page_size=100" |
  Select-Object -ExpandProperty results |
  Where-Object { $_.name -like '2026.3*' } |
  Select-Object name
```

After identifying `2026.3-20260916`, the same tag was checked across the required images:

```powershell
$images = @(
  'fmeflow-core',
  'fmeflow-web',
  'fmeflow-queue',
  'fmeflow-engine',
  'fmeflow-deployment-tester'
)

foreach ($image in $images) {
  $url = "https://registry.hub.docker.com/v2/repositories/safesoftware/$image/tags/2026.3-20260916"
  try {
    $tag = Invoke-RestMethod $url
    [PSCustomObject]@{
      image = $image
      tag = $tag.name
      last_updated = $tag.last_updated
    }
  }
  catch {
    [PSCustomObject]@{
      image = $image
      tag = 'missing'
      last_updated = $null
    }
  }
}
```

### Engine and license activation model

In this environment, Kubernetes replicas and active engine licensing are not treated as the same thing.

- AKS can keep engine replicas pre-provisioned.
- FME Flow decides through its web UI or REST API whether the second engine license remains delegated to on-prem or becomes active on the AKS side.
- This supports a scripted mode switch where a pre-run script disables the on-prem assignment and tells Flow that AKS should own two engines.
- Because of that model, replica count may intentionally stay at 2 in AKS even when only one AKS engine is actively licensed at a given moment.

### 1. Prepare a UTF-8 copy of the exported values file

The exported values file is UTF-16. Helm reads it reliably if you create a temporary UTF-8 copy first.

```powershell
$src = "C:\Users\SEHHAN\OneDrive - Sweco AB\FME\Azure_Kbts_FME_Flow\exports\helm-values-fmeflow.yaml"
$tmp = Join-Path $env:TEMP "helm-values-fmeflow-utf8.yaml"
Get-Content -Raw -Encoding Unicode $src | Set-Content -Encoding utf8 $tmp
```

### 2. Dry-run the upgrade with Helm

```powershell
helm upgrade fmeflow safesoftware/fmeflow --version 2.9.0 -f $tmp --namespace default --dry-run=client --debug
```

### 3. Optionally render the final manifest to inspect it before apply

```powershell
helm template fmeflow safesoftware/fmeflow --version 2.9.0 -f $tmp --namespace default
```

### 4. Apply the upgrade for real

```powershell
helm upgrade fmeflow safesoftware/fmeflow --version 2.9.0 -f $tmp --namespace default --wait --timeout 10m
```

### 5. Watch the rollout and verify the release

```powershell
helm status fmeflow --namespace default
kubectl get pods -n default
kubectl rollout status deployment/fmeflow -n default
```

### 6. Validate the application after rollout

```powershell
kubectl get svc -n default
kubectl logs deployment/fmeflow -n default --tail=100
```

### 7. If Helm reports a field-ownership conflict

If the upgrade fails with a conflict on `engine-standard-group` or `.spec.replicas`, do not guess.

- Confirm the live engine replica count.
- In this environment the live deployment had been scaled to 1 replica while Helm expects 2.
- Reconcile the live state before retrying:

```powershell
kubectl scale deployment/engine-standard-group -n default --replicas=2
kubectl rollout status deployment/engine-standard-group -n default
```

- Re-run the dry-run and apply again once the live replica count matches the Helm values.
- Only use `--force` if you explicitly intend to replace resources and accept the risk.

### 8. Roll back if needed

```powershell
helm rollback fmeflow 7 --namespace default --wait --timeout 10m
kubectl rollout status deployment/fmeflow -n default
```

Replace `7` with the last known good revision from `helm history fmeflow -n default`.

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

## REMS troubleshooting after the 2026.3 upgrade

### Verified findings from this incident

The following was verified from the AKS side after the FME Flow 2026.3 upgrade:

- The reverse SSH tunnel was up and the on-prem host had an `Established` connection to `4.165.180.65:22`.
- The `ssh-proxy` pod was running and the `onprem-tunnel` service had a live endpoint.
- `http://onprem-tunnel:9090/fmeserver` redirected to `/fmeserver/`.
- `http://onprem-tunnel:9090/fmeserver/` returned `401`, which confirms that the REMS web application was reachable and protected by authentication.
- `https://onprem-tunnel:9090` produced an SSL/protocol error and should not be used for this path.
- FME Flow stored the REMS connection in `fme_remote_engine_conn`, but the row remained incomplete and not ready.

The following was verified from the on-prem side after the FME Flow Remote Engine Services 2026.3 installation:

- The installer-created 2026.3 service accounts did not have sufficient rights to start the on-prem FME Flow services.
- `FME Flow Database` failed to start first, which caused `FME Flow Core` and `FME Flow Engines` to fail with dependency error `1068`.
- Changing the affected on-prem FME Flow services to run under Local System allowed Database/Core/Engines to start again.
- After the service-account issue was fixed, the REMS web application still failed its first password-change/bootstrap flow.
- The REMS UI accepted that the new password met policy requirements, but submission still returned `Invalid password parameters`.
- If the password-change flow was bypassed or retried, the local REMS UI still returned `invalid credentials`, so the password change could not be confirmed as successful.

Useful verification commands:

```powershell
kubectl get svc onprem-tunnel -n default -o wide
kubectl get endpoints onprem-tunnel -n default -o wide
kubectl run rems-probe --rm -i --restart=Never -n default --image=curlimages/curl:8.12.1 --command -- sh -lc "curl -sS -D - http://onprem-tunnel:9090/fmeserver/ -o /tmp/body.txt; sed -n '1,20p' /tmp/body.txt"
kubectl exec database-0 -n default -- env PGPASSWORD=a6av3abwzi psql -U postgres -d fmeflow -c "select id,name,url,username,status,uploaded_config,uploaded_key,uploaded_security_policy,updated from fme_remote_engine_conn order by updated desc;"
```

Example incomplete REMS state seen during this incident:

- `status = 0`
- `uploaded_config = f`
- `uploaded_key = f` or `t` depending on how far registration progressed
- `uploaded_security_policy = f`

This means Flow could reach the REMS endpoint but had not completed the REMS bootstrap or authentication handshake.

An empty result from `fme_remote_engine_conn` means the core has no REMS connection stored at all. A newly created but failing connection was also observed in this form:

- `status = 0`
- `uploaded_config = f`
- `uploaded_key = f`
- `uploaded_security_policy = f`

That pattern means the connection was created in Flow but failed before even the first configuration upload step.

### Recovery plan for a stuck REMS registration

Use this order when REMS stays `offline`, `initializing`, or reports `invalid credentials` from Flow.

1. Verify the reverse tunnel first.
2. Verify that `http://onprem-tunnel:9090/fmeserver/` is reachable from AKS and returns an auth challenge instead of `404`.
3. Remove the incomplete REMS connection from FME Flow.
4. On the on-prem host, restart the Remote Engine Services application and wait for the local REMS UI to stop reporting `FME Flow is not ready yet`.
5. Recreate the REMS connection in FME Flow with:

```text
http://onprem-tunnel:9090/fmeserver
```

6. Use a known-good REMS account credential on the host side. Do not keep retrying mixed historic passwords once the connection has entered a half-configured state.
7. Recheck the database row in `fme_remote_engine_conn` and confirm that the connection moves away from `status = 0` and that configuration fields are no longer false.

### Service-account caution from this incident

On this environment, the 2026.3 installation-created service accounts on the on-prem REMS host did not have enough privileges to start the local FME Flow stack reliably.

Observed restart symptoms:

- `FME Flow Database` could not be started.
- `FME Flow Core` failed with dependency error `1068`.
- `FME Flow Engines` failed with dependency error `1068`.

Temporary workaround used during this incident:

- switch the affected on-prem FME Flow services to Local System
- restart the services

Do not treat this as a product best practice by default. Treat it as an environment-specific recovery measure until Safe confirms the correct permanent service-account model for this REMS installation.

### PostgreSQL coexistence caution for 2026.3 installs

Additional field finding from a parallel 2026.3 upgrade attempt:

- Installing FME Flow 2026.3 on a machine that already has an active PostgreSQL instance can cause the database installation step to hang.
- In that state, the local FME Flow services may fail to start correctly after installation.
- A practical workaround observed in testing was to stop the existing PostgreSQL service during the FME Flow 2026.3 installation.
- It was not necessary to uninstall the existing PostgreSQL instance entirely for that workaround.

Recommended precaution before another on-prem 2026.3 install attempt:

```powershell
Get-Service | Where-Object { $_.Name -match 'postgres' -or $_.DisplayName -match 'PostgreSQL' }
Stop-Service -Name <postgres-service-name>
```

After the FME Flow installation completes, restore the expected PostgreSQL service state deliberately rather than assuming the installer handled it cleanly.

### Account-reset note

Safe support search clearly surfaced the following relevant topics:

- `Remote Engines Services`
- `Installing Remote Engines Services`
- `Leverage Remote Engine Service in FME Flow`

During this session no authoritative Safe article was confirmed for a direct host-side REMS account password reset workflow. Treat the host-side REMS account as the source of truth, and if the account cannot be updated through the REMS UI after restart, use the local product documentation or Safe support guidance before editing files or registry values manually.

Additional verified note from this incident:

- A freshly installed REMS host was expected to accept the default first-use admin password and then force a password change.
- In this environment, the REMS UI instead reported `Invalid password parameters` even when the GUI indicated that the new password satisfied the password policy.
- Because of that behavior, the first-use admin bootstrap could not be completed reliably and the REMS connection from the core stayed unusable.

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
