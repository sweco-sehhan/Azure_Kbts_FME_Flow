# Cloudflare access for FME Flow

This document implements the access-path decision captured in the Cloudflare access TODO for this branch.

## Selected model

- Tunnel model: Cloudflare Quick Tunnel using `cloudflared`
- Placement: a dedicated `cloudflared` pod inside the AKS cluster
- Deployment model: Kubernetes Deployment with no Cloudflare token and no owned domain requirement
- Scope: user access to the FME Flow web UI only
- Non-scope: the existing on-prem Remote Engine reverse tunnel remains unchanged

## Why this model fits the current environment

The current Azure resource group contains AKS, networking, and the FME resource, but no standalone Debian VM for a `cloudflared` system service.

The live AKS environment already exposes the web stack through Kubernetes services and ingress:

- Web ingress address: `9.223.239.145`
- SSH proxy address for the separate reverse tunnel path: `4.165.180.65`
- Current live web service in the cluster: `fmeflowweb.default.svc.cluster.local:8080`
- Baseline service name in the simple repo manifests: `fmeflow-svc.default.svc.cluster.local:80`

For this branch, `cloudflared` should front only the web UI path. It must not be attached to the SSH proxy or the `onprem-tunnel` service.

## Verified on-prem reverse tunnel

The on-prem Remote Engine path remains separate from the Quick Tunnel web path.

The validated SSH command for the current environment is:

```powershell
ssh.exe -N -i id_ed25519 -R 0.0.0.0:9090:127.0.0.1:8080 tunnel@4.165.180.65
```

This publishes the on-prem local service on `127.0.0.1:8080` to the Azure side as `onprem-tunnel:9090`, which is what FME Flow uses for the Remote Engine connection.

## Important distinction

The free rotating three-word address is not created from the Cloudflare dashboard flow for named tunnels.

It comes from a Quick Tunnel started by the `cloudflared` process itself. That is why the URL changes when the process restarts.

If you want the free rotating address, do not use the `Add published application` dialog and do not use a tunnel token.

## How Quick Tunnel works here

- `cloudflared` starts in AKS
- it publishes the in-cluster FME Flow web service
- Cloudflare returns a temporary public hostname under `trycloudflare.com`
- that hostname changes whenever the connector is recreated or restarted

This matches the behavior you described from your colleagues' setups.

## Kubernetes deployment

This branch now uses [k8s/cloudflared-deployment.yaml](k8s/cloudflared-deployment.yaml) to launch a Quick Tunnel directly to:

```text
http://fmeflowweb.default.svc.cluster.local:8080
```

Apply it with:

```bash
kubectl apply -f k8s/cloudflared-deployment.yaml
kubectl rollout status deployment/cloudflared
kubectl logs deployment/cloudflared --tail=100
```

The Cloudflare path is additive. It does not replace the baseline 1.0.0 ingress path. Both can exist at the same time.

If you want to switch operationally between them, use [scripts/switch-access-mode.ps1](scripts/switch-access-mode.ps1):

```powershell
./scripts/switch-access-mode.ps1 -Mode status
./scripts/switch-access-mode.ps1 -Mode baseline
./scripts/switch-access-mode.ps1 -Mode cloudflare
```

This only affects the optional `cloudflared` deployment. It does not change FME Flow itself and it does not affect the on-prem reverse SSH tunnel.

## How to get the free public address

Read the `cloudflared` logs after the pod starts.

You are looking for a line similar to:

```text
INF | Your quick Tunnel has been created! Visit it at:
INF | https://random-words-example.trycloudflare.com
```

PowerShell example:

```powershell
kubectl logs deployment/cloudflared --tail=100
```

Or use the helper script to print only the current URL:

```powershell
./scripts/get-cloudflare-url.ps1
```

That `trycloudflare.com` hostname is the free public address.

## What to do in the Cloudflare dashboard

Nothing for this Quick Tunnel scenario.

Do not create a hostname route in the dashboard if your goal is the free rotating address.

The dashboard flow is for named tunnels tied to a domain you control. That is a different product path.

## What not to use for this requirement

- Do not use a tunnel token
- Do not use `Add published application`
- Do not use an owned company domain
- Do not expect a stable hostname

## Validation checklist

Run these checks from your admin shell with `kubectl` access:

```bash
kubectl apply -f k8s/cloudflared-deployment.yaml
kubectl rollout status deployment/cloudflared
kubectl get pods -l app=cloudflared
kubectl logs deployment/cloudflared --tail=100
```

- `cloudflared` runs inside the cluster, so it can reach the web service directly without hairpinning through the public load balancer.
- This removes unnecessary dependence on the public ingress IP for the Cloudflare-to-origin hop.
- Using the in-cluster service avoids origin certificate and host-header mismatch issues.
- The Remote Engine reverse tunnel remains isolated on its existing path.

Run these checks from a browser:

- Open the `https://...trycloudflare.com` URL shown in the logs
- Confirm that `/fmeserver/login` loads
- Expect the hostname to change when the pod restarts

## What not to choose

- Do not point anything at `4.165.180.65`.
- Do not point anything at the `onprem-tunnel` service.
- Do not combine the web-access path with the Remote Engine reverse-tunnel path.
- Do not use Quick Tunnel as a production-grade permanent endpoint.

For clarity, the `4.165.180.65` address above is still correct for the separate on-prem SSH reverse tunnel. It must not be used as the origin for the Cloudflare web-access path.

## Recommended Cloudflare Access follow-up

Cloudflare Access policies in the dashboard are not the right follow-up for this free rotating Quick Tunnel pattern.

If you later need stable authentication policies, move to a named tunnel and a controlled domain.

Expected result:

- A temporary `trycloudflare.com` hostname is shown in the logs
- That hostname opens the FME Flow login page
- Existing on-prem Remote Engine reverse tunnel remains unchanged

## Operational note for this repo

The Cloudflare connector is introduced as an in-cluster frontend component. It complements the existing ingress and does not replace the separate `ssh-proxy` or `onprem-tunnel` path.