# Security advisories live study

This category contains 10 reviewed candidates. 8 are
currently eligible for the two-cycle qualification. A later 24-hour study is
configured separately and is not started by the qualification command.

| Website | Stable ID | Current status | Qualification URL |
|---|---|---|---|
| CISA Cybersecurity Advisories | `security-cisa` | excluded after pilot | https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-293a |
| Apple Security Releases | `security-apple` | eligible for qualification | https://support.apple.com/en-us/102657 |
| Ubuntu Security Notices | `security-ubuntu` | eligible for qualification | https://ubuntu.com/security/notices/USN-8957-1 |
| Chrome Releases | `security-chrome-releases` | eligible for qualification | https://chromereleases.googleblog.com/2026/10/chrome-for-android-update_0160078013.html |
| Mozilla Security Advisories | `security-mozilla` | eligible for qualification | https://www.mozilla.org/en-US/security/advisories/mfsa2026-122/ |
| Oracle Security Alerts | `security-oracle` | eligible for qualification | https://www.oracle.com/security-alerts/alert-cve-2026-109618.html |
| GitHub Security Advisories | `security-github` | eligible for qualification | https://github.com/advisories/GHSA-m65p-9j7q-6w33 |
| GitLab Releases | `security-gitlab` | eligible for qualification | https://docs.gitlab.com/releases/19/ |
| Palo Alto Networks Security Advisories | `security-palo-alto` | excluded after pilot | https://security.paloaltonetworks.com/CVE-2026-111497 |
| Node.js Security Releases | `security-nodejs` | eligible for qualification | https://nodejs.org/en/blog/vulnerability/october-2026-security-releases |

Exact hosts, discovery limits, template mappings, and exclusion reasons are in
[`input/sites.json`](input/sites.json). Completed evidence appears under
`runs/`; an empty `runs/` folder means that no public run has been released.
