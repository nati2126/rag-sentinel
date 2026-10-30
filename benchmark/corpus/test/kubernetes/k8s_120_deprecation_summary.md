---
title: Kubernetes v1.20 - dockershim deprecation (summary)
version: "1.20"
publication_date: 2020-12-08
effective_date: 2020-12-08
source_org: Kubernetes project (public-derived summary)
authority_level: 4
approval_status: approved
---
# Kubernetes v1.20: dockershim deprecated - summary

This is a paraphrased summary prepared for the VersionConflict benchmark; consult the Kubernetes release notes for the authoritative text.

Kubernetes v1.20, released in December 2020, deprecated dockershim, the component that let the kubelet use Docker Engine as a container runtime. Clusters were advised to move to a CRI-compatible runtime such as containerd or CRI-O.
