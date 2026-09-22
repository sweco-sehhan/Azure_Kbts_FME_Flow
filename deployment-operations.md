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
