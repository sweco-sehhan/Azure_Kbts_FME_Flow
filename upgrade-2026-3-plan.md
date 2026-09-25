# FME Flow 2026.1 to 2026.3 upgrade plan

This document is a planning artifact only. It does not imply that any upgrade step has been executed.

## Scope

- Current live FME Flow version: 2026.1 build 26103 on Linux
- Current Helm chart line in exported deployment: `fmeflow-2.9.0`
- Current exported image tag in AKS: target state updated to `2026.3-20260916`; live cluster still needs the rollout
- Current optional web-access path: Cloudflare Quick Tunnel via `cloudflared`
- Current on-prem execution path: Remote Engine Services over the existing reverse SSH tunnel

## Assumptions

- AKS hosts the FME Flow control plane.
- On-prem Remote Engine Services remain outside Kubernetes.
- The Cloudflare path is additive and fronts only `fmeflowweb.default.svc.cluster.local:8080`.
- The Remote Engine path continues to use the separate reverse-tunnel route to `engineregistration:7070`.

## Step 1: Preflight checklist

Complete all items below before any production change window is approved.

### Version and packaging

- Confirm the exact target FME Flow 2026.3 Docker image tag for Core, Web, Queue, and Engine.
- Confirm the exact target version for on-prem Remote Engine Services.
- Confirm whether the upgrade can remain on Helm chart major 2.x.
- Do not assume chart 3.0.0 is required just because the target product version is 2026.3.

### Current-state capture

- Export the current Helm values for the live release.
- Export the current rendered manifests for the live release.
- Export Helm release history.
- Record the current AKS namespace, release name, and Kubernetes context.
- Record the current Cloudflare deployment state and current `trycloudflare.com` URL if it is enabled.
- Record the current on-prem Remote Engine Services version and host OS details.

### Backup and rollback prerequisites

- Verify that a recent `.fsb` backup exists.
- Export and securely store the FME Flow encryption key.
- Take a snapshot or equivalent backup of the FME Flow data PVC.
- Take a snapshot or equivalent backup of the PostgreSQL PVC.
- Verify that rollback access exists for the current image tag `2026.1-20260312`.
- Verify that the current chart package or pinned chart version can still be referenced during rollback.

### Operational freeze

- Pause or drain scheduled jobs that could submit work during the maintenance window.
- Pause or disable automations that submit jobs to either AKS engines or on-prem Remote Engine Services.
- Confirm whether any users or integrations depend on the temporary Cloudflare Quick Tunnel URL.
- Confirm the business owner for on-prem ArcGIS-near workloads during the outage.

### Validation readiness

- Identify one AKS-only test job.
- Identify one job that must run on the on-prem Remote Engine Services queue.
- Confirm who will validate the FME Flow UI, API, and on-prem execution path.
- Prepare a timed rollback decision point for both the AKS stage and the on-prem stage.

## Step 2: Upgrade day runbook

This runbook is sequenced to minimize variables. The target is a product-version upgrade first, not a chart-major migration.

### Concrete target values

- FME Flow image tag for AKS: `2026.3-20260916`
- Helm chart version for the first attempt: `2.9.0`
- Cloudflare path target service: `fmeflowweb.default.svc.cluster.local:8080`
- Remote Engine tunnel path: unchanged

### Stage A: Freeze and capture

1. Confirm the maintenance window is open.
2. Confirm no critical jobs are running in AKS.
3. Confirm no critical jobs are running through the on-prem queue.
4. Capture the final pre-upgrade state:
   - Helm values
   - Helm history
   - current image tags
   - current Cloudflare deployment state
   - current on-prem REMS status

Exit criteria for Stage A:

- No active critical jobs remain.
- All rollback artifacts are present and readable.

### Stage B: Upgrade AKS FME Flow first

1. Keep the existing deployment model and values structure unless a documented 2026.3 requirement forces a change.
2. Prefer a pinned image-tag upgrade on the current chart line before considering any chart-major change.
3. Do not mix these changes into the same window unless required:
   - chart 2.x to 3.0.0
   - ingress model migration
   - hostname model migration
   - Cloudflare path redesign
   - reverse-tunnel redesign

