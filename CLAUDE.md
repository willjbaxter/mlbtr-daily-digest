# CLAUDE.md - MLB Trade Rumors Daily Digest System

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 Quick Start for New Claude Instances

### Current System Status (as of September 15, 2025)
- **Production Status**: 🔧 Fix in progress - validation logic updated
- **Agent System**: Disabled by default (enable with `ENABLE_AGENT_VALIDATION=true`)
- **Last Major Fix**: Validation counting logic (Sept 15, 2025) - Fixed `grep -c` to `grep -o | wc -l` for proper insight counting
- **Deployment**: GitHub Pages via automated workflows
- **Known Issues**: Manual workflow run still failing - needs investigation

### First Time Setup Check
```bash
# 1. Check Python environment
ls -la .venv/  # Should exist
python3 --version  # Should be 3.9+

# 2. Check current workflow status
gh run list --limit 5

# 3. Check latest content
ls -la out/chat/ | tail -3
ls -la out/mailbag/ | tail -3

# 4. Verify deployment status
git log --oneline -5  # Check recent commits
```

### Most Important Files
- `mlbtr_daily_summary.py` - Main content processor
- `.github/workflows/update_digest.yml` - Daily automation workflow
- `.github/workflows/deploy-pages.yml` - GitHub Pages deployment
- `agent_validation.py` - Multi-agent validation system (optional)

---

## 📋 Common Tasks Playbook

### Task: "Posts aren't showing on the site"
```bash
# 1. Check if workflow ran successfully
gh run list --limit 5

# 2. Check validation status in latest run
gh run view $(gh run list --limit 1 --json databaseId -q '.[0].databaseId') --log | grep -A 10 "Validation"

# 3. Check if content was committed
git log --oneline --since="2 days ago"

# 4. Manual trigger if needed
gh workflow run "Update MLBTR Daily Digest"

# 5. Check GitHub Pages deployment
gh run list -w "Deploy to GitHub Pages" --limit 3
```

### Task: "Debug failed content generation"
```bash
# 1. Download validation report artifact
gh run download $(gh run list --limit 1 --json databaseId -q '.[0].databaseId') -n validation-report-*

# 2. Check raw extracted content
cat out/chat/$(date +%Y-%m-%d)/raw_extracted_data.txt

# 3. Check validation details
cat validation_report/results.json

# 4. Force regenerate with debug output
ENABLE_AGENT_VALIDATION=false .venv/bin/python3 mlbtr_daily_summary.py --force
```

### Task: "Emergency: Bad content is live"
```bash
# 1. Revert the last commit
git revert HEAD --no-edit
git push

# 2. Manually trigger Pages deployment
gh workflow run "Deploy to GitHub Pages"

# 3. Investigate the issue
cat out/*/$(date +%Y-%m-%d)/summary.html | grep -C 5 "error\|fail"
```

### Task: "Test the validation system"
```bash
# Create a test file with known bad content
echo '<html><body>I don\'t see any transcript provided</body></html>' > out/chat/$(date +%Y-%m-%d)/summary.html

# Run validation (should fail)
.venv/bin/python3 mlbtr_daily_summary.py --force

# Check validation caught it
grep "validation_passed" validation_report/results.json
```

---

## 🔧 Commands Reference

### Daily Operations
```bash
# Standard daily run (used by GitHub Actions)
.venv/bin/python3 mlbtr_daily_summary.py

# Force regenerate today's content
.venv/bin/python3 mlbtr_daily_summary.py --force

# Manual GitHub Actions trigger
gh workflow run "Update MLBTR Daily Digest"
```

### Development & Testing
```bash
# Test with a specific URL
.venv/bin/python3 mlbtr_daily_summary.py --manual-url "https://example.com" --manual-type chat --manual-date 2025-08-11

# Regenerate all historical content
.venv/bin/python3 mlbtr_daily_summary.py --regenerate-all --force

# Process content since specific date
.venv/bin/python3 mlbtr_daily_summary.py --since 2025-08-01

# Test with agent validation
ENABLE_AGENT_VALIDATION=true AGENT_VALIDATION_PERCENTAGE=100 GEMINI_API_KEY=your_key .venv/bin/python3 mlbtr_daily_summary.py
```

