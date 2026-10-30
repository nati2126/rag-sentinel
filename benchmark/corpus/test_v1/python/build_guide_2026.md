---
title: Engineering Build Guide
family: build-guide
version: "2026"
publication_date: 2026-01-05
effective_date: 2026-01-10
source_org: Halden Engineering
authority_level: 3
approval_status: approved
supersedes: build_guide_2022.md
---
# Engineering Build Guide (2026)

The supported runtime for backend services is Python 3.12. Packaging uses setuptools with pyproject.toml; distutils is not available in Python 3.12.

All services are built in CI on every merge to the main branch. Build artefacts are kept for 30 days.