Suggested operator sequence for the AKS phase:

1. Update the FME Flow image tag in the exported values file from `2026.1-20260312` to `2026.3-20260916`.
2. Keep the chart pinned to `2.9.0` for the first attempt.
3. Review the rendered manifest before applying it.
4. Apply the Helm upgrade only after the rendered diff is acceptable.
5. Wait for the rollout to complete before validating the UI or engine path.

Example Helm flow for the first attempt:

```powershell
helm upgrade fmeflow safesoftware/fmeflow --version 2.9.0 -f exports/helm-values-fmeflow.yaml --namespace default
helm rollout status deployment/fmeflow -n default
```

If the release uses a different namespace, replace `default` with the live namespace.

If the chart or values file requires a different release name, use the current live release name instead of `fmeflow`.

Validation after the AKS upgrade:

- Core pod is healthy.
- Web pod is healthy.
- Queue pod is healthy.
- Websocket pod is healthy.
- `engineregistration` service path still functions.
- FME Flow UI loads.
- API login or authenticated API access works.
- Licensing is healthy.
- One AKS-engine test job completes successfully.

Rollback trigger for Stage B:

- Pods do not become healthy within the agreed timeout.
- UI or API is unavailable.
- `engineregistration` is broken.
- AKS-engine test job fails in a way attributable to the upgrade.

### Stage C: Upgrade on-prem Remote Engine Services second

1. Upgrade the on-prem Remote Engine Services host only after Stage B is fully accepted.
2. Keep the on-prem queue unavailable to users until validation is complete.
3. Upgrade the on-prem Remote Engine Services instance to the target 2026.3 line.

Suggested operator sequence for the on-prem phase:

1. Stop or pause the existing Remote Engine Service processes on the Windows Server.
2. Run the 2026.3 installer that matches the approved target build.
3. Reapply or verify the existing service configuration.
4. Start the service and confirm it connects back to the AKS core.
5. Keep the queue disabled until the validation job passes.

Validation commands and checks for the on-prem host:

- Confirm the REMS service is running in Services or Task Manager.
- Confirm the local REMS web UI opens on the host.
- Confirm the reverse tunnel process is still established.
- Confirm FME Flow shows the engine service as ready.
- Run one job that must route to the on-prem queue.

Suggested checks from the AKS side:

```powershell
kubectl get pods -n default
kubectl get svc -n default
kubectl logs deployment/fmeflow -n default --tail=100
```

If your namespace is not `default`, substitute the live namespace.

Validation after the on-prem upgrade:

- The local REMS instance starts successfully.
- The local REMS web UI or service endpoint is reachable on the host.
- The reverse SSH tunnel reconnects successfully.
- FME Flow can still reach the control path via `engineregistration:7070`.
- The dedicated on-prem queue shows the remote target as ready.
- One on-prem queue test job completes successfully.

Environment-specific caution observed during the 2026.3 attempt:

- The installer-created on-prem 2026.3 service accounts did not have enough rights to start the local FME Flow Database/Core/Engines services.
- Until that was corrected, REMS authentication and registration symptoms were misleading because the on-prem FME Flow stack was not actually healthy.
- Even after the services were brought up under Local System, the REMS first-use password change flow still failed with `Invalid password parameters` despite the UI showing that the password policy was satisfied.
- A separate field report indicated that installing FME Flow 2026.3 on a machine with an already-running PostgreSQL instance can hang the database installation step. Stopping the PostgreSQL service during installation may avoid that failure mode.

Rollback trigger for Stage C:

- REMS fails to start or remain healthy.
- The tunnel cannot be re-established.
- FME Flow cannot route to the on-prem REMS path.
- The on-prem queue test job fails in a way attributable to the upgrade.

### Stage D: Return to service

1. Re-enable schedules and automations in a controlled order.
2. Confirm whether Cloudflare Quick Tunnel should remain enabled or return to baseline ingress-only access.
3. Notify users that the maintenance window is closed.
4. Capture post-upgrade evidence:
   - final versions
   - final image tags
   - job validation results
   - any deviations from the plan

Rollback procedure for the on-prem phase:

