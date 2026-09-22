# FME Flow Hybrid Architecture (Detailed)

```mermaid
flowchart LR
  %% --------------------------
  %% External / Internet
  %% --------------------------
  subgraph EXT["Internet / External Access"]
    USER["User / API Client"]
    PIP443["Public IP (Web)\nTCP 443"]
    PIP22["Public IP (SSH Tunnel)\nTCP 22"]
  end

  %% --------------------------
  %% Azure
  %% --------------------------
  subgraph AZ["Azure"]
    subgraph VNET["VNet"]
      subgraph AKSSN["AKS Subnet"]
        ALB["Azure Load Balancer"]
        NP443["NodePort (HTTPS)\nnot explicitly set in manifests (verify)"]
        NP22["NodePort (SSH Proxy)\nnot explicitly set in manifests (verify)"]

        subgraph AKSC["AKS Cluster"]
          NGINX["NGINX Ingress Controller"]
          SSHPROXY["SSH Proxy in AKS\nport 22 not defined in manifests (verify)"]
          TUNNEL["onprem-tunnel\nService: ClusterIP"]

          subgraph FMEAKS["FME Flow in AKS"]
            CORE0["core-0\ncontainers: core | web | fmeutility"]
            DB0["database-0"]
            Q0["queue-0"]
            WS0["websocket-0"]
            ENGSTD["engine-standard\n(AKS engine pod)"]
          end

          CTRL["Control Plane\n(FME Flow in AKS)"]
          EXEC["Execution Decision\nAKS engine or on-prem engine"]
        end
      end
    end
  end

  %% --------------------------
  %% On-prem
  %% --------------------------
  subgraph ONP["On-prem Network"]
    ONP_HOST["On-prem server"]
    REMOTE["FME Flow Remote Engine\n(not an AKS pod)"]
    L8080["Local port 8080\n(if used) (verify)"]
  end

  subgraph ARC["ArcGIS Enterprise on-prem"]
    ARCGIS["ArcGIS Enterprise"]
  end

  %% --------------------------
  %% Flow A: Normal web/API traffic (solid)
  %% --------------------------
  USER -->|"HTTPS 443"| PIP443
  PIP443 -->|"443"| ALB
  ALB -->|"NodePort path (443)"| NP443
  NP443 -->|"to ingress"| NGINX
  NGINX -->|"to fmeflowweb:8080"| CORE0

  %% --------------------------
  %% Flow B: Reverse tunnel traffic (dashed)
  %% --------------------------
  REMOTE -.->|"Outbound SSH 22 (verify)"| PIP22
  PIP22 -.->|"22 (verify)"| ALB
  ALB -.->|"NodePort path (22 verify)"| NP22
  NP22 -.->|"to SSH proxy"| SSHPROXY
  SSHPROXY -.->|"internal tunnel endpoint"| TUNNEL
  TUNNEL -.->|"tunnel route to engineregistration:7070"| CORE0

  %% --------------------------
  %% Internal FME Flow communication
  %% --------------------------
  CORE0 -->|"internal 5432"| DB0
  CORE0 -->|"internal 6379"| Q0
  CORE0 -->|"internal 7078"| WS0
  CORE0 -->|"dispatch"| CTRL
  CTRL -->|"job control"| EXEC
  EXEC -->|"execute in AKS"| ENGSTD
  EXEC -.->|"execute via tunnel"| TUNNEL
  TUNNEL -.->|"to on-prem engine"| REMOTE

  %% --------------------------
  %% On-prem proximity and local integrations
  %% --------------------------
  ONP_HOST --- REMOTE
  REMOTE -->|"local/near access"| ARCGIS
  REMOTE -->|"localhost:8080 (verify)"| L8080

  %% --------------------------
  %% Visual styles
  %% --------------------------
  classDef azureNode fill:#eef6ff,stroke:#2563eb,stroke-width:1.2px,color:#0b2447;
  classDef fmeNode fill:#ecfdf3,stroke:#16a34a,stroke-width:1.2px,color:#0f3d20;
  classDef onpremNode fill:#f3f4f6,stroke:#6b7280,stroke-width:1.2px,color:#1f2937;
  classDef controlNode fill:#fff7ed,stroke:#f59e0b,stroke-width:1.2px,color:#7c2d12;

  class PIP443,PIP22,ALB,NP443,NP22,NGINX,SSHPROXY,TUNNEL azureNode;
  class CORE0,DB0,Q0,WS0,ENGSTD fmeNode;
  class ONP_HOST,REMOTE,L8080,ARCGIS onpremNode;
  class CTRL,EXEC controlNode;

  %% Link coloring
  %% 0-4   : web/API path (blue)
  %% 5-10  : reverse tunnel path (orange, dashed)
  %% 11-17 : internal/service orchestration (green)
  %% 18-20 : on-prem/local adjacency (gray)
  linkStyle 0,1,2,3,4 stroke:#2563eb,stroke-width:2px,color:#1e40af;
  linkStyle 5,6,7,8,9,10 stroke:#f59e0b,stroke-width:2px,stroke-dasharray:6 4,color:#92400e;
  linkStyle 11,12,13,14,15,16,17 stroke:#16a34a,stroke-width:2px,color:#166534;
  linkStyle 18,19,20 stroke:#6b7280,stroke-width:1.8px,color:#374151;

  %% --------------------------
  %% Legend
  %% --------------------------
  subgraph LEGEND["Legend / Notering"]
    L1["Blå linje = webb/API-trafik"]
    L2["Orange streckad linje = reverse SSH tunnel"]
    L3["Grön linje = intern FME Flow-kommunikation"]
    L4["Grå noder/linjer = on-prem infrastruktur"]
  end
```

