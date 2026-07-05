# NWW Asana Connector Integration Guide

**Version**: 0.1.0  
**Branch**: `claude/nww-asana-connector-2gst3u`  
**Status**: Phase 5 Complete — Ready for deployment

---

## Overview

The **NWW (Nameless Wizardry Weaver) Asana Connector** is a unified reporting system that bridges three thematically-connected projects into Asana as a central coordination hub:

- **shadow-garden-launcher**: Voice synthesis and Grok chat orchestration
- **gitmynotes**: macOS Notes backup and GitHub synchronization
- **wha-spell-simulator**: Spell glyph recognition and compilation

Metrics flow to Asana in real-time + periodic aggregates, enabling cross-project visibility and "soul-resonance" alignment through custom fields and portfolios.

---

## Architecture Overview

### Shared Core Library
**Location**: `asana_connector/` (in each repo)

- **`client.py`** — Asana REST API wrapper (auth, retries, rate limiting)
- **`config.py`** — Configuration management (env vars, config files)
- **`schemas.py`** — Custom field definitions (bilingual: technical + magical)
- **`portfolio_manager.py`** — Portfolio hierarchy creation
- **`data_mapper.py`** — Metric normalization to custom fields
- **`bootstrap.py`** — Workspace initialization CLI

### Project Adapters

| Project | Adapter | Language | Metrics |
|---------|---------|----------|---------|
| shadow-garden-launcher | `adapters/asana_adapter.py` | Python | Voice quality, chat sync |
| gitmynotes | `adapters/asana_adapter.py` | Python | Sync success, audit trail |
| wha-spell-simulator | `src/adapters/asanaAdapter.js` | JavaScript | Glyph accuracy, compilation |

---

## Quick Start

### 1. Bootstrap Asana Workspace

First, set up your Asana workspace structure:

```bash
# Get your Asana Personal Access Token from: https://app.asana.com/0/my-apps
# Get your Workspace GID from: https://app.asana.com/0/<workspace-gid>

export ASANA_API_TOKEN="your-pat-token"
export ASANA_WORKSPACE_ID="your-workspace-gid"

# Run bootstrap in any of the three repos:
cd shadow-garden-launcher
python -m asana_connector.bootstrap

# Or with quiet output:
python -m asana_connector.bootstrap -q --output /tmp/nww_config.json
```

**Output**: Prints all created resource IDs and environment variables to set.

### 2. Configure Each Project

**shadow-garden-launcher/.env**:
```bash
ASANA_API_TOKEN=<your-pat-token>
ASANA_WORKSPACE_ID=<workspace-gid>
ASANA_PORTFOLIO_ID=<nww-portfolio-gid>
ASANA_PROJECT_SHADOWGARDEN=<project-gid>
```

**gitmynotes/gmn_config.yaml**:
```yaml
[asana]
api_token = <your-pat-token>
workspace_id = <workspace-gid>
portfolio_id = <nww-portfolio-gid>
project_id = <project-gid>
```

**wha-spell-simulator/.env**:
```bash
ASANA_API_TOKEN=<your-pat-token>
ASANA_WORKSPACE_ID=<workspace-gid>
ASANA_PORTFOLIO_ID=<nww-portfolio-gid>
ASANA_PROJECT_SPELLSIM=<project-gid>
```

### 3. Integrate with Project Workflows

**shadow-garden-launcher** (after `bridge.py` voice synthesis):
```python
from adapters.asana_adapter import report_synthesis_metrics

# After successful voice synthesis:
report_synthesis_metrics(
    voice="Angela",
    prompt_length=150,
    latency_ms=1200.5,
    quality_score=92.5,
)
```

**gitmynotes** (in `git_add_commit_push()` success path):
```python
from adapters.asana_adapter import report_sync_metrics

# After successful sync:
report_sync_metrics(
    folder_name="Work Notes",
    notes_processed=42,
    notes_failed=0,
    sync_duration_ms=1500.0,
    total_characters=50000,
    git_commit=commit_hash,
)
```

