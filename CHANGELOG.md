# Changelog

## [1.0.0] - 2026-09-22

### Added
- Initial baseline project for Azure-hosted FME Flow on AKS.
- AKS provisioning script for resource group, ACR, and cluster creation.
- Kubernetes manifests for FME Flow deployment, service, ingress, and PVC.
- Project metadata defining FME Flow 2026.3 and on-prem FME Remote Engine Services via reverse tunnel.

### Notes
- This repository captures the initial working baseline for the architecture.
- Remote Engine Services remain behind the on-prem firewall and are reached through a reverse tunnel.
