---
title: NIST SP 800-63B Memorized Secret Guidance (summary)
version: "2017"
publication_date: 2017-06-22
effective_date: 2017-06-22
source_org: NIST (public-derived summary)
authority_level: 4
approval_status: approved
---
# NIST SP 800-63B (2017): memorized secrets - summary

This is a paraphrased summary prepared for the VersionConflict benchmark; consult NIST SP 800-63B for the authoritative text. It is external federal guidance, not a Halden Systems policy.

* Memorized secrets chosen by subscribers must be at least 8 characters long.
* Verifiers should permit passwords of at least 64 characters.
* Verifiers should not impose composition rules such as requiring mixtures of character types.
* Verifiers should not require periodic password changes; a change should be forced when there is evidence of compromise.
* New passwords should be checked against lists of commonly used, expected or compromised values.
* Verifiers must limit failed authentication attempts to no more than 100 consecutive failures on an account.