### Emergency Procedures
```bash
# Disable agent system if causing issues
ENABLE_AGENT_VALIDATION=false .venv/bin/python3 mlbtr_daily_summary.py

# Clean slate recovery
rm -rf out/chat/* out/mailbag/* chat/* mailbag/*
.venv/bin/python3 mlbtr_daily_summary.py --regenerate-all --force
cp out/index.html index.html && cp -r out/chat/* chat/ && cp -r out/mailbag/* mailbag/
git add . && git commit -m "Emergency content reset" && git push
```

---

## 🏗️ System Architecture

### Core Pipeline
```
RSS Feed → Python Processor → [Agent Validation] → Content Validation → Git Commit → GitHub Pages
    ↓            ↓                    ↓                   ↓               ↓            ↓
[MLB Trade]  [BeautifulSoup]    [Optional]      [Multi-signal]     [Atomic sync]  [Live site]
```

### Key Components

#### 1. Content Processor (`mlbtr_daily_summary.py`)
- Fetches MLB Trade Rumors RSS feed
- Extracts chat transcripts and mailbags
- Summarizes using LLM cascade (Claude → OpenAI → Gemini → Keyword fallback)
- Outputs to `out/` directory structure

#### 2. Validation Pipeline (GitHub Actions)
- **Multi-signal validation** (Sept 11, 2025 implementation):
  - File size checks (>8KB threshold)
  - Error message detection
  - DOM structure validation
  - Minimum content counts (≥2 insights)
- **Atomic file operations**: Stage → Validate → Swap
- **Concurrency control**: Prevents race conditions
- **SHA verification**: Ensures deployment correctness

#### 3. Agent System (`agent_validation.py`) - Optional
- 4-agent sequential pipeline: Extraction → Editorial → Preview → Publisher
- Circuit breaker for failure protection
- Shadow mode for testing
- Percentage-based rollout capability

### File Structure
```
out/                              # Generated content (source of truth)
├── index.html                    # Main navigation
├── chat/YYYY-MM-DD/
│   ├── summary.html             # Processed summary with insights
│   └── raw_extracted_data.txt   # Debug data
└── mailbag/YYYY-MM-DD/
    ├── summary.html
    └── raw_extracted_data.txt

chat/                             # GitHub Pages serving directory
mailbag/                          # (synced from out/ by workflow)
index.html                        # (synced from out/ by workflow)
```

---

## ⚙️ Configuration

### Environment Variables
```bash
# LLM APIs (fallback cascade)
CLAUDE_API_KEY=xxx       # Primary
OPENAI_API_KEY=xxx       # Secondary  
GEMINI_API_KEY=xxx       # Tertiary + Agent system

# Agent System Controls
ENABLE_AGENT_VALIDATION=true/false     # Master switch
AGENT_VALIDATION_PERCENTAGE=0-100      # Gradual rollout
AGENT_SHADOW_MODE=true/false          # Test without affecting output
```

### Key Configuration Points
- **Team priorities**: Edit `KEYWORDS_PRIMARY` in `mlbtr_daily_summary.py`
- **Content types**: Modify `POST_TYPES` dictionary for new content patterns
- **Validation thresholds**: Adjust in `.github/workflows/update_digest.yml`

---

## 🛡️ Production System

### Current Implementation (September 11, 2025)

#### Security & Reliability Features
1. **All GitHub Actions pinned by SHA** (supply chain security)
2. **Concurrency control** with date-scoped keys
3. **Multi-signal validation** prevents false positives
4. **Atomic file operations** prevent partial updates
5. **SHA verification** ensures correct deployment
6. **Output robustness** with safe defaults

#### Production Test Matrix
| Test | Validates | Expected Result |
|------|-----------|-----------------|
| Overlap runs | Concurrency control | One cancels cleanly |
| SHA mismatch | Deploy correctness | Deploy aborts |
| No-change day | Skip logic | No commit/deploy |
| Provider outage | LLM fallback | Cascade to next provider |
| Tiny valid post | Multi-signal validation | Publishes correctly |
| Malformed HTML | Content validation | Fails before commit |

#### Validation Gate Logic
```yaml
# The critical gate that prevents bad content
if: steps.sync.outputs.sync_success == 'true' 
    && steps.validate.outputs.validation_passed == 'true' 
    && fromJson(steps.validate.outputs.new_files_count || '0') > 0
```

