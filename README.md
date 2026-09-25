# Azure_Kbts_FME_Flow

This repository contains the baseline project for an FME Flow deployment running on Azure Kubernetes Service (AKS), with a hybrid access pattern that separates user access to the web application from the outbound connection used by on-prem FME Remote Engine Services.

## Project purpose

The solution is designed to run FME Flow in Azure while keeping the execution model flexible:

- Web and administrative traffic to the FME Flow web interface should be reachable via a secure public entry point.
- FME Remote Engine Services can remain on-prem and connect outbound to Azure using a reverse tunnel.
- This pattern keeps the on-prem engine protected behind the corporate firewall while still allowing Azure-hosted FME Flow to dispatch jobs to it.

The current project baseline is version 1.0.0.

## High-level architecture

The setup follows a hybrid pattern:

1. Azure-hosted FME Flow in AKS provides the web application, core services, and job orchestration.
2. On-prem FME Remote Engine Services connect back to Azure using an outbound reverse tunnel instead of exposing on-prem services directly to the internet.
3. User access to the Azure-hosted FME Flow UI is separated from the engine connection path and should ideally use a hostname-based entry point such as Cloudflare or a corporate reverse proxy.

This separation is important because the web application path and the engine connectivity path are different concerns.

## Why this architecture was chosen

A raw Azure public IP can often be blocked or degraded by enterprise controls such as:

- direct-IP browsing restrictions in browsers,
- web security tools or proxy policies,
- region or network policies,
- DNS or certificate assumptions that expect a hostname rather than a bare IP.

In practice, a hostname-based access path is more stable and easier to secure than exposing a raw Azure IP directly.

## Components in this repo

- [scripts/create_aks.ps1](scripts/create_aks.ps1) — Azure bootstrap script that creates the resource group, ACR, and AKS cluster.
- [k8s/fmeflow-deployment.yaml](k8s/fmeflow-deployment.yaml) — deployment definition for FME Flow in AKS.
- [k8s/fmeflow-service.yaml](k8s/fmeflow-service.yaml) — internal service for the application.
- [k8s/ingress.yaml](k8s/ingress.yaml) — ingress for external connectivity.
- [k8s/pvc.yaml](k8s/pvc.yaml) — persistent volume claim definition.
- [exports/](exports/) — exported Helm values and manifests.
- [architecture-simple.md](architecture-simple.md) — simplified architecture overview.
- [architecture-detailed.md](architecture-detailed.md) — more detailed architecture explanation.

## Typical traffic flow

### 1. User access to FME Flow

A user reaches the Azure-hosted FME Flow web UI through an external entry point, usually a hostname behind a proxy or ingress. In the current project, this is represented by the AKS ingress and Azure public IP path.

The expected login page is:

- /fmeserver/login

A request to the root path without authentication may return 401, which is normal behavior for FME Flow.

### 2. Reverse tunnel for Remote Engine Services

This is the critical path for on-prem execution.

- The on-prem FME Remote Engine initiates an outbound connection to Azure.
- The Azure side exposes a tunnel endpoint internally in the AKS cluster.
- FME Flow in Azure can then communicate with the on-prem engine through that tunnel.
- This avoids exposing the on-prem engine directly to the internet.

In other words, the connection is established from the on-prem side outward to Azure, not by exposing the on-prem service inbound.

### 3. Separation of access concerns

The web frontend and the remote engine tunnel are intentionally separate:

- FME Flow UI access is for users and administrators.
- Reverse tunnel connectivity is for job dispatch and remote execution.
- They should not be treated as one single exposure path.

This is also why a hostname-based front door such as Cloudflare or an internal reverse proxy is often a cleaner choice than exposing the Azure IP directly.

## Operational notes

- The project was validated as running from the Azure side, including the FME Flow login page path and service availability.
- The service responded correctly outside the corporate network, which strongly suggests the problem was environmental and policy-based rather than a cluster outage.
- Cloudflare or similar front-end access is optional and complementary to the reverse tunnel model.
- The reverse tunnel for Remote Engine Services should remain separate from the user-facing web access pattern.
- The baseline 1.0.0 ingress path and the optional `cloudflared` Quick Tunnel path can run in parallel and be switched operationally without changing the on-prem reverse tunnel.

## Prerequisites for deployment

- Azure CLI
- kubectl
- Docker for image builds when needed
- An Azure subscription with permission to create resource groups, ACR, and AKS
- FME Flow image or deployment package
- Appropriate secrets and configuration for the production environment

## Quick deployment sequence

```powershell
# Create resource group
az group create -n myResourceGroup -l northeurope

# Create ACR
az acr create -n myAcrName -g myResourceGroup --sku Basic --admin-enabled true

# Create AKS and attach ACR
az aks create -g myResourceGroup -n myAksCluster --node-count 3 --enable-addons monitoring --generate-ssh-keys --attach-acr myAcrName

# Get kube credentials
az aks get-credentials -g myResourceGroup -n myAksCluster

# Deploy the manifests
kubectl apply -f k8s/
```

## Repository layout

- [README.md](README.md) — project overview and architectural context
- [deployment-operations.md](deployment-operations.md) — Azure CLI, Docker, and kubectl command reference
- [cloudflare-access.md](cloudflare-access.md) — exact Cloudflare Tunnel and Access choices for the current AKS-native web-access solution
- [architecture-simple.md](architecture-simple.md) — simplified architecture diagram
- [architecture-detailed.md](architecture-detailed.md) — detailed architecture notes
- [scripts/create_aks.ps1](scripts/create_aks.ps1) — infrastructure bootstrap script
- [k8s/](k8s/) — Kubernetes manifests
- [exports/](exports/) — Helm and YAML exports

## Versioning

Current baseline:

- Version: 1.0.0
- Product: FME Flow
- Product version: 2026.3

## Security guidance

- Prefer a hostname-based public endpoint over exposing bare Azure IP addresses directly.
- Keep on-prem Remote Engine Services behind the corporate firewall.
- Preserve the reverse tunnel as the outbound communication path for remote execution.
- Do not treat the Cloudflare or ingress front end as a replacement for the on-prem engine tunnel.

## Current status

The repository is set up as a versioned baseline for an AKS-based FME Flow hybrid architecture and documents the separation between:

- public web access,
- remote execution via reverse tunnel,
- and on-prem FME Remote Engine connectivity.

