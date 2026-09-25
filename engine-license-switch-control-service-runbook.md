# Engine License Switch Control Service Runbook

## Goal
Deploy and test the internal AKS control service that switches REMS Standard Engine allocation through FME Flow REST API v4.

This runbook is for the prototype path only.

First acceptance target:

- establish `1+1` mode first
- verify one licensed Standard Engine on AKS and one on REMS
- verify successful test execution on both sides before attempting `2+0`

## Prerequisites
- The AKS-based FME Flow deployment is healthy.
- The REMS connection exists in FME Flow Core and is reachable.
- A valid FME Flow API token exists with permission to read and update Remote Engines Service connections.
- `kubectl` is connected to the target AKS cluster.

## Files used
- [k8s/engine-license-switch-control-service-configmap.yaml](k8s/engine-license-switch-control-service-configmap.yaml)
- [k8s/engine-license-switch-control-service-deployment.yaml](k8s/engine-license-switch-control-service-deployment.yaml)
- [k8s/engine-license-switch-control-service.yaml](k8s/engine-license-switch-control-service.yaml)
- [k8s/engine-license-switch-control-service-secret.example.yaml](k8s/engine-license-switch-control-service-secret.example.yaml)

## 1. Create the secret

Do not commit real token values to the repository.

Option A: create the secret directly with `kubectl`:

```powershell
kubectl create secret generic engine-license-switch-control-service-secrets \
  -n default \
  --from-literal=fme-flow-api-token="<REAL_FME_FLOW_API_TOKEN>" \
  --from-literal=control-service-shared-token="<OPTIONAL_INTERNAL_SHARED_TOKEN>"
```

Option B: copy the example file locally, fill values, and apply it from a non-committed path.

## 2. Deploy the control service

```powershell
kubectl apply -f k8s/engine-license-switch-control-service-configmap.yaml
kubectl apply -f k8s/engine-license-switch-control-service-deployment.yaml
kubectl apply -f k8s/engine-license-switch-control-service.yaml
kubectl rollout status deployment/engine-license-switch-control-service -n default
```

## 3. Verify the service is healthy

Port-forward locally:

```powershell
kubectl port-forward svc/engine-license-switch-control-service 18081:8081 -n default
```

In another shell:

```powershell
curl.exe http://127.0.0.1:18081/healthz
```

Expected response:

```json
{"ok": true, "status": "healthy"}
```

## 4. Dry-run a baseline `1+1` request

If you configured `CONTROL_SERVICE_SHARED_TOKEN`, add it as a bearer token.

```powershell
$headers = @{
  Authorization = "Bearer <OPTIONAL_INTERNAL_SHARED_TOKEN>"
  "Content-Type" = "application/json"
}

$body = @{
  connectionName = "onPremEngineTest"
  targetRemoteStandardEngines = 1
  targetRemoteDynamicEngines = 0
  expectedStatus = "online"
  expectedReady = $true
  timeoutSeconds = 180
  pollIntervalSeconds = 5
  dryRun = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18081/switch -Headers $headers -Body $body
```

Dry-run should not change the REMS connection. It should return the current state and/or a dry-run message.

## 5. Execute a real baseline `1+1` switch

```powershell
$headers = @{
  Authorization = "Bearer <OPTIONAL_INTERNAL_SHARED_TOKEN>"
  "Content-Type" = "application/json"
}

$body = @{
  connectionName = "onPremEngineTest"
  targetRemoteStandardEngines = 1
  targetRemoteDynamicEngines = 0
  expectedStatus = "online"
  expectedReady = $true
  timeoutSeconds = 180
  pollIntervalSeconds = 5
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18081/switch -Headers $headers -Body $body
```

This is the first required acceptance test. Do not move on to `2+0` until:

- the REMS connection shows `online`
- `ready` is `true`
- one test workspace succeeds on an AKS queue
- one test workspace succeeds on the REMS queue

## 6. Execute an override `2+0` switch

```powershell
$headers = @{
  Authorization = "Bearer <OPTIONAL_INTERNAL_SHARED_TOKEN>"
  "Content-Type" = "application/json"
}

$body = @{
  connectionName = "onPremEngineTest"
  targetRemoteStandardEngines = 0
  targetRemoteDynamicEngines = 0
  expectedStatus = "unlicensed"
  expectedReady = $false
  timeoutSeconds = 180
  pollIntervalSeconds = 5
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18081/switch -Headers $headers -Body $body
```

## 7. Validate from FME Flow Core

Confirm the REMS state directly from the API or UI after each switch.

Example direct API validation:

```powershell
curl.exe -H "Authorization: fmetoken token=<REAL_FME_FLOW_API_TOKEN>" http://127.0.0.1:18080/fmeapiv4/remoteengines
```

Things to confirm:
- `numStandardEngines` matches the requested value
- `status` changes as expected
- `ready` changes as expected

## 8. Roll back the prototype

To remove the prototype service from AKS:

```powershell
kubectl delete -f k8s/engine-license-switch-control-service.yaml
kubectl delete -f k8s/engine-license-switch-control-service-deployment.yaml
kubectl delete -f k8s/engine-license-switch-control-service-configmap.yaml
kubectl delete secret engine-license-switch-control-service-secrets -n default
```

## Notes
- Start with `1+1` as the desired baseline mode.
- Use `2+0` only as an explicit override.
- Do not point workspace pre-scripts at Cloudflare or public ingress for this control path.
- Do not store the real API token in repository-tracked files.