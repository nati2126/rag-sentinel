---
title: Kubernetes v1.24 - dockershim removal (summary)
version: "1.24"
publication_date: 2022-05-03
effective_date: 2022-05-03
source_org: Kubernetes project (public-derived summary)
authority_level: 4
approval_status: approved
---
# Kubernetes v1.24: dockershim removed - summary

This is a paraphrased summary prepared for the VersionConflict benchmark; consult the Kubernetes release notes for the authoritative text.

Kubernetes v1.24, released in May 2022, removed dockershim from the kubelet. From v1.24 onwards, Docker Engine cannot be used directly as the container runtime; nodes must use a CRI-compatible runtime such as containerd or CRI-O.