**wha-spell-simulator** (in glyph recognition + compilation):
```javascript
import { reportGlyphAccuracy, reportSpellCompilation } from './adapters/asanaAdapter.js';

// After glyph recognition:
await reportGlyphAccuracy({
    glyphName: "Symbol of Power",
    accuracy: 94.2,
    confidence: 96.5,
    processingTime: 125,
    strokeCount: 7,
    success: true,
});

// After spell compilation:
await reportSpellCompilation({
    lastGlyphName: "Symbol of Power",
    glyphAccuracy: 94.2,
    compilationSuccess: 97.1,
    spellsCompiled: 1,
    copyTechniquePrecision: 89.5,
});
```

---

## Asana Workspace Structure

Once bootstrapped, your Asana workspace will contain:

```
📊 NWW Unified Resonance (Portfolio)
│
├─ 🎤 Shadow-Garden Voice Resonance (Portfolio)
│  └─ 🎵 Shadow-Garden Voice Bridge (Project)
│     ├─ [Voice Synthesis: Angela - 2026-07-05]
│     ├─ [Grok Chat Sync - 2026-07-05]
│     ├─ [Daily Resonance Summary - 2026-07-05]
│     └─ ...
│
├─ 📝 GitMyNotes Technique Mastery (Portfolio)
│  └─ 📚 GitMyNotes Sync Pipeline (Project)
│     ├─ [Note Sync: Work Notes - 2026-07-05]
│     ├─ [Audit Trail: Work Notes - 2026-07-05]
│     ├─ [Daily Sync Summary - 2026-07-05]
│     └─ ...
│
└─ ✨ Spell Simulator Soul Resonance (Portfolio)
   └─ 🔮 Wha-Spell Simulator Glyph Mastery (Project)
      ├─ [Spell Compilation: Power Symbol - 2026-07-05]
      ├─ [Glyph Recognition: Power Symbol - 2026-07-05]
      ├─ [Daily Glyph Mastery Summary - 2026-07-05]
      └─ ...
```

---

## Custom Fields Reference

All custom fields use **bilingual presentation**: technical backing, magical names/descriptions.

### Shared Across All Projects

| Field | Type | Technical Meaning | Magical Meaning | Example |
|-------|------|------|------|---------|
| **Resonance Score** | Number (0-100) | Quality/accuracy metric | Soul alignment | 92.5 |
| **Technique Mastery** | Dropdown | Proficiency level | Mastery grade | "Expert" |
| **Soul Alignment** | Text | Completeness/status | Thematic descriptor | "Ascending Harmony" |
| **Last Reported** | Date | Metric timestamp | Resonance moment | 2026-07-05 |
| **Metrics JSON** | Text (hidden) | Raw data for analysis | Technical backing | `{...}` |

### Project-Specific

**Shadow-Garden Voice Bridge**:
- Resonance Score: Voice quality (0-100%)
- Technique Mastery: Synthesis proficiency

**GitMyNotes Sync Pipeline**:
- Copy Technique Success: Sync success rate (0-100%)
- Technique Mastery: Configuration complexity

**Spell Simulator Glyph Mastery**:
- Resonance Score: Glyph accuracy (0-100%)
- Copy Technique Success: Precision effectiveness (0-100%)
- Technique Mastery: Glyph mastery level

---

## Reporting Cadence

### Real-Time Events
Individual execution → Asana task created immediately

**Shadow-Garden**:
- Voice synthesis completion → Task with voice quality metrics
- Chat sync completion → Task with sync success metrics

**GitMyNotes**:
- Sync run completion → Task with note counts and success rate
- Audit trail → Comments on sync task with detailed entries

**Spell Simulator**:
- Glyph recognition → Task with accuracy metrics
- Spell compilation → Task with compilation success

### Periodic Aggregates
Batch summaries at scheduled intervals:

- Daily summaries created in each project (usually midnight)
- Weekly portfolio rollups (usually Sunday)
- Monthly trend analysis (usually month-end)

---

## Verification Checklist

Before marking Phase 5 complete, verify:

- [ ] **Authentication**: `python -m asana_connector.bootstrap` completes without errors
- [ ] **Workspace**: NWW portfolio + sub-portfolios exist in Asana
- [ ] **Projects**: All three projects created and accessible
- [ ] **Custom Fields**: All 5+ custom fields appear in project task views
- [ ] **shadow-garden**: Voice synthesis metrics flow to Asana
- [ ] **gitmynotes**: Note sync metrics and audit trails appear
- [ ] **spell-simulator**: Glyph accuracy and compilation metrics show
- [ ] **Cross-project**: All three projects visible in unified portfolio
- [ ] **Documentation**: All adapters have docstrings and examples

