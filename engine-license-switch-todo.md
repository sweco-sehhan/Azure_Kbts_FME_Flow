# Engine License Switch TODO

## Goal
Implement a controlled way to switch Standard Engine licensing between AKS-hosted FME Flow engines and the on-prem Remote Engine Services host by using an FME Flow REST API v4 call from a pre-script that runs before selected workspaces.

## Current assumptions
- Total available Standard Engine capacity is `2`.
- Desired baseline mode is `1+1`: `1` Standard Engine active in AKS and `1` Standard Engine assigned to REMS.
- AKS can keep `2` engine replicas pre-provisioned even when only `1` AKS engine is effectively licensed.
- The on-prem Remote Engine Services connection can be present but show `Unlicensed` until core assigns engine capacity to it.
- The pre-script will run on an AKS-hosted queue, not on the remote queue it is trying to control.
- The controlling script should call FME Flow Core internally, not through Cloudflare or the public ingress path.

## Recommended control model
1. Keep a dedicated AKS queue for the control workspace that runs the pre-script.
2. Call FME Flow Core REST API v4 from the pre-script by using an internal base URL.
3. Store the FME Flow API token outside the workspace itself and inject it into the AKS runtime securely.
4. Treat the Remote Engine Services connection as the object whose Standard Engine count is switched between active and inactive states.
5. Verify the result after each API call before the main workspace continues.

## First implementation slice

The first implementation pass should stop before any production switching logic is enabled.

1. Prove the control workspace can run on a dedicated AKS queue.
2. Prove a script running there can reach FME Flow Core internally at `http://fmeflowweb:8080`.
3. Identify the exact REST API v4 endpoints and payloads for reading and updating the Remote Engines Service connection.
4. Decide how the API token reaches the engine runtime in practice.
5. Only after those four are confirmed, implement the real license-switch logic.

First acceptance test after implementation:

- both AKS-hosted FME Flow and on-prem REMS must have one licensed Standard Engine each
- the REMS connection must be `online` and `ready`
- one test job must run successfully on the AKS side
- one test job must run successfully on the REMS side

## Implementation checklist

### Design and scope
- [ ] Confirm the target operating modes:
  - Baseline `1+1` mode: `1` Standard Engine in AKS and `1` Standard Engine assigned to REMS.
  - Override `2+0` mode: `2` Standard Engines in AKS and `0` assigned to REMS.
- [ ] Confirm which workspaces are allowed to trigger a global engine-license switch.
- [ ] Confirm whether the license switch is one-way per job or whether a post-run reversal is required.
- [ ] Confirm the exact Remote Engine Services connection name in FME Flow Core.
- [ ] Confirm that the on-prem REMS connection is healthy and no longer blocked by first-use password issues before automating anything.

### Secrets and configuration
- [ ] Create an Azure Key Vault secret for the FME Flow API token.
- [ ] Decide the AKS secret-delivery pattern:
  - Key Vault CSI mount, or
  - synchronized Kubernetes Secret.
- [ ] Expose the API token to the AKS engine runtime as an environment variable, for example `FME_FLOW_API_TOKEN`.
- [ ] Define a stable internal base URL, for example `FME_FLOW_BASE_URL=http://fmeflowweb:8080`.
- [ ] Define a stable identifier for the REMS connection, for example `REMS_CONNECTION_NAME=<name>`.
- [ ] Define a switch target variable, for example `TARGET_REMOTE_STANDARD_ENGINES=0|1`.

### Networking and runtime
- [ ] Verify that AKS engine pods can reach `fmeflowweb:8080` internally.
- [ ] Verify that no Kubernetes `NetworkPolicy` blocks engine-to-core API calls.
- [ ] Do not depend on Cloudflare, public ingress, or the external Azure IP for this control path.
- [ ] Do not depend on speculative variables like `FME_ENGINE_HOST_NAME` unless the runtime proves they are required.

### Chart and deployment constraints
- [ ] Verify whether the current Helm chart exposes an official env-injection hook for engine pods.
- [ ] If no supported env hook exists, choose one of these implementation paths:
  - patch the engine deployment after Helm,
  - extend the Helm values/model with a supported template override,
  - or move the control logic out of the engine pod into a separate AKS control workload.
- [ ] Keep the chosen method compatible with future Helm upgrades so the control integration is not lost on the next rollout.

### API design
- [x] Identify the exact FME Flow REST API v4 endpoints needed to:
  - read the current Remote Engine Services connection,
  - update the Standard Engine count for that connection,
  - read back status until the connection reaches the expected state.
- [ ] Verify token scope and permissions for those endpoints.
- [x] Define the expected status transitions for the REMS connection, such as `Unlicensed -> Ready` or `Ready -> Unlicensed`.
- [ ] Define timeout and retry behavior for status polling.

Verified REMS-related REST API v4 endpoints from the local OpenAPI spec:

- `GET /fmeapiv4/remoteengines`
  - list REMS connections
- `POST /fmeapiv4/remoteengines`
  - create REMS connection
- `GET /fmeapiv4/remoteengines/{id}`
  - read one REMS connection
- `PUT /fmeapiv4/remoteengines/{id}`
  - replace/update one REMS connection
- `POST /fmeapiv4/remoteengines/{id}/test`
  - test an existing REMS connection
- `GET /fmeapiv4/remoteengines/{id}/engines`
  - list engines currently associated with the REMS connection
- `POST /fmeapiv4/remoteengines/{id}/accounts/{account}/password`
  - change REMS account password from core side when connection administration is functional

Verified key request/response fields:

