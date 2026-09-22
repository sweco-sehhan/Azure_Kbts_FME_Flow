# FME Flow Hybrid Architecture (Simple)

```mermaid
flowchart LR
  subgraph EXT["Internet / External Access"]
    U["User / API Client"]
    IP443["Public IP 443"]
    IP22["Public IP 22"]
  end

  subgraph AZ["Azure"]
    ALB["Azure Load Balancer"]
    NP443["NodePort HTTPS path\n(number not explicit in manifests)"]
    NP22["NodePort SSH path\n(number not explicit in manifests) (verify)"]

    subgraph AKS["AKS Cluster"]
      NGINX["NGINX Ingress"]
      SSHP["SSH proxy\n(port 22 verify)"]
      TUN["onprem-tunnel (ClusterIP)"]
      CORE["FME Flow core-0\n(core/web/fmeutility)"]
      ENGAKS["engine-standard"]
      EREG["engineregistration:7070"]
      WS["fmeflowwebsocket:7078"]
    end
  end

  subgraph ONP["On-prem Network"]
    RE["Remote Engine\n(not an AKS pod)"]
    ARC["ArcGIS Enterprise"]
  end

  %% Web/API
  U -->|"443"| IP443 --> ALB --> NP443 --> NGINX -->|"fmeflowweb:8080"| CORE

  %% Reverse tunnel
  RE -.->|"outbound SSH 22 (verify)"| IP22 -.->|"22 (verify)"| ALB -.-> NP22 -.-> SSHP -.-> TUN -.->|"engineregistration:7070"| CORE

  %% Execution split
  CORE -->|"some jobs"| ENGAKS
  CORE --> EREG
  CORE --> WS
  CORE -.->|"ArcGIS-near jobs via tunnel"| TUN -.-> RE --> ARC
```

Kort notering:
- Kontrollplan: FME Flow i AKS.
- Exekvering: antingen engine-standard i AKS eller on-prem Remote Engine.
- Faktiska FME-portar från projektet: 443 (extern), 8080 (fmeflowweb), 7070 (engineregistration), 7078 (websocket).
- Reverse SSH-tunneln möjliggör säker koppling till on-prem utan att Remote Engine blir en Kubernetes-pod.