1. Stop the upgraded REMS service.
2. Reinstall the last known good Windows installer if the upgrade failed.
3. Restore the previous service configuration if any settings changed.
4. Restart the service and confirm the tunnel comes back.
5. Re-run the on-prem queue test before re-enabling users.

Rollback decision rule:

- If the on-prem service cannot connect back to AKS or the test job fails, roll back the on-prem host before opening the queue to users.

## Step 3: Risk matrix

### Option A: Stay on Helm chart 2.x for the 2026.3 upgrade

Risk profile: lower

- Pros:
  - Smaller change surface
  - Keeps current ingress and selector behavior unchanged
  - Makes rollback simpler because the current deployment shape remains familiar
  - Keeps Cloudflare Quick Tunnel isolated from the product-version change
- Cons:
  - Defers chart modernization work
  - Does not address older ingress annotation conventions yet

Recommended use:

- Preferred first upgrade path if Safe supports the target 2026.3 image tag on the current chart major.

### Option B: Upgrade to Helm chart 3.0.0 in the same window

Risk profile: higher

- Pros:
  - Moves to the latest chart line
  - Aligns with current chart documentation and newer ingress expectations
- Cons:
  - Engine deployments require delete-and-recreate behavior because selectors are immutable
  - Ingress migration expectations differ from the current values structure
  - Rollback is more complex because both product version and deployment shape change together
  - Adds unnecessary variables to the same outage window

Recommended use:

- Only if 2026.3 requires chart 3.x or if you explicitly choose a larger maintenance window for both product and chart migration.

### Option C: Separate chart migration from product upgrade

Risk profile: medium across two windows, lower per window

- Pros:
  - Simplifies root-cause analysis if something fails
  - Makes rollback decisions clearer
  - Preserves a cleaner path back to the known-good `cloudflare-access` setup
- Cons:
  - Requires two planned maintenance windows
  - Extends the overall modernization timeline

Recommended use:

- Best long-term path if you want both low immediate risk and eventual chart modernization.

## Rollback answer for the current `cloudflare-access` setup

Yes, you can usually back out to the current FME Flow version with `cloudflare-access` without much difficulty, provided that the upgrade keeps the same release topology.

Rollback is relatively straightforward if all of the following remain true:

- You stay on the current chart major instead of moving to chart 3.0.0.
- You keep the current service target for Cloudflare as `fmeflowweb.default.svc.cluster.local:8080`.
- You do not redesign ingress or switch the tunnel model.
- You preserve access to the current image tag `2026.1-20260312`.
- You keep the `cloudflared` deployment separate from the product upgrade.

Why rollback is manageable in that case:

- `cloudflared` is an additive frontend only.
- It points at the in-cluster FME Flow web service, not at a version-specific external endpoint.
- The helper operational mode switch only scales the `cloudflared` deployment and does not modify FME Flow itself.
- The on-prem reverse tunnel is already a separate path and does not depend on the Cloudflare Quick Tunnel.

Rollback becomes less simple if any of the following are introduced in the same window:

- chart 3.0.0 migration
- ingress migration to the newer hostname-based pattern
- changes to service names or service URL mode
- changes to the reverse-tunnel architecture

## Known environment-specific cautions

- Repo metadata and exported target files now point at 2026.3, while the live cluster still reflects 2026.1 until the rollout is executed.
- Current values use older ingress conventions, including `useHostnameIngress: false`, `hostname: localhost`, and `nginx.ingress.kubernetes.io/*` annotations. That is another reason not to combine chart modernization with the version upgrade unless necessary.
- The Cloudflare Quick Tunnel URL is temporary and can change whenever the `cloudflared` pod restarts. It should not be treated as a stable rollback dependency.

## Recommended decision

For the first move, upgrade FME Flow from 2026.1 to 2026.3 on the smallest possible deployment delta.

- First choice: keep chart major 2.x if supported.
- Second choice: upgrade AKS FME Flow first and validate it fully.
- Third choice: upgrade on-prem Remote Engine Services only after the AKS side is stable.
- Defer any chart-major migration to a later, separate window unless Safe support or packaging forces the change now.