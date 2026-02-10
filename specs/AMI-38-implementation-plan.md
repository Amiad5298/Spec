# Implementation Plan: AMI-38 - Update User Documentation for Multi-Platform Support

**Ticket:** [AMI-38](https://linear.app/amiadingot/issue/AMI-38/update-user-documentation-for-multi-platform-support)
**Status:** Draft
**Date:** 2026-01-28

---

## Summary

After AMI-25 (CLI migration to platform-agnostic providers), SPEC now supports **6 ticket platforms**: Jira, Linear, GitHub, Azure DevOps, Monday, and Trello. However, the current documentation (primarily `README.md`) still references Jira as the only supported platform. This creates a discoverability problem—users won't know about the multi-platform capability.

**Why This Matters:**
- New users may assume SPEC is Jira-only and not adopt it
- Existing users won't discover how to use other platforms
- The `--platform` flag and `default_platform` configuration are undocumented in README
- Usage examples are all Jira-specific

**Key Changes:**
- Transform Jira-specific language to platform-agnostic
- Add multi-platform usage examples
- Document the `--platform` CLI flag
- Create a "Supported Platforms" section
- Update workflow diagrams to show generic "ticket" instead of "Jira ticket"

**Scope:**
- `README.md` - Main user documentation
- CLI help text examples in documentation (actual CLI help text was updated in AMI-25)

**Out of Scope (handled by separate tickets):**
- Platform Configuration Guide → [AMI-39](https://linear.app/amiadingot/issue/AMI-39)
- `spec --config` output updates → [AMI-42](https://linear.app/amiadingot/issue/AMI-42)
- User-facing string audit → [AMI-43](https://linear.app/amiadingot/issue/AMI-43)

---

## Technical Approach

### Documentation Audit Strategy

The approach is to systematically identify and update all Jira-specific content:

1. **Search for "Jira" references** - Find all instances that need platform-agnostic language
2. **Preserve accuracy** - Ensure Jira-specific features remain documented where appropriate
3. **Add multi-platform examples** - Show usage for Linear, GitHub, and other platforms
4. **Maintain consistency** - Use consistent terminology ("ticket" instead of "Jira ticket")

### Architecture Reference

The system now uses a hybrid fetching approach:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SPEC CLI (Platform-Agnostic)                        │
│  spec <ticket_url_or_id> [--platform jira|linear|github|azure_devops|...]       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          TicketService (Orchestration Layer)                     │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  1. Platform detection (ProviderRegistry)                                │   │
│   │  2. Primary: AuggieMediatedFetcher (Jira, Linear, GitHub)               │   │
│   │  3. Fallback: DirectAPIFetcher (All 6 platforms)                        │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Supported Platforms:**
| Platform | URL Detection | ID Detection | Auggie Integration | Direct API |
|----------|--------------|--------------|-------------------|------------|
| Jira | ✅ | ✅ (PROJECT-123) | ✅ Primary | ✅ Fallback |
| Linear | ✅ | ✅ (ENG-456) | ✅ Primary | ✅ Fallback |
| GitHub | ✅ | ✅ (owner/repo#42) | ✅ Primary | ✅ Fallback |
| Azure DevOps | ✅ | ⚠️ (AB#789) | ❌ | ✅ Only |
| Monday | ✅ | ❌ | ❌ | ✅ Only |
| Trello | ✅ | ❌ | ❌ | ✅ Only |

---

## Files Requiring Changes

### Primary Documentation Files

| File | Change Type | Description |
|------|-------------|-------------|
| `README.md` | **Major Update** | Update all sections for multi-platform support |

### Sections in README.md Requiring Updates

| Section | Current Issue | Required Change |
|---------|--------------|-----------------|
| Header tagline | "Transform Jira tickets" | Platform-agnostic: "Transform tickets from any platform" |
| "What is SPEC?" | "Given a Jira ticket, SPEC:" | "Given a ticket from any supported platform, SPEC:" |
| Features → Deep Integrations | Lists only Jira | Add all 6 platforms |
| Quick Start | `spec PROJECT-123` example | Add examples for multiple platforms |
| How It Works diagram | References "Jira Ticket" | Use "Ticket (Any Platform)" |
| Usage → Basic Commands | Only Jira examples | Add Linear, GitHub examples |
| Command-Line Options | Missing --platform flag | Document -p/--platform option |
| Configuration | `DEFAULT_JIRA_PROJECT` focus | Add `DEFAULT_PLATFORM` setting |
| First Run | "Check Jira integration" | "Check platform integrations" |
| Agent Files | "from Jira tickets" | "from tickets" |
| Troubleshooting | Jira-specific | Add multi-platform troubleshooting |

---

## Implementation Steps

### Phase 1: Update Header and Introduction

#### Step 1.1: Update Header Tagline (Lines 1-9)

**Current:**
```html
<p align="center">
  Transform Jira tickets into implemented features with a structured, AI-assisted three-step workflow.
</p>
```

**New:**
```html
<p align="center">
  Transform tickets from any platform into implemented features with a structured, AI-assisted three-step workflow.
</p>
```

#### Step 1.2: Update "What is SPEC?" Section (Lines 23-31)

**Current:**
```markdown
SPEC is a command-line tool that orchestrates AI agents to implement software features from start to finish. Given a Jira ticket, SPEC:
```

**New:**
```markdown
SPEC is a command-line tool that orchestrates AI agents to implement software features from start to finish. Given a ticket from any supported platform (Jira, Linear, GitHub, Azure DevOps, Monday, or Trello), SPEC:
```

### Phase 2: Add Supported Platforms Section

#### Step 2.1: Create New Section After Features

Add a new "Supported Platforms" section after the Features section:

```markdown
## Supported Platforms

SPEC supports 6 ticket platforms out of the box:

| Platform | URL Support | Ticket ID Support | Notes |
|----------|-------------|-------------------|-------|
| **Jira** | ✅ | ✅ `PROJECT-123` | Full integration via Auggie |
| **Linear** | ✅ | ✅ `ENG-456` | Full integration via Auggie |
| **GitHub Issues** | ✅ | ✅ `owner/repo#42` | Full integration via Auggie |
| **Azure DevOps** | ✅ | ⚠️ `AB#789` | Requires fallback credentials |
| **Monday** | ✅ | ❌ URL only | Requires fallback credentials |
| **Trello** | ✅ | ❌ URL only | Requires fallback credentials |

### Platform Detection

SPEC automatically detects the platform from the ticket URL or ID:

```bash
# URLs are auto-detected
spec https://company.atlassian.net/browse/PROJ-123     # → Jira
spec https://linear.app/team/issue/ENG-456             # → Linear
spec https://github.com/owner/repo/issues/42           # → GitHub
spec https://dev.azure.com/org/project/_workitems/789 # → Azure DevOps

# Ambiguous IDs (PROJECT-123 format) may require --platform flag
spec PROJ-123 --platform jira
spec ENG-456 --platform linear
```
```

### Phase 3: Update Features Section

#### Step 3.1: Update "Deep Integrations" (Lines 50-53)

**Current:**
```markdown
### 🔗 Deep Integrations
- **Jira**: Automatic ticket fetching, context extraction, and branch naming
- **Git**: Feature branch creation, checkpoint commits after each task, optional commit squashing
- **Auggie CLI**: Leverages Auggie's AI capabilities with specialized subagents
```

**New:**
```markdown
### 🔗 Deep Integrations
- **6 Ticket Platforms**: Jira, Linear, GitHub, Azure DevOps, Monday, and Trello
- **Automatic Platform Detection**: URLs and ticket IDs are automatically routed to the correct platform
- **Git**: Feature branch creation, checkpoint commits after each task, optional commit squashing
- **Auggie CLI**: Leverages Auggie's AI capabilities with specialized subagents
```

### Phase 4: Update Quick Start Section

#### Step 4.1: Update Quick Start Examples (Lines 111-124)

**Current:**
```markdown
## Quick Start

```bash
# Install SPEC
pip install spec

# Navigate to your git repository
cd your-project

# Start a workflow with a Jira ticket
spec PROJECT-123
```
```

**New:**
```markdown
## Quick Start

```bash
# Install SPEC
pip install spec

# Navigate to your git repository
cd your-project

# Start a workflow with any ticket
spec https://company.atlassian.net/browse/PROJECT-123  # Jira URL
spec https://linear.app/team/issue/ENG-456              # Linear URL
spec https://github.com/owner/repo/issues/42            # GitHub URL

# Or use a ticket ID with explicit platform
spec PROJECT-123 --platform jira
spec ENG-456 --platform linear
spec owner/repo#42                                       # GitHub (unambiguous)
```
```

### Phase 5: Update "How It Works" Diagram

#### Step 5.1: Update Workflow Diagram (Lines 132-170)

Replace "Jira Ticket" with "Ticket (Any Platform)" in the ASCII diagram:

**Key changes in diagram:**
- Line 137: "Jira Ticket" → "Ticket"
- Line 142: "Fetch ticket details from Jira" → "Fetch ticket details from platform"

### Phase 6: Update Usage Section

#### Step 6.1: Update Basic Commands (Lines 251-268)

**Current:**
```markdown
### Basic Commands

```bash
# Start workflow with a Jira ticket
spec PROJECT-123

# Start with a full Jira URL
spec https://company.atlassian.net/browse/PROJECT-123
```
```

**New:**
```markdown
### Basic Commands

```bash
# Start workflow with a ticket URL (auto-detected platform)
spec https://company.atlassian.net/browse/PROJECT-123     # Jira
spec https://linear.app/team/issue/ENG-456                 # Linear
spec https://github.com/owner/repo/issues/42               # GitHub

# Start with ticket ID (may need --platform for ambiguous IDs)
spec PROJECT-123 --platform jira
spec ENG-456 --platform linear
spec owner/repo#42                                          # GitHub (unambiguous)

# Show interactive main menu
spec

# View current configuration
spec --config
```
```

#### Step 6.2: Add --platform to Command-Line Options (Lines 271-309)

Add after line 275 (`Arguments:` section):

```markdown
Arguments:
  TICKET                      Ticket ID or URL from any supported platform
                              Examples: PROJ-123, https://jira.example.com/browse/PROJ-123,
                              https://linear.app/team/issue/ENG-456, owner/repo#42

Platform Options:
  --platform, -p PLATFORM     Override platform detection (jira, linear, github,
                              azure_devops, monday, trello)
```

### Phase 7: Update Configuration Section

#### Step 7.1: Add DEFAULT_PLATFORM to Config Options (Lines 389-405)

Add to the Configuration Options table:

```markdown
| `DEFAULT_PLATFORM` | string | "" | Default platform for ambiguous ticket IDs |
```

Update the configuration file example:

```bash
# Platform Settings
DEFAULT_PLATFORM=""  # Options: jira, linear, github, azure_devops, monday, trello
```

### Phase 8: Update First Run Section

#### Step 8.1: Update First Run Description (Lines 241-248)

**Current:**
```markdown
### First Run

On first run, SPEC will:
1. Check for Auggie CLI installation (offer to install if missing)
2. Prompt for Auggie login if needed
3. Check Jira integration status
4. Create agent definition files in `.augment/agents/`
```

**New:**
```markdown
### First Run

On first run, SPEC will:
1. Check for Auggie CLI installation (offer to install if missing)
2. Prompt for Auggie login if needed
3. Check platform integration status (Jira, Linear, GitHub via Auggie)
4. Create agent definition files in `.augment/agents/`

**Note:** Azure DevOps, Monday, and Trello require fallback credentials to be configured. See [AMI-39: Platform Configuration Guide] for setup instructions.
```

### Phase 9: Update Agent Documentation

#### Step 9.1: Update Agent Files Table (Lines 430-435)

**Current:**
```markdown
| `.augment/agents/ingot-planner.md` | Creates implementation plans from Jira tickets |
```

**New:**
```markdown
| `.augment/agents/ingot-planner.md` | Creates implementation plans from tickets |
```

### Phase 10: Update Troubleshooting Section

#### Step 10.1: Add Multi-Platform Troubleshooting (After Lines 602-663)

Add new troubleshooting sections:

```markdown
#### Platform Detection Issues

If SPEC detects the wrong platform:

```bash
# Use --platform to explicitly specify
spec PROJ-123 --platform jira

# Or set a default in configuration
# Add to ~/.ingot-config:
DEFAULT_PLATFORM="jira"
```

#### "Platform not supported" Error

For Azure DevOps, Monday, or Trello, fallback credentials are required:

```bash
# Check which platforms are configured
spec --config

# See AMI-39: Platform Configuration Guide for credential setup
```

#### Ambiguous Ticket ID

If prompted to select a platform:

```bash
# Both Jira and Linear use PROJECT-123 format
# SPEC will prompt you to choose, or use --platform:
spec ENG-456 --platform linear
```
```

---

## Acceptance Criteria

### Content Requirements

- [ ] **AC1:** README header tagline is platform-agnostic
- [ ] **AC2:** "What is SPEC?" section mentions all 6 platforms
- [ ] **AC3:** A "Supported Platforms" section exists with platform comparison table
- [ ] **AC4:** Quick Start shows examples for multiple platforms
- [ ] **AC5:** Workflow diagram references generic "Ticket" not "Jira Ticket"
- [ ] **AC6:** Basic Commands section shows Jira, Linear, and GitHub examples
- [ ] **AC7:** `--platform` / `-p` flag is documented in Command-Line Options
- [ ] **AC8:** `DEFAULT_PLATFORM` is documented in Configuration section
- [ ] **AC9:** First Run section mentions multi-platform integration checking
- [ ] **AC10:** Agent file descriptions are platform-agnostic
- [ ] **AC11:** Troubleshooting section includes multi-platform issues

### Language Requirements

- [ ] **LR1:** All instances of "Jira ticket" are reviewed and updated where appropriate
- [ ] **LR2:** Jira-specific features remain accurately documented (not falsely generalized)
- [ ] **LR3:** Terminology is consistent ("ticket" not "Jira ticket" for generic references)
- [ ] **LR4:** Examples show real, valid syntax for each platform

### Quality Requirements

- [ ] **QR1:** All markdown renders correctly (no broken links, tables, code blocks)
- [ ] **QR2:** Example commands are accurate and functional
- [ ] **QR3:** No duplicate sections or conflicting information
- [ ] **QR4:** Table of contents links still work after reorganization

---

## Testing/Validation Strategy

### Manual Validation Steps

1. **Render README.md** - View in GitHub or local markdown viewer to ensure formatting
2. **Test example commands** - Run each example command to verify accuracy
3. **Search for "Jira"** - Verify all instances are intentional (not missed updates)
4. **Check links** - Ensure all internal links (`#section-name`) work
5. **Review tables** - Confirm all tables render correctly

### Validation Checklist

```bash
# Search for remaining Jira-specific language
grep -n "Jira" README.md

# Expected: Only in platform-specific contexts, not generic references
# Example OK: "Jira: Automatic ticket fetching..."
# Example NOT OK: "Given a Jira ticket, SPEC:"

# Verify --platform examples work
spec --help | grep -A2 "platform"

# Verify configuration documentation matches actual settings
spec --config
```

---

## Dependencies

### Upstream Dependencies (Must Be Complete First)

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| AMI-25 | CLI Migration | ✅ Required | CLI must support multi-platform before documenting it |

### Related Tickets (Parallel Work)

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-39](https://linear.app/amiadingot/issue/AMI-39) | Create Platform Configuration Guide | Detailed credential setup docs |
| [AMI-42](https://linear.app/amiadingot/issue/AMI-42) | Update spec --config Output | Config display updates |
| [AMI-43](https://linear.app/amiadingot/issue/AMI-43) | Audit User-Facing Strings | Code-level string updates |

---

## Estimated Effort

### Per-Phase Estimates

| Phase | Description | Estimate | Risk |
|-------|-------------|----------|------|
| Phase 1 | Update header and introduction | 0.25 day | Low |
| Phase 2 | Add Supported Platforms section | 0.25 day | Low |
| Phase 3 | Update Features section | 0.15 day | Low |
| Phase 4 | Update Quick Start | 0.15 day | Low |
| Phase 5 | Update workflow diagram | 0.1 day | Low |
| Phase 6 | Update Usage section | 0.25 day | Low |
| Phase 7 | Update Configuration section | 0.15 day | Low |
| Phase 8 | Update First Run section | 0.1 day | Low |
| Phase 9 | Update Agent documentation | 0.1 day | Low |
| Phase 10 | Update Troubleshooting section | 0.25 day | Low |
| Validation | Manual testing and review | 0.25 day | Low |
| **Total** | | **2 days** | **Low** |

---

## Example: Before and After

### Header Tagline

**Before:**
```
Transform Jira tickets into implemented features with a structured, AI-assisted three-step workflow.
```

**After:**
```
Transform tickets from any platform into implemented features with a structured, AI-assisted three-step workflow.
```

### Quick Start Example

**Before:**
```bash
spec PROJECT-123
```

**After:**
```bash
# From any platform:
spec https://company.atlassian.net/browse/PROJECT-123  # Jira
spec https://linear.app/team/issue/ENG-456              # Linear
spec owner/repo#42                                       # GitHub

# With explicit platform:
spec PROJECT-123 --platform jira
```

---

## References

### Related Documentation

| Document | Purpose |
|----------|---------|
| [AMI-25-implementation-plan.md](./AMI-25-implementation-plan.md) | CLI migration details |
| [AMI-32-implementation-plan.md](./AMI-32-implementation-plan.md) | TicketService architecture |
| [00_Architecture_Refactor_Spec.md](./00_Architecture_Refactor_Spec.md) | Overall architecture |

### Current CLI Help Text (from AMI-25)

Reference the implemented CLI for accurate documentation:

```bash
spec --help
```

Key options to document:
- `--platform, -p PLATFORM` - Override platform detection
- Ticket argument accepts URLs and IDs from all platforms

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-28 | AI Assistant | Initial draft created |
