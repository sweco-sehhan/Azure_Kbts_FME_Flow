param(
    [string]$ResourceGroup = "fme-rg",
    [string]$Location = "northeurope",
    [string]$AcrName = "fmeacr",
    [string]$AksName = "fme-aks",
    [int]$NodeCount = 3
)

Write-Host "Creating resource group $ResourceGroup in $Location"
az group create -n $ResourceGroup -l $Location

Write-Host "Creating Azure Container Registry $AcrName"
az acr create -n $AcrName -g $ResourceGroup --sku Basic --admin-enabled true

Write-Host "Creating AKS cluster $AksName and attaching ACR"
az aks create -g $ResourceGroup -n $AksName --node-count $NodeCount --enable-addons monitoring --generate-ssh-keys --attach-acr $AcrName

Write-Host "Retrieving credentials for kubectl"
az aks get-credentials -g $ResourceGroup -n $AksName

Write-Host "Done. You can now run: kubectl apply -f k8s/"