---

## Troubleshooting

### "ASANA_API_TOKEN not set"
Ensure token is in environment:
```bash
export ASANA_API_TOKEN="<your-token>"
# Or set in project's .env file
```

### "Invalid workspace_id"
Workspace GID format: Usually a large numeric string. Find it at:
- URL: `https://app.asana.com/0/<workspace-gid>`
- Or in browser dev console: `Asana.workspaceId`

### "403 Forbidden" on push
Workspace authentication failed. Verify:
- [ ] Token is valid (test at app.asana.com/0/my-apps)
- [ ] Token has "workspace" and "task:write" scopes
- [ ] Token belongs to workspace owner/admin

### Tasks not appearing in Asana
Check adapter logs:
```bash
# Python adapters
python -c "from adapters.asana_adapter import ShadowGardenAsanaReporter; \
    r = ShadowGardenAsanaReporter(); print('Connected!' if r.health_check() else 'Failed')"

# JavaScript adapters (in Node.js)
node -e "import('./src/adapters/asanaAdapter.js').then(m => \
    new m.SpellSimulatorAsanaReporter().healthCheck().then(r => \
    console.log(r ? 'Connected!' : 'Failed')))"
```

### Rate limiting (429 errors)
Asana allows ~50 requests/min per token. The client retries automatically with exponential backoff. If persistent:
- Space out metric reports (batch instead of real-time)
- Use aggregate-only mode (disable individual event reporting)

---

## Development & Extension

### Adding a New Project

1. Create `adapters/asana_adapter.py` or `src/adapters/asanaAdapter.js` in your project
2. Copy pattern from existing adapters (shadow-garden, gitmynotes, or spell-simulator)
3. Update `AsanaConfig.project_ids` to include your project key
4. Add project-specific convenience function for reporting
5. Bootstrap creates new project automatically via `PortfolioManager.create_nww_projects()`

### Adding a New Custom Field

1. Add field definition to `asana_connector/schemas.py`:
```python
"new_field": {
    "name": "Display Name",
    "type": "number",  # or "text", "date", "enum"
    "description": "Technical: ... Magical: ...",
}
```

2. Add project-specific entry to `PROJECT_FIELD_MAPS`
3. Add mapper method to `asana_connector/data_mapper.py`
4. Re-run bootstrap: `python -m asana_connector.bootstrap`

### Testing Adapters

```bash
# Python
python -c "from adapters.asana_adapter import report_synthesis_metrics; \
    print(report_synthesis_metrics(voice='Test', prompt_length=100, \
    latency_ms=500, quality_score=85))"

# JavaScript (Node.js)
node -e "import('./src/adapters/asanaAdapter.js').then(m => \
    m.reportGlyphAccuracy({glyphName: 'Test', accuracy: 85, \
    confidence: 90, processingTime: 100, strokeCount: 5, success: true}))"
```

---

## Architecture Decisions

### Why Bilingual Fields?
Technical backing allows programmatic analysis (ML, aggregation). Magical presentation makes Asana UI delightful and thematic.

### Why Shared Core?
Reduces duplication. Updates to API client, retry logic, or field schemas benefit all three projects instantly.

### Why Hybrid Reporting (Real-time + Aggregates)?
- Real-time: Immediate insight into execution failures
- Aggregates: Trend analysis, weekly/monthly reports without noise

### Why Custom Fields Over Templates?
Custom fields are universally queryable and aggregatable across projects. Templates are just task names/descriptions.

---

## Future Enhancements

- [ ] Portfolio rollup dashboard (aggregate metrics from all three projects)
- [ ] Slack integration (post summaries to #nww-resonance channel)
- [ ] GitHub Actions CI/CD integration (auto-report test metrics)
- [ ] Historical data backfill (import past sync/voice logs)
- [ ] Machine learning insights (anomaly detection, trend prediction)
- [ ] Browser extension (quick-capture glyph accuracy from spell-simulator UI)
- [ ] Mobile app integration (report on-the-go)

---

## Support & Contact

For issues or questions:
1. Check troubleshooting section above
2. Review adapter docstrings and README files in each repo
3. Run health checks: `<project>_adapter.health_check()`
4. Check Asana workspace for connectivity errors in task comments

---

## License

Part of the NWW integration suite. See individual project READMEs for details.
