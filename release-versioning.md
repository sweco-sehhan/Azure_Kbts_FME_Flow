# Release Versioning

## Goal
Keep a clear and reproducible mapping between:

- FME Flow product version
- architecture mode
- Cloudflare access mode
- REMS license mode
- git tag / release label

This repository needs clear version identities for these states:

1. `2026.1`
2. `2026.3` without Cloudflare
3. `2026.3` with Cloudflare
4. `2026.3` with dynamic engine/license switching between AKS host and on-prem REMS, with or without Cloudflare

## Recommended version model

Use two layers of identification:

1. one semantic repository release number
2. one descriptive release tag suffix that captures the deployment mode

That gives readable git tags without overloading the semantic version itself.

Format:

```text
v<repo-version>-<mode>
```

Examples:

```text
v1.0.0-fmeflow-2026.1-baseline
v1.1.0-fmeflow-2026.3-baseline
v1.2.0-fmeflow-2026.3-cloudflare
v1.3.0-fmeflow-2026.3-license-switch-no-cloudflare
v1.3.1-fmeflow-2026.3-license-switch-cloudflare
```

## Recommended mapping

### 1. Existing baseline

- Intended deployment state: FME Flow `2026.1`
- Access mode: baseline ingress / no Cloudflare dependency
- REMS mode: fixed, no dynamic switching
- Recommended tag meaning: `v1.0.0-fmeflow-2026.1-baseline`

Current note:

- The repository currently has tag `v1.0.0`.
- Treat that as the historical `2026.1` baseline unless you decide to create an additional annotated compatibility tag for clarity.

### 2. 2026.3 without Cloudflare

- FME Flow version: `2026.3`
- Access mode: baseline ingress only
- REMS mode: no dynamic switching logic
- Recommended tag: `v1.1.0-fmeflow-2026.3-baseline`

### 3. 2026.3 with Cloudflare

- FME Flow version: `2026.3`
- Access mode: Cloudflare enabled
- REMS mode: no dynamic switching logic
- Current behavior note: this setup currently works with `2` AKS engine replicas on the host side
- Recommended tag: `v1.2.0-fmeflow-2026.3-cloudflare`

### 4. 2026.3 with dynamic engine/license switching

This should be treated as a separate feature line from plain `2026.3`, because it introduces runtime control logic, secrets handling, and an internal control service.

#### 4a. Dynamic switching without Cloudflare

- FME Flow version: `2026.3`
- Access mode: baseline ingress only
- REMS mode: dynamic `1+1` / `2+0` switching
- Recommended tag: `v1.3.0-fmeflow-2026.3-license-switch-no-cloudflare`

#### 4b. Dynamic switching with Cloudflare

- FME Flow version: `2026.3`
- Access mode: Cloudflare enabled
- REMS mode: dynamic `1+1` / `2+0` switching
- Recommended tag: `v1.3.1-fmeflow-2026.3-license-switch-cloudflare`

## Why this split

Cloudflare and dynamic REMS license switching are separate capability changes:

- Cloudflare changes the web-access path
- license switching changes runtime control behavior and security model

Keeping them as explicit release modes makes rollback and support much easier.

## Recommended tagging rules

### Rule 1

Create a git tag only after the state is:

- committed
- pushed
- validated in the target environment

### Rule 2

Do not reuse one tag for multiple runtime modes.

If Cloudflare status changes the deployed behavior, it gets its own tag.

### Rule 3

Treat dynamic license switching as a feature release, not as a hidden patch to the plain `2026.3` setup.

### Rule 4

Use annotated tags, not lightweight tags.

Example:

```powershell
git tag -a v1.2.0-fmeflow-2026.3-cloudflare -m "FME Flow 2026.3 with Cloudflare access"
git push origin v1.2.0-fmeflow-2026.3-cloudflare
```

## Recommended release order

1. Tag the stable `2026.3` baseline without Cloudflare.
2. Tag the stable `2026.3` Cloudflare-enabled variant.
3. Build and validate the dynamic switching feature.
4. Tag the dynamic switching variant without Cloudflare.
5. Tag the dynamic switching variant with Cloudflare only if you actually validate that combined mode.

## Status tracking suggestion

Use this simple release matrix in future PRs or release notes:

| Tag | FME Flow | Cloudflare | REMS switching | Status |
| --- | --- | --- | --- | --- |
| `v1.0.0` | `2026.1` | No | No | historical baseline |
| `v1.1.0-fmeflow-2026.3-baseline` | `2026.3` | No | No | planned / tag when committed |
| `v1.2.0-fmeflow-2026.3-cloudflare` | `2026.3` | Yes | No | planned / tag when committed |
| `v1.3.0-fmeflow-2026.3-license-switch-no-cloudflare` | `2026.3` | No | Yes | prototype / not yet deployed |
| `v1.3.1-fmeflow-2026.3-license-switch-cloudflare` | `2026.3` | Yes | Yes | prototype / not yet deployed |

## Important current status

At the time of writing:

- the repository contains local changes that are not yet committed or pushed
- the current deployed AKS state and the git remote state are not yet aligned under a new release tag
- do not create any of the new tags until the working tree is committed and pushed