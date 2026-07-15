# K8s manifests for V4+ (Model Serving + Auto-scaling)
#
# Structure:
#   base/        — shared resources (Namespace, ServiceAccount, etc.)
#   overlays/    — environment-specific patches
#     dev/       — dev overlay (minimal replicas, debug)
#     prod/      — prod overlay (HA, HPA, PDB)
#
# Phase-in plan:
#   1. backend-deployment.yaml + backend-service.yaml
#   2. ConfigMap for env vars
#   3. HPA based on custom metrics (prometheus-adapter)
#   4. PDB for HA
