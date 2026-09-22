# Azure AKS for FME Flow

This repo contains a minimal scaffold to deploy an FME Flow workload to Azure Kubernetes Service (AKS).

Prerequisites
- `az` (Azure CLI)
- `kubectl`
- `docker` (if building images locally)

Quick steps

1. Create resource group:

   `az group create -n myResourceGroup -l <location>`

2. Create Azure Container Registry (ACR) and push image:

   `az acr create -n myAcrName -g myResourceGroup --sku Basic --admin-enabled true`
   `az acr login -n myAcrName`
   `docker build -t myAcrName.azurecr.io/fmeflow:latest .`
   `docker push myAcrName.azurecr.io/fmeflow:latest`

3. Create AKS and attach ACR:

   `az aks create -g myResourceGroup -n myAksCluster --node-count 3 --enable-addons monitoring --generate-ssh-keys --attach-acr myAcrName`
   `az aks get-credentials -g myResourceGroup -n myAksCluster`

4. Deploy manifests:

   `kubectl apply -f k8s/`

Notes
- Replace image names, secrets, and configuration values with your production settings.
- Use `kubectl rollout status deployment/fmeflow` to watch deployment progress.

Files added
- `scripts/create_aks.ps1` — PowerShell helper to create RG, ACR, AKS
- `k8s/` — Kubernetes manifests (deployment, service, ingress, pvc)

Next steps
- Configure `Secret` objects for credentials before applying manifests.
- Optionally add Helm chart or Terraform for infrastructure as code.

Using `:latest` during development
---------------------------------

If you want Kubernetes to always pull and run the newest development image (workflow A), follow these steps:

- Build and push the image to your ACR (example):

   ```powershell
   az acr login -n myacr
   docker build -t myacr.azurecr.io/fmeflow:latest .
   docker push myacr.azurecr.io/fmeflow:latest
   ```

- Ensure the deployment uses `imagePullPolicy: Always` (the provided `k8s/fmeflow-deployment.yaml` already sets this). If your ACR is private, create an image pull secret and reference it in the Deployment:

   ```powershell
   kubectl create secret docker-registry acr-secret \
      --docker-server=myacr.azurecr.io \
      --docker-username=<username> \
      --docker-password=<password> \
      --docker-email=<email>
   ```

- Apply the manifests (or update them) and verify rollout:

   ```bash
   kubectl apply -f k8s/
   kubectl rollout status deployment/fmeflow
   ```

- After pushing a new `:latest` image, force pods to pull the new image with either:

   ```bash
   # restart the deployment so pods re-pull the latest image
   kubectl rollout restart deployment/fmeflow
   kubectl rollout status deployment/fmeflow

   # or explicitly set the image (useful to record change history)
   kubectl set image deployment/fmeflow fmeflow=myacr.azurecr.io/fmeflow:latest --record
   kubectl rollout status deployment/fmeflow
   ```

Notes and caveats
- Using `:latest` is convenient for development and quick testing, but it is not recommended for production because it is not reproducible and makes rollbacks harder.
- For production, prefer tagging images with semantic versions or pinning by digest; then update the Deployment to the specific tag or digest when you want to deploy a release.

