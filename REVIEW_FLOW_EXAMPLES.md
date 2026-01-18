# Review Flow Examples

This document shows example flows for the updated phase review feature.

## Example 1: Review Passes

```
$ spec PROJECT-123 --enable-review

[Phase 1 tasks complete]

Running fundamental phase review...
✓ Fundamental review: PASS

[Phase 2 tasks complete]

Running final phase review...
✓ Final review: PASS

[Workflow continues to commit instructions]
```

## Example 2: Review Fails, Auto-Fix Succeeds

```
$ spec PROJECT-123 --enable-review

[Phase 1 tasks complete]

Running fundamental phase review...
⚠ Fundamental review: NEEDS_ATTENTION

Would you like to attempt auto-fix? [y/N]: y

Attempting auto-fix based on review feedback...
✓ Auto-fix completed

Run review again after auto-fix? [Y/n]: y

Re-running fundamental phase review after auto-fix...
✓ Fundamental review after auto-fix: PASS

[Workflow continues to Phase 2]
```

## Example 3: Review Fails, User Declines Auto-Fix, Continues Anyway

```
$ spec PROJECT-123 --enable-review

[Phase 1 tasks complete]

Running fundamental phase review...
⚠ Fundamental review: NEEDS_ATTENTION

Would you like to attempt auto-fix? [y/N]: n

Continue workflow despite review issues? [Y/n]: y

[Workflow continues to Phase 2]
```

## Example 4: Review Fails, User Chooses to Stop

```
$ spec PROJECT-123 --enable-review

[Phase 1 tasks complete]

Running fundamental phase review...
⚠ Fundamental review: NEEDS_ATTENTION

Would you like to attempt auto-fix? [y/N]: n

Continue workflow despite review issues? [Y/n]: n

ℹ Workflow stopped by user after review
Stopping after Phase 1 review.

[Workflow exits, user can fix issues manually]
```

## Example 5: Auto-Fix Runs, Re-Review Still Finds Issues

```
$ spec PROJECT-123 --enable-review

[Phase 1 tasks complete]

Running fundamental phase review...
⚠ Fundamental review: NEEDS_ATTENTION

Would you like to attempt auto-fix? [y/N]: y

Attempting auto-fix based on review feedback...
✓ Auto-fix completed

Run review again after auto-fix? [Y/n]: y

Re-running fundamental phase review after auto-fix...
⚠ Fundamental review after auto-fix: NEEDS_ATTENTION
ℹ Issues remain after auto-fix. Please review manually.

Continue workflow despite review issues? [Y/n]: y

[Workflow continues to Phase 2]
```

## Example 6: Review Execution Crashes (Advisory Behavior)

```
$ spec PROJECT-123 --enable-review

[Phase 1 tasks complete]

Running fundamental phase review...
⚠ Review execution failed: Connection timeout
ℹ Continuing workflow despite review failure

[Workflow continues to Phase 2]
```

## Example 7: Final Review Stops Workflow

```
$ spec PROJECT-123 --enable-review

[All tasks complete]

Running final phase review...
⚠ Final review: NEEDS_ATTENTION

Would you like to attempt auto-fix? [y/N]: n

Continue workflow despite review issues? [Y/n]: n

ℹ Workflow stopped by user after review
⚠ Workflow stopped after final review. Please address issues before committing.

[Workflow exits with failure status]
```

## Parser Examples

The new `_parse_review_status()` function handles various output formats:

### Standard Format (Bold Markers)
```
**Status**: PASS
```
→ Returns: `"PASS"`

### Plain Format
```
Status: NEEDS_ATTENTION
```
→ Returns: `"NEEDS_ATTENTION"`

### Multiple Markers (Uses Last)
```
**Status**: NEEDS_ATTENTION

[After fixes]

**Status**: PASS
```
→ Returns: `"PASS"`

### PASS in Normal Text (Ignored)
```
The implementation will PASS all tests.

**Status**: NEEDS_ATTENTION
```
→ Returns: `"NEEDS_ATTENTION"`

### Standalone Marker at End
```
Review complete.

**PASS**
```
→ Returns: `"PASS"`

### Ambiguous Output (Fail-Safe)
```
Some review text without clear status.
```
→ Returns: `"NEEDS_ATTENTION"`

