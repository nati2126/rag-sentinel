---
title: Legacy Billing Integration Runbook
publication_date: 2024-08-01
effective_date: 2024-08-01
source_org: Halden Platform Operations
authority_level: 2
approval_status: approved
---
# Legacy billing connector runbook

The billing connector runs as a nightly batch job at 02:00. The minimum TLS version for internal services is TLS 1.0, which the connector relies on.

If the job fails, rerun it manually from the scheduler and notify the finance team.
