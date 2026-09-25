# FME Flow 2026.3 upgrade checklist

Use this checklist for the actual change window. It assumes the plan in [upgrade-2026-3-plan.md](upgrade-2026-3-plan.md) has already been approved.

## Before the window

- [x] Confirm target AKS image tag: `2026.3-20260916`
- [x] Confirm Helm chart stays on `2.9.0` for the first attempt
- [x] Confirm the FME Flow `.fsb` backup is current
- [x] Confirm the encryption key is available
- [x] Confirm PVC or storage snapshots exist for data and PostgreSQL
- [x] Confirm current Helm values and release history are exported
- [x] Confirm no critical jobs are running in AKS
- [x] Confirm no critical jobs are running on the on-prem queue
- [x] Confirm the Cloudflare path is understood as additive only
- [x] Confirm the rollback owner and decision time

	- Rollback owner: SEHHAN
	- Decision time: 2026-09-23

## AKS stage

- [x] Update `fmeflow.image.tag` to `2026.3-20260916`
- [x] Keep chart version pinned to `2.9.0`
- [x] Review the rendered Helm diff before applying
- [x] Apply the Helm upgrade
- [x] Wait for rollout completion
- [x] Confirm Core pod is healthy
- [x] Confirm Web service in core pod is healthy
- [x] Confirm Queue pod is healthy
- [x] Confirm Websocket pod is healthy
- [x] Confirm `engineregistration` still works
- [x] Confirm the UI loads
- [ ] Confirm API access works
- [ ] Confirm licensing is healthy
- [ ] Run one AKS-engine test job

## On-prem stage

- [ ] Stop or pause the current Remote Engine Service on Windows Server
- [ ] Install the approved 2026.3 Remote Engine Service build
- [ ] Verify the service configuration
- [ ] Start the service
- [x] Confirm the reverse tunnel reconnects
- [ ] Confirm FME Flow shows the remote engine as ready
- [ ] Run one job against the on-prem queue

## Return to service

- [ ] Re-enable schedules
- [ ] Re-enable automations
- [ ] Re-enable the on-prem queue for users
- [ ] Confirm Cloudflare access is still working if enabled
- [ ] Capture final version numbers and any deviations

## Rollback triggers

- [ ] AKS pods do not become healthy in time
- [ ] UI or API is unavailable after the AKS upgrade
- [ ] `engineregistration` is broken after the AKS upgrade
- [ ] The on-prem service cannot connect back to AKS
- [ ] The on-prem queue test job fails for upgrade-related reasons
