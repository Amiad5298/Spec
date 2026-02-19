# INGOT

**Spec-Driven Development Workflow Powered by AI**

Transform tickets from any supported platform into implemented features with a structured, AI-assisted workflow.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## Table of Contents

- [What is INGOT?](#what-is-ingot)
- [Why INGOT is Different](#why-ingot-is-different-context-engineering--git-sterility)
- [Features](#features)
- [AI Backends](#ai-backends)
- [Supported Platforms](#supported-platforms)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Agent Customization](#agent-customization)
- [Project Structure](#project-structure)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## What is INGOT?

INGOT is a command-line tool that orchestrates AI agents to implement software features from start to finish. Given a ticket from any supported platform (Jira, Linear, GitHub, Azure DevOps, Monday, or Trello), INGOT runs a multi-step workflow:

1. **Plans** - Creates a detailed implementation plan by analyzing requirements and your codebase
2. **Clarifies** - Optional interactive Q&A to resolve ambiguities before coding begins
3. **Tasks** - Generates an optimized task list, identifying which tasks can run in parallel
4. **Executes** - Runs specialized AI agents to complete each task, with checkpoint commits and progress tracking
5. **Updates Docs** - Automatically updates documentation to reflect code changes
6. **Commits** - Stages and commits implementation files with a generated commit message

INGOT orchestrates AI coding assistants with specialized AI agents to deliver a structured, reproducible development workflow.

## Why INGOT is Different: Context Engineering & Git Sterility

Most AI orchestration tools accumulate chat history across tasks — the planner's conversation bleeds into the implementer's, one task's context leaks into the next, and the reviewer sees diffs polluted by pre-existing changes. The result is **Context Rot**: hallucinated references to prior tasks, stale instructions, and token bloat that degrades output quality over time. INGOT takes a fundamentally different approach by treating context as a first-class engineering concern.

| Dimension | Typical AI Tools | INGOT |
|-----------|-----------------|-------|
| Session management | Accumulated chat history across tasks | Fresh, isolated session per task |
| Git diff scope | `git diff` of entire working tree | Baseline-anchored diffs scoped to workflow changes only |
| Dirty tree handling | Hope for the best | Fail-fast policy — refuses to start with uncommitted changes |
| Parallel agent isolation | Shared context, shared session | Fresh backend instance + fresh session + file-level scoping per worker |
| Review determinism | Reviews polluted by pre-existing changes | Reviewer sees only changes introduced by the current workflow |

### Context Sterility

Every task execution — implementation, review, self-correction, testing — starts a completely fresh LLM session with zero prior conversation history. Self-correction attempts don't even share context with the original failed attempt; the error output is embedded in a new prompt, not appended to a conversation. This eliminates "context rot" where the LLM hallucinates references to work done in prior tasks.

### Fail-Fast Git Baselines

Before any code changes, INGOT pins the current HEAD as a baseline and verifies the working tree is clean. All subsequent diffs — including the final code review — are scoped to changes since that baseline. The reviewer never sees pre-existing noise. If the working tree is dirty, INGOT refuses to proceed (configurable via `--dirty-tree-policy`). For replan loops, the working tree is restored to the baseline state, ensuring each attempt starts from a known-good state.

### Parallel Isolation

When running up to 5 agents concurrently, each worker gets three layers of isolation: (1) a fresh backend instance with no shared process state, (2) a fresh session with no shared conversation history, and (3) file-level scoping via task annotations that prevent parallel tasks from touching overlapping files. Even the cross-task memory system is disabled during parallel execution to prevent contamination.

> **Bottom line:** INGOT treats context as a first-class engineering concern, not an afterthought. Every architectural decision — session isolation, baseline anchoring, file-level scoping — exists to ensure that each agent invocation operates on exactly the information it needs and nothing more.

## Features

### Multi-Step Workflow
A structured approach that breaks complex features into manageable pieces:
- **Step 1 - Plan**: AI-generated implementation plan based on ticket and codebase analysis
- **Step 1.5 - Clarify** (optional): Interactive Q&A loop with conflict detection to resolve ambiguities before coding
- **Step 2 - Task List**: Task list with dependency analysis and user approval loop (approve/edit/regenerate)
- **Step 3 - Execute**: Dual-phase task execution with self-correction loop, code review, and replan capability
- **Step 4 - Update Docs** (optional): AI-driven documentation synchronization with guardrails
- **Step 5 - Commit** (optional): Automated staging and commit with artifact exclusion

### Parallel Task Execution
Dramatically reduce implementation time:
- Automatically identifies independent tasks that can run concurrently
- Configurable parallelism (1-5 concurrent tasks)
- Fail-fast or continue-on-error modes
- Built-in rate limit handling with exponential backoff and jitter
- Thread-safe execution with fresh backend instance per worker

### Conflict Detection
Fail-Fast Semantic Check before implementation begins:
- Detects contradictions between ticket requirements and user-provided context
- LLM-powered semantic analysis (not keyword matching)
- Automatically triggers clarification step when conflicts are found

### Task Memory
Cross-task learning system that improves execution across tasks:
- Captures patterns, key decisions, and test commands from completed tasks
- Finds related memories via keyword overlap
- Provides established patterns to subsequent tasks without context pollution

### Deep Integrations
- **6 Ticket Platforms**: Jira, Linear, GitHub, Azure DevOps, Monday, and Trello
- **Automatic Platform Detection**: URLs and ticket IDs are automatically routed to the correct platform
- **6 AI Backends**: Auggie, Claude Code, Cursor, Aider, Gemini, and Codex
- **Git**: Feature branch creation, checkpoint commits after each task, optional commit squashing
- **Fetch Strategy System**: Configurable AGENT/DIRECT/AUTO strategies with ticket caching

### Git Integration
INGOT integrates with Git while giving you full control over your commits:

- **Automatic `.gitignore` Configuration**: On first run, INGOT adds patterns to exclude run logs (`.ingot/`), keeping your repository clean.
- **Baseline-Anchored Diffs**: Captures a baseline commit at Step 3 start. All subsequent diffs are scoped to changes since that baseline, preventing pollution from pre-existing uncommitted changes.
- **Dirty Tree Policy**: Configurable handling of uncommitted changes before execution (`fail-fast` to abort, `warn` to continue).
- **Workflow Artifact Exclusion**: Files in `specs/`, `.ingot/`, and `.augment/` are excluded from commits and dirty tree checks.

### Automated Code Review
Optional reviews that validate work quality:
- Runs after task execution with baseline-anchored diffs
- Smart diff handling (uses `--stat` for large changesets >2000 lines or >20 files)
- Three review statuses: `PASS`, `NEEDS_ATTENTION`, `NEEDS_REPLAN`
- **Auto-fix**: When reviews return `NEEDS_ATTENTION`, the implementer agent addresses feedback automatically
- Auto-fix loop is configurable via `--max-review-fix-attempts` (default: 3, 0 to disable)
- **Re-review**: Automatically re-runs review after auto-fix to verify fixes
- **Replan**: When reviews return `NEEDS_REPLAN`, triggers the replan loop (see below)
- Enable with `--enable-review` flag

### Self-Correction Loop
Automatic error recovery during task execution:
- When a task fails, INGOT feeds the error output back to the AI in a fresh session
- Each correction attempt starts a clean LLM session — only the error is embedded in the new prompt
- Configurable max attempts via `--max-self-corrections` (default: 3, 0 to disable)
- Distinct from rate-limit retry (which retries the same prompt after a delay)

### Replan Loop
Automatic re-planning when the implementation approach is fundamentally wrong:
- When code review returns `NEEDS_REPLAN`, INGOT loops back to Step 1
- Working tree is restored to the baseline state before re-planning
- Two replan modes: **AI-driven** (regenerates plan with review feedback) or **Manual** (user edits plan)
- Each iteration: restore working tree → update plan → regenerate task list → re-execute

### Documentation Enforcement (Step 4)
Non-blocking documentation maintenance with guardrails:
- Smart doc-file detection across multiple patterns (`.md`, `.rst`, `docs/`, root README, CHANGELOG, etc.)
- Non-doc change enforcement: snapshots non-doc state, detects, and reverts unauthorized changes by the doc agent
- Prominent violation warnings for manual review

### Predictive Context (Target Files)
Reduce AI hallucinations and prevent file conflicts during parallel execution:
- Explicit file scoping with `<!-- files: ... -->` task annotations
- Task list agent predicts which files each task will modify
- File disjointness validation for parallel tasks
- Path security with directory traversal prevention

```markdown
<!-- category: fundamental, order: 1 -->
<!-- files: src/models/user.py, src/db/schema.py -->
- [ ] Create user model and database schema

<!-- category: independent, group: features -->
<!-- files: src/api/auth.py, tests/test_auth.py -->
- [ ] Implement authentication endpoint
```

### Terminal UI (Textual)
- Real-time task progress visualization with Textual
- Split-pane layout with task list and scrollable log panel
- Interactive menus for task review and approval
- Thread-safe parallel execution display
- Works in both TUI mode and simple fallback for CI environments

### Specialized AI Agents
Seven purpose-built agents work together:

| Agent | Purpose |
|-------|---------|
| `ingot-planner` | Analyzes requirements and creates implementation plans |
| `ingot-tasklist` | Converts plans into optimized, executable task lists |
| `ingot-tasklist-refiner` | Post-processes task lists to extract test tasks into the independent category |
| `ingot-implementer` | Executes individual tasks with codebase awareness |
| `ingot-reviewer` | Validates completed work with PASS/NEEDS_ATTENTION output |
| `ingot-fixer` | Auto-fixes issues found by the reviewer (reuses implementer) |
| `ingot-doc-updater` | Updates documentation after code changes (Step 4) |

## AI Backends

INGOT supports six AI coding assistants as backends. You choose one during first-run setup and can switch at any time.

| Backend | CLI Requirement | Installation |
|---------|----------------|--------------|
| **Auggie** | Auggie CLI (Node.js 22+) | [docs.augmentcode.com/cli](https://docs.augmentcode.com/cli) |
| **Claude Code** | Claude Code CLI | [docs.anthropic.com/en/docs/claude-code](https://docs.anthropic.com/en/docs/claude-code/overview) |
| **Cursor** | Cursor CLI | [cursor.com/cli](https://www.cursor.com/cli) |
| **Aider** | Aider CLI | [aider.chat](https://aider.chat) |
| **Gemini** | Gemini CLI | [ai.google.dev](https://ai.google.dev) |
| **Codex** | OpenAI Codex CLI | [openai.com](https://openai.com) |

### Selecting Your Backend

1. **First run**: The onboarding wizard prompts you to choose a backend and verifies installation
2. **Configuration**: Your choice is saved as `AI_BACKEND` in `~/.ingot-config`
3. **CLI override**: Use `--backend` (`-b`) to override for a single run

```bash
# Override backend for a single run
ingot --backend claude PROJECT-123
ingot -b cursor PROJECT-123
ingot -b aider PROJECT-123

# Or change the default in ~/.ingot-config
# AI_BACKEND="claude"
```

## Supported Platforms

INGOT supports 6 ticket platforms. Three backends (Auggie, Claude Code, Cursor) provide MCP integrations for zero-config ticket fetching on supported platforms; the remaining backends (Aider, Gemini, Codex) require API credentials for all platforms.

| Platform | URL Support | Ticket ID Support | MCP Support | Notes |
|----------|-------------|-------------------|-------------|-------|
| **Jira** | Yes | `PROJECT-123` | Auggie, Claude, Cursor | Zero-config with MCP-enabled backends |
| **Linear** | Yes | URL preferred | Auggie, Claude, Cursor | IDs like `ENG-123` may be ambiguous with Jira |
| **GitHub Issues** | Yes | `owner/repo#42` | Auggie, Claude, Cursor | Zero-config with MCP-enabled backends |
| **Azure DevOps** | Yes | `AB#123` | -- | Requires credentials in `~/.ingot-config` |
| **Monday** | Yes | URL only | -- | Requires credentials in `~/.ingot-config` |
| **Trello** | Yes | 8-char short ID | -- | Requires credentials in `~/.ingot-config` |

> **MCP-integrated platforms** (Jira, Linear, GitHub): No additional configuration needed when using Auggie, Claude Code, or Cursor backends — works via built-in MCP integrations.
>
> **API-only platforms** (Azure DevOps, Monday, Trello): Requires API credentials regardless of backend. See the [Platform Configuration Guide](docs/platform-configuration.md).
>
> **Non-MCP backends** (Aider, Gemini, Codex): Require API credentials for all platforms, including Jira, Linear, and GitHub.

### Platform Detection

INGOT automatically detects the platform from the ticket URL or ID:

```bash
# URLs are auto-detected
ingot https://company.atlassian.net/browse/PROJ-123          # Jira
ingot https://linear.app/team/issue/ENG-456                  # Linear
ingot https://github.com/owner/repo/issues/42                # GitHub
ingot https://dev.azure.com/org/project/_workitems/edit/789  # Azure DevOps

# Ambiguous IDs require --platform flag
ingot PROJ-123 --platform jira
ingot ENG-456 --platform linear
```

### Ambiguous IDs

Some ticket ID formats are shared across platforms (e.g., `ABC-123` matches both Jira and Linear). When INGOT cannot determine the platform unambiguously, it will:

1. Check `DEFAULT_PLATFORM` in `~/.ingot-config` (if set)
2. Prompt you to select a platform interactively

```bash
ingot ENG-456                    # Ambiguous - prompts or uses DEFAULT_PLATFORM
ingot ENG-456 --platform linear  # Explicitly targets Linear
ingot ENG-456 --platform jira    # Explicitly targets Jira
```

## Quick Start

```bash
# Install INGOT
pip install ingot

# Navigate to your git repository
cd your-project

# Start a workflow with any ticket
ingot https://company.atlassian.net/browse/PROJECT-123  # Jira URL
ingot https://linear.app/team/issue/ENG-456              # Linear URL
ingot https://github.com/owner/repo/issues/42            # GitHub URL
ingot https://dev.azure.com/org/project/_workitems/edit/789  # Azure DevOps
ingot https://mycompany.monday.com/boards/123456/pulses/789  # Monday
ingot https://trello.com/c/aBcDeFgH/123-card-title           # Trello

# Or use a ticket ID with explicit platform
ingot PROJECT-123 --platform jira
ingot owner/repo#42  # GitHub (unambiguous)
```

That's it! INGOT will guide you through the entire workflow with interactive prompts.

## How It Works

### The INGOT Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INGOT WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Ticket (Any Platform)                                               │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: PLAN                                                │    │
│  │  • Fetch ticket details from platform                        │    │
│  │  • Analyze codebase with context retrieval                   │    │
│  │  • Generate implementation plan                              │    │
│  │  • Output: specs/{ticket}-plan.md                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  STEP 1.5: CLARIFY (optional)                                │    │
│  │  • Conflict detection between ticket and user context        │    │
│  │  • Interactive Q&A loop (up to 10 rounds)                    │    │
│  │  • Rewrite plan with clarifications                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  STEP 2: TASK LIST                                           │    │
│  │  • Generate task list with FUNDAMENTAL/INDEPENDENT categories │    │
│  │  • Post-process: extract test tasks to INDEPENDENT           │    │
│  │  • User reviews and approves/edits/regenerates/aborts        │    │
│  │  • Output: specs/{ticket}-tasklist.md                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  STEP 3: EXECUTE                                             │    │
│  │  • Capture baseline commit for diff anchoring                │    │
│  │  • Phase 1: Sequential execution of FUNDAMENTAL tasks        │    │
│  │  • Phase 2: Parallel execution of INDEPENDENT tasks          │    │
│  │  • Self-correction loop per task (up to N attempts)          │    │
│  │  • Post-implementation targeted test execution               │    │
│  │  • Optional code review with auto-fix                        │    │
│  │  • NEEDS_REPLAN → restore tree → back to Step 1              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│      │         ▲                                                     │
│      │         └── replan loop ──────────────────────────────┘      │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  STEP 4: UPDATE DOCS (optional)                              │    │
│  │  • AI-driven documentation synchronization                   │    │
│  │  • Non-doc change enforcement (revert unauthorized changes)  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  STEP 5: COMMIT (optional)                                   │    │
│  │  • Diff summary display                                      │    │
│  │  • Workflow artifact exclusion from staging                   │    │
│  │  • Auto-generated commit message with user editing            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│      │                                                               │
│      ▼                                                               │
│  Implemented Feature (ready for PR)                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Task Categories

INGOT organizes tasks into two categories for optimal execution:

#### Fundamental Tasks (Sequential)
Tasks that must run in order due to dependencies:
- Database schema changes
- Core model/type definitions
- Shared utilities
- Configuration setup

#### Independent Tasks (Parallel)
Tasks that can run concurrently with no dependencies:
- UI components (after models exist)
- Separate API endpoints
- Test suites
- Documentation updates

### Generated Files

INGOT creates files in the `specs/` directory:

| File | Description |
|------|-------------|
| `specs/{ticket}-plan.md` | Detailed implementation plan with technical approach, steps, and testing strategy |
| `specs/{ticket}-tasklist.md` | Executable task list with categories and checkboxes |

Run logs are stored in `.ingot/runs/{ticket}/` for debugging and audit purposes:

```
.ingot/runs/{ticket}/
├── {timestamp}/          # Step 3 task logs
│   ├── task_001_*.log
│   └── task_002_*.log
├── plan_generation/      # Step 1 logs
├── test_execution/       # Post-implementation test logs
└── doc_update/           # Step 4 logs
```

## Installation

### Requirements

- **Python 3.12+**
- **Git** (must be run from a git repository)
- **AI Backend CLI** (at least one):
  - [Auggie CLI](https://docs.augmentcode.com/cli) (requires Node.js 22+)
  - [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/overview)
  - [Cursor](https://www.cursor.com/cli)
  - [Aider](https://aider.chat)
  - [Gemini CLI](https://ai.google.dev)
  - [Codex CLI](https://openai.com)

> Backend requirements are verified during first-run setup.

### Install from PyPI

```bash
pip install ingot
```

### Install from Source

```bash
git clone https://github.com/Amiad5298/INGOT.git
cd AI-Platform

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"
```

### Verify Installation

```bash
ingot --version
ingot --help
```

### First Run

On first run, INGOT launches an onboarding wizard that walks you through backend setup:

1. **Select AI Backend** - choose your preferred AI coding assistant
2. **Verify Installation** - INGOT checks that the CLI is installed
3. **Save Configuration** - your choice is saved to `~/.ingot-config` as `AI_BACKEND`

```
$ ingot PROJECT-123

  Welcome to INGOT!
  Let's set up your AI backend. You can change this later with 'ingot config'.

  ? Which AI backend would you like to use?
  > Auggie (Augment Code CLI)
    Claude Code CLI
    Cursor
    Aider
    Gemini
    Codex

  ✓ Backend detected and configured.
  ✓ Configuration saved to ~/.ingot-config
```

## Usage

### Basic Commands

```bash
# Start workflow with a ticket URL (auto-detected platform)
ingot https://company.atlassian.net/browse/PROJECT-123

# Start with ticket ID
ingot PROJECT-123 --platform jira

# Show interactive main menu
ingot

# View current configuration
ingot --config
```

### Command-Line Options

```
ingot [OPTIONS] [TICKET]

Arguments:
  TICKET                      Ticket ID or URL from a supported platform

Platform Options:
  --platform, -p PLATFORM     Override platform detection (jira, linear, github,
                              azure_devops, monday, trello)

Backend Options:
  --backend, -b BACKEND       Override AI backend (auggie, claude, cursor,
                              aider, gemini, codex)

Model Options:
  --model, -m MODEL           Override AI model for all phases
  --planning-model MODEL      Model for Steps 1-2 (planning)
  --impl-model MODEL          Model for Step 3 (implementation)

Workflow Options:
  --skip-clarification        Skip the clarification step (Step 1.5)
  --no-squash                 Don't squash checkpoint commits at end
  --force-integration-check   Force fresh platform integration check
  --enable-review             Enable automated code review after task execution
  --dirty-tree-policy POLICY  Handle uncommitted changes: 'fail-fast' (default) or 'warn'
  --auto-update-docs /
    --no-auto-update-docs     Enable/disable automatic documentation updates (Step 4)
  --auto-commit /
    --no-auto-commit          Enable/disable automatic commit (Step 5)

Parallel Execution:
  --parallel/--no-parallel    Enable/disable parallel task execution
  --max-parallel N            Maximum parallel tasks (1-5, default: from config)
  --fail-fast/--no-fail-fast  Stop on first task failure

Self-Correction & Review:
  --max-self-corrections N    Max self-correction attempts per task (0 to disable, default: 3)
  --max-review-fix-attempts N Max auto-fix attempts during review (0 to disable, default: 3)

Rate Limiting:
  --max-retries N             Max retries on rate limit (0 to disable, default: 5)
  --retry-base-delay SECS     Base delay for retry backoff (default: 2.0 seconds)

Display Options:
  --tui/--no-tui              Enable/disable TUI mode (default: auto-detect)
  --verbose, -V               Show verbose output in TUI log panel

Other:
  --config                    Show current configuration and exit
  --version, -v               Show version information
  --help, -h                  Show help message
```

### Example Workflows

#### Standard Feature Development

```bash
ingot PROJ-456

# INGOT will:
# 1. Fetch ticket from platform
# 2. Ask if you want to add context
# 3. Detect conflicts (if context provided)
# 4. Create feature branch
# 5. Generate implementation plan (Step 1)
# 6. Run interactive clarification (Step 1.5, if not skipped)
# 7. Generate task list with approval loop (Step 2)
# 8. Execute tasks in two phases (Step 3)
# 9. Update documentation (Step 4)
# 10. Commit changes (Step 5)
```

#### Fast Mode (Skip Clarification)

```bash
ingot PROJ-789 --skip-clarification
```

#### Custom Model Selection

```bash
# Use specific model for planning vs implementation
ingot PROJ-101 --planning-model claude-sonnet-4-5 --impl-model claude-opus-4

# Use same model for everything
ingot PROJ-101 --model claude-opus-4
```

#### Parallel Execution Control

```bash
# Run up to 5 tasks in parallel
ingot PROJ-202 --max-parallel 5

# Disable parallel execution (sequential only)
ingot PROJ-202 --no-parallel

# Stop immediately on any task failure
ingot PROJ-202 --fail-fast
```

#### With Code Review

```bash
# Enable automated code review with auto-fix
ingot PROJ-303 --enable-review
```

#### Documentation and Commit Control

```bash
# Skip automatic documentation updates
ingot PROJ-404 --no-auto-update-docs

# Skip automatic commit
ingot PROJ-404 --no-auto-commit

# Skip both
ingot PROJ-404 --no-auto-update-docs --no-auto-commit
```

## Configuration

### Configuration File

INGOT stores configuration in `~/.ingot-config`:

```bash
# AI Backend
AI_BACKEND="auggie"

# AI Model Configuration
PLANNING_MODEL="claude-sonnet-4-5"
IMPLEMENTATION_MODEL="claude-sonnet-4-5"

# Platform Settings
DEFAULT_PLATFORM=""  # Options: jira, linear, github, azure_devops, monday, trello

# Workflow Behavior
SKIP_CLARIFICATION="false"
SQUASH_AT_END="true"
AUTO_OPEN_FILES="true"
AUTO_UPDATE_DOCS="true"
AUTO_COMMIT="true"

# Parallel Execution
PARALLEL_EXECUTION_ENABLED="true"
MAX_PARALLEL_TASKS="3"
FAIL_FAST="false"
MAX_SELF_CORRECTIONS="3"
MAX_REVIEW_FIX_ATTEMPTS="3"

# Fetch Strategy
FETCH_STRATEGY_DEFAULT="auto"      # Options: auto, agent, direct
FETCH_CACHE_DURATION_HOURS="24"
FETCH_TIMEOUT_SECONDS="30"
FETCH_MAX_RETRIES="3"
FETCH_RETRY_DELAY_SECONDS="1.0"

# Custom Subagent Names
SUBAGENT_PLANNER="ingot-planner"
SUBAGENT_TASKLIST="ingot-tasklist"
SUBAGENT_TASKLIST_REFINER="ingot-tasklist-refiner"
SUBAGENT_IMPLEMENTER="ingot-implementer"
SUBAGENT_REVIEWER="ingot-reviewer"
SUBAGENT_FIXER="ingot-implementer"
SUBAGENT_DOC_UPDATER="ingot-doc-updater"
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `AI_BACKEND` | string | `""` | AI backend (auggie, claude, cursor, aider, gemini, codex) |
| `PLANNING_MODEL` | string | `""` | AI model for Steps 1-2 |
| `IMPLEMENTATION_MODEL` | string | `""` | AI model for Step 3 |
| `DEFAULT_PLATFORM` | string | `""` | Default platform for ambiguous ticket IDs |
| `SKIP_CLARIFICATION` | bool | `false` | Skip clarification step (Step 1.5) |
| `SQUASH_AT_END` | bool | `true` | Squash commits after workflow |
| `AUTO_OPEN_FILES` | bool | `true` | Auto-open generated files |
| `AUTO_UPDATE_DOCS` | bool | `true` | Enable automatic documentation updates (Step 4) |
| `AUTO_COMMIT` | bool | `true` | Enable automatic commit (Step 5) |
| `PARALLEL_EXECUTION_ENABLED` | bool | `true` | Enable parallel task execution |
| `MAX_PARALLEL_TASKS` | int | `3` | Max concurrent tasks (1-5) |
| `FAIL_FAST` | bool | `false` | Stop on first task failure |
| `MAX_SELF_CORRECTIONS` | int | `3` | Max self-correction attempts per task (0 to disable) |
| `MAX_REVIEW_FIX_ATTEMPTS` | int | `3` | Max auto-fix attempts during review (0 to disable) |
| `FETCH_STRATEGY_DEFAULT` | string | `"auto"` | Fetch strategy: auto, agent, or direct |
| `FETCH_CACHE_DURATION_HOURS` | int | `24` | Ticket cache TTL in hours |
| `FETCH_TIMEOUT_SECONDS` | int | `30` | Fetch timeout per request |
| `FETCH_MAX_RETRIES` | int | `3` | Max fetch retry attempts |
| `FETCH_RETRY_DELAY_SECONDS` | float | `1.0` | Retry delay between fetch attempts |
| `SUBAGENT_PLANNER` | string | `"ingot-planner"` | Custom planner agent name |
| `SUBAGENT_TASKLIST` | string | `"ingot-tasklist"` | Custom tasklist agent name |
| `SUBAGENT_TASKLIST_REFINER` | string | `"ingot-tasklist-refiner"` | Custom tasklist refiner agent name |
| `SUBAGENT_IMPLEMENTER` | string | `"ingot-implementer"` | Custom implementer agent name |
| `SUBAGENT_REVIEWER` | string | `"ingot-reviewer"` | Custom reviewer agent name |
| `SUBAGENT_FIXER` | string | `"ingot-implementer"` | Custom fixer agent name |
| `SUBAGENT_DOC_UPDATER` | string | `"ingot-doc-updater"` | Custom doc updater agent name |

### Configuration Hierarchy

Configuration is resolved with the following priority (highest to lowest):

1. **CLI flags** (e.g., `--backend claude`)
2. **Environment variables** (e.g., `INGOT_LOG`)
3. **Local config** (`.ingot` file in project or parent directories)
4. **Global config** (`~/.ingot-config`)
5. **Built-in defaults**

### Changing AI Backend

```bash
# Edit the default in ~/.ingot-config
AI_BACKEND="claude"   # Options: auggie, claude, cursor, aider, gemini, codex

# Or override for a single run
ingot --backend cursor PROJECT-123
```

### Platform Credentials

For platforms without Auggie integration (Azure DevOps, Monday, Trello), you must configure fallback credentials. Jira, Linear, and GitHub can optionally use fallback credentials as a backup.

See the **[Platform Configuration Guide](docs/platform-configuration.md)** for:
- Step-by-step credential setup for each platform
- Security best practices for storing credentials
- Troubleshooting common authentication errors

### View Current Configuration

```bash
ingot --config
```

## Agent Customization

INGOT uses specialized AI agents defined in `.augment/agents/`. These are created automatically on first run and updated when INGOT detects newer internal templates. All backends load subagent prompts from this directory.

### Agent Files

| File | Purpose |
|------|------------|
| `.augment/agents/ingot-planner.md` | Creates implementation plans from tickets |
| `.augment/agents/ingot-tasklist.md` | Generates task lists with FUNDAMENTAL/INDEPENDENT categories |
| `.augment/agents/ingot-tasklist-refiner.md` | Extracts test tasks into the INDEPENDENT category |
| `.augment/agents/ingot-implementer.md` | Executes individual tasks with codebase awareness |
| `.augment/agents/ingot-reviewer.md` | Validates completed tasks with PASS/NEEDS_ATTENTION output |

### Agent File Format

Each agent file uses YAML frontmatter followed by markdown instructions:

```yaml
---
name: ingot-planner
description: INGOT workflow planner
model: claude-sonnet-4-5
color: blue
ingot_version: 2.0.0
ingot_content_hash: abc123def456
---

# Your custom instructions here...
```

### Version Management

INGOT tracks agent file versions:
- **Automatic updates**: When INGOT's internal templates are newer, you'll be prompted to update
- **User customizations preserved**: If you've modified the instructions, INGOT won't overwrite without confirmation
- **Hash-based detection**: The `ingot_content_hash` field tracks whether the file matches the expected template

## Project Structure

```
ingot/
├── __init__.py              # Version and constants
├── __main__.py              # Module entry point (python -m ingot)
├── cli/                     # CLI layer (Typer-based)
│   ├── app.py              # Typer application and main command
│   ├── menu.py             # Main menu and configuration UI
│   ├── platform.py         # Platform detection and disambiguation
│   ├── ticket.py           # Ticket fetching logic
│   ├── workflow.py         # Workflow orchestration
│   └── async_helpers.py    # Async execution helpers
├── config/                  # Configuration management
│   ├── manager.py          # ConfigManager (cascading hierarchy)
│   ├── settings.py         # Settings dataclass
│   ├── fetch_config.py     # Fetch strategy and backend config
│   ├── backend_resolver.py # Backend resolution logic
│   ├── compatibility.py    # Backward-compatible config migrations
│   ├── validation.py       # Configuration validation
│   └── display.py          # Configuration display
├── integrations/            # External integrations
│   ├── backends/           # AI backend implementations
│   │   ├── base.py        # AIBackend protocol and BaseBackend
│   │   ├── factory.py     # BackendFactory for instantiation
│   │   ├── errors.py      # Backend-specific error re-exports
│   │   ├── model_discovery.py # Model detection and validation
│   │   ├── auggie.py      # Auggie backend
│   │   ├── claude.py      # Claude Code backend
│   │   ├── cursor.py      # Cursor backend
│   │   ├── aider.py       # Aider backend
│   │   ├── gemini.py      # Gemini backend
│   │   └── codex.py       # Codex backend
│   ├── providers/          # Ticket platform providers
│   │   ├── base.py        # IssueTrackerProvider ABC
│   │   ├── registry.py    # Provider registry
│   │   ├── detector.py    # Platform detection
│   │   ├── exceptions.py  # Provider-specific exceptions
│   │   ├── user_interaction.py # Interactive platform prompts
│   │   ├── jira.py        # Jira provider
│   │   ├── linear.py      # Linear provider
│   │   ├── github.py      # GitHub provider
│   │   ├── azure_devops.py # Azure DevOps provider
│   │   ├── monday.py      # Monday provider
│   │   └── trello.py      # Trello provider
│   ├── fetchers/           # Ticket fetching strategies
│   │   ├── base.py        # Base fetcher ABC
│   │   ├── auggie_fetcher.py  # Auggie MCP fetcher
│   │   ├── claude_fetcher.py  # Claude MCP fetcher
│   │   ├── cursor_fetcher.py  # Cursor MCP fetcher
│   │   ├── direct_api_fetcher.py # Direct API fetcher
│   │   ├── templates.py   # Fetch prompt templates
│   │   ├── exceptions.py  # Fetcher-specific exceptions
│   │   └── handlers/      # Per-platform API handlers
│   │       ├── base.py    # Base handler ABC
│   │       ├── jira.py    # Jira API handler
│   │       ├── linear.py  # Linear API handler
│   │       ├── github.py  # GitHub API handler
│   │       ├── azure_devops.py # Azure DevOps API handler
│   │       ├── monday.py  # Monday API handler
│   │       └── trello.py  # Trello API handler
│   ├── auggie.py           # Auggie client module
│   ├── claude.py           # Claude client module
│   ├── cursor.py           # Cursor client module
│   ├── aider.py            # Aider client module
│   ├── gemini.py           # Gemini client module
│   ├── codex.py            # Codex client module
│   ├── git.py             # Git operations
│   ├── agents.py          # Agent file management
│   ├── auth.py            # Authentication manager
│   ├── cache.py           # Ticket caching
│   └── ticket_service.py  # Unified ticket service
├── onboarding/             # First-run setup
│   └── flow.py            # Onboarding wizard
├── ui/                     # User interface
│   ├── textual_runner.py  # Textual TUI orchestrator
│   ├── messages.py        # Textual message types & event bridge
│   ├── log_buffer.py      # Memory-efficient log buffer
│   ├── menus.py           # Interactive menus
│   ├── prompts.py         # User prompts (Questionary)
│   ├── screens/           # Textual screen classes
│   │   ├── multi_task.py  # Split-pane task list + log panel
│   │   ├── single_operation.py  # Single long-running operation
│   │   └── quit_modal.py  # Quit confirmation modal
│   └── widgets/           # Textual widget classes
│       ├── task_list.py   # Task status list widget
│       ├── log_panel.py   # Scrollable log panel widget
│       └── single_operation.py  # Spinner + liveness widget
├── utils/                  # Utilities
│   ├── errors.py          # Error hierarchy (IngotError base)
│   ├── logging.py         # Logging setup
│   ├── console.py         # Rich console output
│   ├── retry.py           # Rate limit retry with backoff
│   ├── env_utils.py       # Environment variable handling
│   └── error_analysis.py  # Error classification
└── workflow/               # Workflow execution engine
    ├── runner.py           # Main workflow orchestrator
    ├── state.py            # Workflow state management (WorkflowState)
    ├── constants.py        # Agent names and timeout values
    ├── events.py           # Task execution events
    ├── tasks.py            # Task parsing, categories, metadata
    ├── step1_plan.py       # Step 1: Plan creation
    ├── step1_5_clarification.py  # Step 1.5: Interactive clarification
    ├── step2_tasklist.py   # Step 2: Task list generation
    ├── step3_execute.py    # Step 3: Task execution
    ├── step4_update_docs.py # Step 4: Documentation updates
    ├── step5_commit.py     # Step 5: Git commit
    ├── parallel_executor.py # Thread-safe parallel execution
    ├── review.py           # Phase review logic
    ├── autofix.py          # Auto-fix after review failures
    ├── conflict_detection.py # Semantic conflict detection
    ├── git_utils.py        # Baseline-anchored diff utilities
    ├── log_management.py   # Run log organization
    ├── task_memory.py      # Cross-task learning system
    └── prompts.py          # Task and test prompt templates
```

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/Amiad5298/INGOT.git
cd AI-Platform

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_cli.py -v

# Run tests in parallel
pytest -n auto

# Run with verbose output (no coverage)
pytest -v --no-cov
```

### Code Quality

```bash
# Type checking
mypy ingot

# Linting
ruff check ingot tests

# Fix auto-fixable issues
ruff check --fix ingot tests

# Formatting
ruff format ingot tests
```

### Test Coverage

The project maintains 80%+ code coverage. Coverage reports are generated in `htmlcov/`:

```bash
pytest --cov=ingot --cov-report=html
open htmlcov/index.html
```

## Contributing

Contributions are welcome! Here's how to get started:

### Reporting Issues

- Check existing issues before creating a new one
- Include INGOT version, Python version, and OS
- Provide steps to reproduce the issue
- Include relevant error messages and logs

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest`
5. Run linting: `ruff check ingot tests`
6. Commit with clear messages
7. Push and create a Pull Request

### Development Guidelines

- Follow existing code patterns and style
- Add tests for new functionality
- Update documentation as needed
- Keep commits atomic and well-described
- Use type hints for all function signatures
- Follow PEP 8 (enforced by Ruff)
- Document public APIs with docstrings
- **Do not use `AGENT_PLATFORM` / `agent_platform` naming** — the codebase uses `AI_BACKEND` / `ai_backend`

## Troubleshooting

### Common Issues

#### "AI Backend CLI is not installed"

INGOT requires a supported AI backend CLI. Install one matching your `AI_BACKEND` setting:

- **Auggie**: `npm install -g @augmentcode/auggie && auggie login` — [docs](https://docs.augmentcode.com/cli)
- **Claude Code**: See [docs.anthropic.com/en/docs/claude-code](https://docs.anthropic.com/en/docs/claude-code/overview)
- **Cursor**: Download from [cursor.com/cli](https://www.cursor.com/cli)
- **Aider**: `pip install aider-chat` — [aider.chat](https://aider.chat)
- **Gemini**: See [ai.google.dev](https://ai.google.dev)
- **Codex**: See [openai.com](https://openai.com)

#### "Not in a git repository"

```bash
cd your-project
git init  # if not already a repo
ingot PROJECT-123
```

#### Rate Limit Errors

```bash
# Reduce parallelism
ingot PROJECT-123 --max-parallel 2

# Or increase retry attempts
ingot PROJECT-123 --max-retries 10 --retry-base-delay 5
```

#### TUI Display Issues

```bash
# Force simple output mode
ingot PROJECT-123 --no-tui
```

#### Dirty Working Tree Error

```bash
# Option 1: Stash your changes
git stash push -m "WIP before ingot workflow"
ingot PROJECT-123
git stash pop

# Option 2: Commit your changes
git add -A && git commit -m "WIP"
ingot PROJECT-123

# Option 3: Continue anyway (diffs may include unrelated changes)
ingot PROJECT-123 --dirty-tree-policy warn
```

#### Platform Detection Issues

```bash
# Use --platform to explicitly specify
ingot PROJ-123 --platform jira

# Or set a default in ~/.ingot-config
# DEFAULT_PLATFORM="jira"
```

### Debug Logging

INGOT writes detailed logs to `.ingot/runs/{ticket}/`:

```bash
ls -la .ingot/runs/PROJECT-123/
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with:
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Textual](https://textual.textualize.io/) - Terminal UI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Questionary](https://questionary.readthedocs.io/) - Interactive prompts
- [httpx](https://www.python-httpx.org/) - HTTP client
