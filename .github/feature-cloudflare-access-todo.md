# Cloudflare access TODO

## Goal
Enable secure access to the Azure-hosted FME Flow web UI through a free Cloudflare tunnel solution without disrupting the existing on-prem remote engine reverse-tunnel architecture.

## Access options
1. Option 1: Run `cloudflared` as a companion workload in the same AKS environment as FME Flow.
   - Selected for this test environment.
   - Lowest cost and fastest to test.
   - Acceptable because this is for internal testing only.
   - Trade-off: less isolation than a dedicated tunnel host.
2. Option 2: Run `cloudflared` on a separate Azure VM or dedicated tunnel host.
   - Better separation of responsibilities and cleaner production posture.
   - More robust if the FME Flow host changes or if we want stricter operational isolation.
   - Trade-off: additional Azure cost and more infrastructure to maintain.

## Required steps
1. Run `cloudflared` as a small companion deployment in AKS, keeping the setup simple and low-cost.
2. Use Cloudflare Quick Tunnel mode instead of a named tunnel.
3. Point the Quick Tunnel at the in-cluster FME Flow web service.
4. Read the generated `trycloudflare.com` hostname from the connector logs.
5. Verify that the browser reaches the FME Flow login page through that hostname rather than the raw Azure IP.
6. Keep the existing on-prem reverse tunnel for FME Remote Engine Services unchanged.
7. Validate that no direct public-IP access is required for the primary web access path.
8. Document the resulting temporary access model and any company firewall or Netskope exceptions.

## Exact implementation choices

- Tunnel type: Quick Tunnel
- No Cloudflare-owned zone required
- No tunnel token required
- No `Published application` route required
- Run the connector with [k8s/cloudflared-deployment.yaml](k8s/cloudflared-deployment.yaml)
- Origin for the current live Helm-based deployment: `http://fmeflowweb.default.svc.cluster.local:8080`
- Resulting public hostname: temporary `https://<random>.trycloudflare.com`

Do not choose a private-network or CIDR route for this branch. This branch is for temporary hostname-based web access only.

## Notes
- This branch is for the access-path work only.
- Do not remove or overwrite the existing on-prem remote-engine setup.
- For this internal test environment, we are choosing Option 1 (in-cluster `cloudflared`) to avoid extra Azure server cost.
- The free Quick Tunnel hostname is temporary and can change whenever the connector pod restarts.
- Use the hostname-based path to reduce corporate network issues with bare Azure public IP access.
- Verified on-prem reverse SSH command for the current environment: `ssh.exe -N -i id_ed25519 -R 0.0.0.0:9090:127.0.0.1:8080 tunnel@4.165.180.65`
