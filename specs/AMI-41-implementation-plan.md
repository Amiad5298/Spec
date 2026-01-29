# Implementation Plan: AMI-41 - Create Platform Configuration Guide

**Ticket:** [AMI-41](https://linear.app/amiadspec/issue/AMI-41/create-platform-configuration-guide)
**Status:** In Progress
**Date:** 2026-01-28

---

## Summary

This ticket creates comprehensive documentation for configuring credentials and settings for each of the 6 supported ticket platforms. The goal is to provide users with a clear, user-friendly guide explaining:

1. **Two authentication modes** - Auggie MCP integration (primary) vs fallback credentials (direct API)
2. **Platform-specific setup** - Where to obtain API keys/tokens for each platform
3. **Configuration file setup** - How to configure credentials securely using environment variables
4. **Troubleshooting** - Common credential issues and their solutions

**Why This Matters:**
- Azure DevOps, Monday, and Trello **require** fallback credentials (no Auggie MCP integration)
- Jira, Linear, and GitHub can optionally use fallback credentials as a backup
- Credential configuration errors are a common source of user frustration
- Without guidance, users may misconfigure platforms and assume the feature is broken

**Target File:** `docs/platform-configuration.md`

**Current State:** A comprehensive guide already exists in `docs/platform-configuration.md` (702 lines) that covers all acceptance criteria. This plan validates the existing content against requirements.

---

## Technical Approach

### Documentation Strategy

The guide follows a logical structure that helps users understand:

1. **When credentials are needed** - Understanding the two authentication modes
2. **What credentials are required** - Platform-specific requirements (canonical keys from AMI-22/AMI-31)
3. **Where to get credentials** - Step-by-step for each platform's API portal
4. **How to configure them** - Config file examples with environment variable best practices
5. **How to verify** - Testing the configuration works

### Architecture Reference

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION MODES                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY: Auggie MCP Integration                                                │
│  • Platforms: Jira, Linear, GitHub                                             │
│  • Authentication handled by Auggie agent configuration                         │
│  • User sets up credentials in Auggie, not SPEC                                │
│  • No configuration needed in SPEC (works out of the box)                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  FALLBACK: Direct API Access                                                    │
│  • Platforms: ALL 6 (Azure DevOps, Monday, Trello REQUIRE this)                │
│  • Authentication via FALLBACK_* config keys                                    │
│  • Uses AuthenticationManager (AMI-22) for credential retrieval                 │
│  • Uses DirectAPIFetcher (AMI-31) for HTTP requests                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Credential Requirements Summary

| Platform | Auggie MCP | Credential Keys | Required Fields |
|----------|------------|-----------------|-----------------|
| **Jira** | ✅ Primary | `FALLBACK_JIRA_*` | `url`, `email`, `token` |
| **Linear** | ✅ Primary | `FALLBACK_LINEAR_*` | `api_key` |
| **GitHub** | ✅ Primary | `FALLBACK_GITHUB_*` | `token` |
| **Azure DevOps** | ❌ | `FALLBACK_AZURE_DEVOPS_*` | `organization`, `pat` |
| **Monday** | ❌ | `FALLBACK_MONDAY_*` | `api_key` |
| **Trello** | ❌ | `FALLBACK_TRELLO_*` | `api_key`, `token` |

---

## File Requiring Changes

### `docs/platform-configuration.md`

**Change Type:** Validation and minor updates (content already exists)

**Current Content (702 lines):**
The file already contains comprehensive documentation including:
- Overview with two authentication modes explained (Lines 1-41)
- Quick Reference Table (Lines 43-52)
- Credential Key Aliases section (Lines 56-68)
- Configuration File Locations & Precedence (Lines 71-120)
- Default Platform configuration (Lines 123-156)
- Platforms with Auggie Integration: Jira, Linear, GitHub (Lines 159-300)
- Platforms Requiring Fallback Credentials: Azure DevOps, Monday, Trello (Lines 303-452)
- Complete Configuration Example (Lines 455-503)
- Security Best Practices (Lines 507-582)
- Verifying Configuration (Lines 585-618)
- Troubleshooting section (Lines 620-702)

**Required Actions:**
1. Validate all content against acceptance criteria
2. Verify credential keys match `PLATFORM_REQUIRED_CREDENTIALS` in `spec/config/fetch_config.py`
3. Verify credential aliases match `CREDENTIAL_ALIASES` in `spec/config/fetch_config.py`
4. Ensure all external links are valid
5. Test configuration examples for correctness

---

## Implementation Steps

### Phase 1: Validate Against Acceptance Criteria

#### Step 1.1: Verify AC1 - Two Authentication Modes Documented
**Status:** ✅ Complete
- Lines 16-39: "Two Authentication Modes" and "How Authentication Works" sections

#### Step 1.2: Verify AC2 - All 6 Platforms Have Dedicated Sections
**Status:** ✅ Complete
- Jira: Lines 163-206
- Linear: Lines 209-249
- GitHub: Lines 252-300
- Azure DevOps: Lines 307-354
- Monday: Lines 357-397
- Trello: Lines 400-452

#### Step 1.3: Verify AC3 - Required Credentials Listed
**Status:** ✅ Complete
- Quick Reference Table: Lines 43-52
- Each platform section includes credential table

#### Step 1.4: Verify AC4 - Step-by-Step for Fallback Platforms
**Status:** ✅ Complete
- Azure DevOps: "Getting a Personal Access Token (PAT)" (Lines 326-341)
- Monday: "Getting an API Token" (Lines 376-385)
- Trello: "Getting Credentials (Two-Step Process)" (Lines 419-439)

#### Step 1.5: Verify AC5 - Default Platform Configuration
**Status:** ✅ Complete
- "Setting Default Platform" section: Lines 123-156

#### Step 1.6: Verify AC6 - Error Messages Documented
**Status:** ✅ Complete
- "Common Errors" table: Lines 623-633
- "Debugging Tips": Lines 635-652

#### Step 1.7: Verify AC7 - Security Best Practices
**Status:** ✅ Complete
- "Security Best Practices" section: Lines 507-582
- Environment variable syntax, token rotation, scoping tokens

### Phase 2: Validate Technical Accuracy

#### Step 2.1: Cross-Reference Credential Keys with Implementation

Verify credential keys in documentation match `spec/config/fetch_config.py`:

| Platform | Doc Keys | Implementation (`PLATFORM_REQUIRED_CREDENTIALS`) | Match |
|----------|----------|--------------------------------------------------|-------|
| Jira | `url`, `email`, `token` | `{"url", "email", "token"}` | ✅ |
| Linear | `api_key` | `{"api_key"}` | ✅ |
| GitHub | `token` | `{"token"}` | ✅ |
| Azure DevOps | `organization`, `pat` | `{"organization", "pat"}` | ✅ |
| Monday | `api_key` | `{"api_key"}` | ✅ |
| Trello | `api_key`, `token` | `{"api_key", "token"}` | ✅ |

#### Step 2.2: Verify Credential Aliases

Cross-reference with `CREDENTIAL_ALIASES` in `spec/config/fetch_config.py`:

| Platform | Documented Aliases | Implementation | Match |
|----------|-------------------|----------------|-------|
| Azure DevOps | `org` → `organization`, `token` → `pat` | `{"org": "organization", "token": "pat"}` | ✅ |
| Jira | `base_url` → `url` | `{"base_url": "url"}` | ✅ |
| Trello | `api_token` → `token` | `{"api_token": "token"}` | ✅ |

### Phase 3: Validate External Links

#### Step 3.1: Verify All Platform Documentation Links

| Platform | Link | Purpose | Status |
|----------|------|---------|--------|
| Jira | https://id.atlassian.com/manage-profile/security/api-tokens | API token creation | 🔍 Verify |
| Jira | https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/ | REST API docs | 🔍 Verify |
| Linear | https://linear.app/settings/api | Personal API keys | 🔍 Verify |
| Linear | https://developers.linear.app/docs/graphql/working-with-the-graphql-api | GraphQL API docs | 🔍 Verify |
| GitHub | https://github.com/settings/tokens | Personal access tokens | 🔍 Verify |
| GitHub | https://docs.github.com/en/rest/issues | REST API docs | 🔍 Verify |
| Azure DevOps | https://dev.azure.com/ | PAT creation portal | 🔍 Verify |
| Azure DevOps | https://learn.microsoft.com/en-us/rest/api/azure/devops/ | REST API docs | 🔍 Verify |
| Monday | https://developer.monday.com/api-reference/docs | API docs | 🔍 Verify |
| Trello | https://trello.com/power-ups/admin | API key portal | 🔍 Verify |
| Trello | https://developer.atlassian.com/cloud/trello/ | REST API docs | 🔍 Verify |

### Phase 4: Test Configuration Examples

#### Step 4.1: Validate Configuration File Syntax

Ensure the complete configuration example (Lines 455-503) is syntactically correct:
- All `FALLBACK_*` keys follow the correct naming convention
- Environment variable references use `${VAR_NAME}` syntax
- Comments explain each section

---

## Acceptance Criteria

From the Linear ticket (with validation status):

- [x] **AC1:** Documentation explains the two authentication modes (agent integration vs. fallback credentials)
- [x] **AC2:** Each of the 6 platforms has a dedicated setup section
- [x] **AC3:** Required credentials for each platform are clearly listed
- [x] **AC4:** Step-by-step instructions for platforms requiring fallback credentials (Azure DevOps, Monday, Trello)
- [x] **AC5:** Instructions for setting `default_platform` configuration
- [x] **AC6:** Common error messages and their solutions are documented
- [x] **AC7:** Security best practices for credential storage are mentioned (e.g., use environment variables)

### Additional Criteria (Best Practices)

- [x] **AC8:** Links to official platform API documentation are included
- [x] **AC9:** Configuration file examples are complete
- [x] **AC10:** Credential key aliases are documented
- [x] **AC11:** Environment variable expansion syntax is explained (`${VAR_NAME}`)
- [x] **AC12:** Verification instructions using `spec --config` are included
- [x] **AC13:** Required API scopes/permissions are documented per platform

---

## Testing/Validation Strategy

### Content Validation Checklist

```bash
# 1. Verify credential keys match implementation
grep -E "PLATFORM_REQUIRED_CREDENTIALS" spec/config/fetch_config.py

# Expected output should match documentation:
# jira: url, email, token
# linear: api_key
# github: token
# azure_devops: organization, pat
# trello: api_key, token
# monday: api_key

# 2. Verify credential aliases
grep -E "CREDENTIAL_ALIASES" spec/config/fetch_config.py

# Expected: azure_devops: org→organization, token→pat
#           jira: base_url→url
#           trello: api_token→token

# 3. Test spec --config command works
spec --config

# 4. Verify markdown renders correctly
# Open docs/platform-configuration.md in GitHub or markdown viewer
```

### Link Validation

Manually verify each external link is accessible and points to the correct page.

### User Experience Validation

1. **Completeness check** - Follow the guide for at least one platform to verify steps work
2. **Error message validation** - Intentionally misconfigure to verify error messages match troubleshooting section
3. **Cross-reference** - Ensure README.md links to this guide correctly

---

## Dependencies

### Upstream Dependencies

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| AMI-22 | AuthenticationManager | ✅ Complete | Defines canonical credential keys per platform |
| AMI-25 | CLI Migration | ✅ Complete | Platform-agnostic CLI with `--platform` flag |
| AMI-31 | DirectAPIFetcher | ✅ Complete | Uses credentials for direct API access |
| AMI-33 | Fetch Config | ✅ Complete | Configuration schema and validation |
| AMI-38 | README Update | ✅ Complete | Links to this guide |
| AMI-39 | Platform Config Guide (Original) | ✅ Complete | Initial implementation |

### Related Tickets

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-38](https://linear.app/amiadspec/issue/AMI-38) | Update README for Multi-Platform | Links to this guide |
| [AMI-39](https://linear.app/amiadspec/issue/AMI-39) | Create Platform Configuration Guide | Original ticket (duplicate) |
| [AMI-42](https://linear.app/amiadspec/issue/AMI-42) | Update spec --config Output | Shows configuration status |
| [AMI-43](https://linear.app/amiadspec/issue/AMI-43) | Audit User-Facing Strings | Error messages referenced here |

---

## Estimated Effort

| Phase | Description | Estimate |
|-------|-------------|----------|
| Phase 1 | Validate against acceptance criteria | 0.25 day |
| Phase 2 | Cross-reference with implementation | 0.25 day |
| Phase 3 | Validate external links | 0.25 day |
| Phase 4 | Test configuration examples | 0.25 day |
| **Total** | | **~1 day** |

**Note:** Since the documentation content already exists and appears complete, the effort is primarily validation rather than creation.

---

## Before/After Examples

### Before (Original Placeholder - Now Replaced)

```markdown
# Platform Configuration Guide

> **TODO:** This is a placeholder document. Fill in configuration steps for each platform.

## Platforms Requiring Fallback Credentials

### Azure DevOps

TODO: Document credential setup steps for Azure DevOps.
```

### After (Current State)

```markdown
# Platform Configuration Guide

> Complete documentation for configuring credentials for SPEC's 6 supported ticket platforms.

## Overview

SPEC supports fetching tickets from 6 platforms:

- **Jira** – Atlassian's issue tracking system
- **Linear** – Modern project management for software teams
- **GitHub Issues** – GitHub's built-in issue tracker
- **Azure DevOps** – Microsoft's DevOps platform (Work Items)
- **Monday.com** – Work management platform
- **Trello** – Kanban-style project boards

### Two Authentication Modes

SPEC uses two authentication modes to fetch tickets:

1. **Auggie MCP Integration (Primary)**
   - Platforms: Jira, Linear, GitHub
   - Authentication is handled by Auggie's built-in integrations
   - No configuration needed in SPEC—works out of the box

2. **Fallback Credentials (Direct API)**
   - Platforms: **All 6** (Azure DevOps, Monday, Trello **require** this)
   - Authentication via `FALLBACK_*` configuration keys
   - Credentials stored in `~/.spec-config` or `.spec` file
```

---

## Usage Examples

### Verifying Configuration

```bash
# Check which platforms are configured
spec --config

# Expected output shows:
# - Default platform setting
# - Agent integration status per platform
# - Fallback credential status (configured/not configured)
```

### Testing Platform Access

```bash
# Test Jira (with Auggie integration)
spec PROJ-123

# Test Linear (with explicit platform)
spec --platform linear ABC-123

# Test GitHub
spec --platform github owner/repo#42

# Test Azure DevOps (requires fallback credentials)
spec --platform azure_devops https://dev.azure.com/org/project/_workitems/edit/123

# Test Monday (requires fallback credentials)
spec https://mycompany.monday.com/boards/123456/pulses/789

# Test Trello (requires fallback credentials)
spec https://trello.com/c/aBcDeFgH/123-card-title
```

### Common Configuration Issues

```bash
# Issue: "No fallback credentials configured for platform 'azure_devops'"
# Solution: Add to ~/.spec-config:
FALLBACK_AZURE_DEVOPS_ORGANIZATION=myorg
FALLBACK_AZURE_DEVOPS_PAT=${AZURE_DEVOPS_PAT}

# Issue: "Credential field 'X' contains unexpanded environment variable"
# Solution: Set the environment variable:
export AZURE_DEVOPS_PAT="your-pat-here"
source ~/.zshrc  # or ~/.bashrc
```

---

## External Links Reference

| Platform | Link | Purpose |
|----------|------|---------|
| Jira | https://id.atlassian.com/manage-profile/security/api-tokens | API token creation |
| Jira | https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/ | REST API docs |
| Linear | https://linear.app/settings/api | Personal API keys |
| Linear | https://developers.linear.app/docs/graphql/working-with-the-graphql-api | GraphQL API docs |
| GitHub | https://github.com/settings/tokens | Personal access tokens |
| GitHub | https://docs.github.com/en/rest/issues | REST API docs |
| Azure DevOps | https://dev.azure.com/ (User settings → Personal access tokens) | PAT creation |
| Azure DevOps | https://learn.microsoft.com/en-us/rest/api/azure/devops/ | REST API docs |
| Monday | https://developer.monday.com/api-reference/docs | API docs |
| Trello | https://trello.com/power-ups/admin | API key |
| Trello | https://developer.atlassian.com/cloud/trello/ | REST API docs |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-28 | AI Assistant | Initial draft created (validation of existing documentation) |