---

## 🔍 Troubleshooting Guide

### Issue: Empty/Error Content on Site
**Symptoms**: Page shows "I don't see any transcript provided"

**Solution Path**:
1. This should be prevented by validation gate (Sept 11 fix)
2. If it occurs, check validation logs: `gh run view <id> --log | grep validation`
3. Likely causes: Validation gate disabled or bypassed
4. Fix: Re-enable validation, revert bad commit

### Issue: Workflow Succeeds but No Content Published
**Symptoms**: Green checkmarks in Actions but no new posts

**Check Sequence**:
```bash
# 1. Verify content generation
ls -la out/chat/$(date +%Y-%m-%d)/

# 2. Check validation results
gh run download <run-id> -n validation-report-*
cat validation_report/results.json

# 3. Check if commit occurred
git log --oneline --since="today"

# 4. Check Pages deployment
gh run list -w "Deploy to GitHub Pages" --limit 1
```

### Issue: GitHub Pages Not Updating
**Solution**: The deploy workflow should trigger automatically after successful digest workflow. If not:
```bash
# Manual trigger
gh workflow run "Deploy to GitHub Pages"

# Verify deployment SHA
gh run view <deploy-run-id> --log | grep "Expected SHA"
```

---

## 📝 Development Patterns

### Adding New Content Types
1. Add entry to `POST_TYPES` dictionary in `mlbtr_daily_summary.py`
2. Implement extraction function following `extract_transcript` pattern
3. Update `extract_content_by_type()` dispatcher
4. Test with `--manual-url` flag

### Modifying Validation Rules
Edit validation function in `.github/workflows/update_digest.yml`:
- Adjust size thresholds
- Add new error patterns
- Modify DOM selectors
- Change minimum content counts

### Testing Changes Locally
```bash
# 1. Make changes to mlbtr_daily_summary.py
# 2. Test with recent content
.venv/bin/python3 mlbtr_daily_summary.py --force

# 3. Check generated output
cat out/chat/$(date +%Y-%m-%d)/summary.html

# 4. Test validation would pass
# (Check file size, search for error messages, verify structure)
```

---

## 📊 Monitoring & Metrics

### Health Indicators
- **Workflow success rate**: Should be >95%
- **Content validation passes**: Should be 100% for valid content
- **Average file size**: Chat ~12KB, Mailbag ~10KB
- **Deployment frequency**: Daily at 22:00 UTC

### Where to Check Metrics
```bash
# Recent workflow performance
gh run list --limit 20 | grep -c "success"

# Validation history
for run in $(gh run list --limit 10 --json databaseId -q '.[].databaseId'); do
  gh run download $run -n validation-report-* 2>/dev/null && cat validation_report/results.json | jq '.validation_passed'
done

# Content generation frequency
ls -la out/chat/ | wc -l  # Total chat days
ls -la out/mailbag/ | wc -l  # Total mailbag days
```

---

## 🚨 Critical Notes

1. **NEVER** commit directly to `chat/` or `mailbag/` directories - always work in `out/` first
2. **ALWAYS** ensure validation passes before deployment
3. **GitHub Pages** serves from root, not `out/` - the workflow handles syncing
4. **SHA pinning** is critical for security - update carefully with exact SHAs
5. **Concurrency keys** prevent race conditions - include date to allow backfills

---

## 📅 Maintenance Schedule

- **Daily**: Automated content generation at 22:00 UTC
- **Weekly**: Check workflow success rate
- **Monthly**: Review and update action SHAs
- **Quarterly**: Audit validation rules and thresholds

---

## 📜 Recent Changes

### September 15, 2025
- **Fixed validation bug**: Changed insight counting from `grep -c` (counts lines) to `grep -o | wc -l` (counts occurrences)
  - Issue: Valid content with 10+ insights was failing validation because all insights were on one HTML line
  - Impact: Today's chat transcript was blocked despite having valid content
  - Status: Fix committed, manual workflow still needs investigation

### September 11, 2025
- **Production-hardened implementation**: Multi-signal validation, atomic operations, SHA verification

---

*Last updated: September 15, 2025 - Validation counting fix applied*