- `name`
- `url`
- `username`
- `password`
- `queues`
- `numStandardEngines`
- `numDynamicEngines`
- response `status`: `offline | online | initializing | unlicensed`
- response `ready`: boolean

This confirms that the intended control lever is the REMS connection object itself, specifically `numStandardEngines`, not a speculative host-name environment variable.

### Pre-script behavior
- [x] Write the Python pre-script so it:
  - reads env vars,
  - calls REST API v4,
  - updates the REMS Standard Engine count,
  - polls until the requested state is reached,
  - fails fast with a clear error if the requested state is not reached.
- [ ] Ensure the script logs only non-sensitive status data.
- [ ] Ensure the script never prints the API token.
- [ ] Ensure the script can be run idempotently if the requested target state is already active.

### Validation plan
- [ ] Validate baseline `1+1` mode first and treat it as the normal steady state.
- [ ] Use `1+1` as the first acceptance test after implementation.
- [ ] Validate `2+0` mode by confirming REMS shows `Unlicensed` and AKS retains local capacity.
- [ ] Validate `1+1` mode by confirming REMS receives `1` Standard Engine and becomes usable.
- [ ] Run a dedicated test workspace on the AKS queue after a switch.
- [ ] Run a dedicated test workspace on the REMS queue after a switch.
- [ ] Confirm that failed switching leaves the platform in a known state.

### Failure handling
- [ ] Define what the pre-script should do if REMS stays `Initializing`, `Offline`, or `Unlicensed` longer than the timeout.
- [ ] Define whether the script should revert the attempted change on failure.
- [ ] Define an operator-only manual recovery path if the API switch succeeds partially.
- [ ] Record which on-prem and core-side checks must be run before retrying a failed switch.

### Documentation and rollout
- [ ] Document the final env vars, secret source, and queue placement.
- [ ] Document the exact REST API endpoints and payloads used.
- [ ] Document how operators manually verify the active license mode.
- [ ] Add a small operational runbook for switching to `1+1` and back to `2+0`.
- [ ] Gate production use on successful tests in both directions.

## Observed constraint in current environment

- The exported Helm values currently show no obvious `extraEnv`-style injection point for engine pods.
- The chart does expose structural values such as `annotations.engine.deployment`, `annotations.engine.template`, and engine group settings, but no verified secret-to-env hook has yet been confirmed from the exported configuration alone.
- Because of that, secret delivery into the pre-script runtime is still a design decision, not a solved detail.
- The rendered engine deployment does contain a fixed `env:` block, which means Kubernetes-level env injection is technically possible, but a chart-backed values hook for doing so has not yet been verified.

## Preferred implementation strategy

See also: [engine-license-switch-control-service-design.md](engine-license-switch-control-service-design.md)

### Preferred production path

Use a small internal control workload in AKS instead of injecting the FME Flow API token directly into every engine pod.

Target shape:

1. A small AKS control service or job owns the FME Flow API token.
2. The token is sourced from Azure Key Vault through a Kubernetes Secret or CSI mount.
3. The workspace pre-script calls the internal control service.
4. The control service performs the actual REST API v4 update against FME Flow Core.

Why this is preferred:

- avoids spreading the Core admin token to all engine pods
- avoids depending on a Helm env-injection hook that has not yet been verified
- keeps the global license-switch authority in one place
- gives a clearer place for retries, auditing, and rollback logic

### Acceptable prototype path

If a separate control workload is too much for the first prototype, use a post-Helm Kubernetes patch to inject the required environment variables into the `engine-standard-group` deployment.

Constraints of that path:

- more fragile across Helm upgrades
- broader token exposure because the token reaches the engine runtime directly
- requires careful reconciliation after every Helm rollout

### Deferred decision

Choose one of these before production implementation:

- `control-service` design
- `post-helm-patch` design

## Prototype artifact

- First prototype script added at [scripts/engine_license_switch.py](scripts/engine_license_switch.py).
- The script expects `FME_FLOW_BASE_URL`, `FME_FLOW_API_TOKEN`, `REMS_CONNECTION_NAME` or `REMS_CONNECTION_ID`, and `TARGET_REMOTE_STANDARD_ENGINES`.
- The script is intentionally a prototype and should not be treated as production-ready until token injection, endpoint permissions, and failure-handling behavior are validated.
- First control-service prototype added at [scripts/engine_license_switch_control_service.py](scripts/engine_license_switch_control_service.py).
- The control-service currently exposes `GET /healthz` and `POST /switch` and is intended for internal AKS use only.
- Minimal pre-script client added at [scripts/engine_license_switch_client.py](scripts/engine_license_switch_client.py) for calling the control-service instead of FME Flow Core directly.
- First AKS prototype manifests added at:
  - [k8s/engine-license-switch-control-service-configmap.yaml](k8s/engine-license-switch-control-service-configmap.yaml)
  - [k8s/engine-license-switch-control-service-deployment.yaml](k8s/engine-license-switch-control-service-deployment.yaml)
  - [k8s/engine-license-switch-control-service.yaml](k8s/engine-license-switch-control-service.yaml)
  - [k8s/engine-license-switch-control-service-secret.example.yaml](k8s/engine-license-switch-control-service-secret.example.yaml)
- First deploy/test runbook added at [engine-license-switch-control-service-runbook.md](engine-license-switch-control-service-runbook.md).

## Do not do
- Do not let the control workspace itself depend on the REMS queue it is trying to enable.
- Do not store the Flow API token directly in the workspace or repository.
- Do not route control traffic through Cloudflare.
- Do not assume REMS is healthy unless the connection reaches a verified ready state.