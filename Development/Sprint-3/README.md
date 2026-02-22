# Sprint 3 - ContinuumAI

## Overview

Sprint 3 focused on enhancing the ContinuumAI platform with intelligent features, performance improvements, and production-ready deployment infrastructure.

---

## Key Features Added

### Chatbot Functionality
- Integrated AI-powered chatbot for natural language interactions
- Users can query data and get insights conversationally

### Strategy Layer
- Added strategic analysis capabilities
- Business intelligence recommendations based on data patterns

### Redis Integration
- Implemented Redis for caching and session management
- Improved response times and reduced database load

---

## Infrastructure & DevOps

### CI/CD Pipeline
- **Continuous Integration (CI):** Automated Docker image builds on push to main/Sprint3_Final
- **Continuous Deployment (CD):** Automated deployment to Oracle Kubernetes Engine (OKE)
- Images hosted on GitHub Container Registry (GHCR)

### Kubernetes Deployment
- Backend and Frontend deployed as separate services
- NGINX Ingress Controller for routing
- Secrets management for sensitive configuration

---

## Project Structure

```
Sprint-3/
├── code/
│   ├── backend/          # FastAPI backend service
│   └── frontend/         # Next.js frontend application
├── k8s/                  # Kubernetes manifests
├── misc/                 # Documentation and scripts
└── .github/workflows/    # CI/CD pipelines (at repo root)
```

---

## Running Locally

See [code/docker_guide.txt](code/docker_guide.txt) for Docker setup instructions.

---

## Team

ContinuumAI - P13