## Architecture summary

FME Flow kontrollplan körs i AKS i Azure, där core, database, queue, websocket och en standard engine hanteras i Kubernetes. Vanlig användar- och API-trafik går via Public IP på port 443 till Azure Load Balancer, vidare till NodePort (nummer ej explicit i manifest) och NGINX Ingress innan den når tjänsten fmeflowweb på port 8080 i AKS.

En on-prem FME Flow Remote Engine etablerar en utgående reverse SSH-anslutning mot Azure (port 22 är märkt verify eftersom den inte finns explicit i manifest). Trafiken går via Azure Load Balancer och NodePort till en SSH-proxy i AKS, och exponeras internt via Kubernetes-tjänsten onprem-tunnel (ClusterIP). Därmed kan FME Flow i AKS styra jobb som exekveras på on-prem Remote Engine, logiskt mot engineregistration på port 7070.

## Primary traffic paths

1. Web/API path: User/API Client -> Public IP:443 -> Azure Load Balancer -> NodePort (nummer ej explicit) -> NGINX Ingress -> fmeflowweb:8080 -> core-0 (web/core).
2. Reverse tunnel path: On-prem Remote Engine -> outbound SSH:22 (verify) -> Public IP:22 (verify) -> Azure Load Balancer -> NodePort (22 verify) -> SSH proxy -> onprem-tunnel (ClusterIP) -> FME Flow control path via engineregistration:7070.
3. On-prem execution path: FME Flow dispatchar utvalda jobb via tunneln till Remote Engine, som kör ArcGIS-nära arbetsflöden lokalt i on-prem-miljön.

## Key design decisions

- Tydlig separation mellan kontrollplan (FME Flow i AKS) och exekveringsplan (AKS engine eller on-prem Remote Engine).
- Remote Engine körs uttryckligen utanför Kubernetes och är inte en AKS-pod.
- Reverse SSH används för att möjliggöra säker utgående anslutning från on-prem utan att exponera on-prem tjänster direkt mot internet.
- onprem-tunnel som intern ClusterIP-tjänst håller tunnelvägen intern i klustret; FME-relaterad tunnelväg är kopplad mot engineregistration (7070).
- ArcGIS-relaterade jobb kan köras nära ArcGIS Enterprise on-prem för låg latens och enklare åtkomst till lokala resurser.
- Osäkra implementationdetaljer är markerade med (verify) för teknisk validering innan produktionssättning.
