# NWW Asana Connector

Unified reporting bridge for shadow-garden-launcher, gitmynotes, and wha-spell-simulator. Enables thematic project metrics to flow into Asana as portfolios, projects, tasks, and custom-field tracked "magical resonance."

## Architecture

### Shared Core Library
- **`client.py`**: Asana REST API wrapper with auth, retries, and rate limiting
- **`config.py`**: Configuration management from env vars and config files
- **`schemas.py`**: Custom field definitions (bilingual: technical + magical)
- **`portfolio_manager.py`**: Creates and organizes portfolio hierarchy
- **`data_mapper.py`**: Converts project metrics to Asana custom fields
- **`bootstrap.py`**: Workspace initialization script

### Project-Specific Adapters (in each repo)
- `shadow-garden-launcher/adapters/asana_adapter.py` — Voice synthesis metrics
- `gitmynotes/adapters/asana_adapter.py` — Note sync & audit trail
- `wha-spell-simulator/src/adapters/asana_adapter.js` — Glyph mastery tracking

## Setup

### 1. Prerequisites
- Asana workspace (free or enterprise)
- Asana Personal Access Token: https://app.asana.com/0/my-apps
- Python 3.8+ (for shared core)

### 2. Install Dependencies
```bash
pip install requests
```

### 3. Bootstrap Asana Workspace
Run the bootstrap script to create portfolios, projects, and custom fields:

```bash
export ASANA_API_TOKEN=<your-pat-token>
export ASANA_WORKSPACE_ID=<workspace-gid>

python -m asana_connector.bootstrap
```

This will:
- ✅ Create NWW Unified Resonance portfolio (top-level)
- ✅ Create three sub-portfolios (Voice, Notes, Spells)
- ✅ Create three projects (one per repo)
- ✅ Create all custom fields
- ✅ Print environment variables to set in each project

### 4. Configure Each Project
After bootstrap, set the printed environment variables in each project:

**shadow-garden-launcher/.env:**
```
ASANA_API_TOKEN=<your-pat-token>
ASANA_WORKSPACE_ID=<workspace-gid>
ASANA_PORTFOLIO_ID=<nww-portfolio-gid>
ASANA_PROJECT_SHADOWGARDEN=<project-gid>
```

**gitmynotes/gmn_config.yaml:**
```yaml
[asana]
api_token = <your-pat-token>
workspace_id = <workspace-gid>
portfolio_id = <nww-portfolio-gid>
project_id = <project-gid>
```

**wha-spell-simulator/.env:**
```
ASANA_API_TOKEN=<your-pat-token>
ASANA_WORKSPACE_ID=<workspace-gid>
ASANA_PORTFOLIO_ID=<nww-portfolio-gid>
ASANA_PROJECT_SPELLSIM=<project-gid>
```

## Usage in Adapters

### Python Example (shadow-garden, gitmynotes)
```python
from asana_connector import AsanaClient, AsanaConfig, DataMapper

# Load config from env vars
config = AsanaConfig()
client = AsanaClient(config.api_token, config.workspace_id)
mapper = DataMapper(field_ids={...})  # from bootstrap output

# Create a task with metrics
custom_fields = mapper.map_shadow_garden_metrics(
    voice_quality_score=92.5,
    chat_sync_success_rate=98.0,
    total_messages=150,
)

task = client.create_task(
    name="Voice Resonance Report - 2026-07-05",
    project_id=config.project_ids["shadow_garden"],
    description="Real-time voice synthesis metrics from today's runs",
    custom_fields=custom_fields,
)
```

### JavaScript Example (spell-simulator)
```javascript
// See wha-spell-simulator/src/adapters/asana_adapter.js
import { AsanaClient } from '../../../asana_connector/client.js';

const client = new AsanaClient(process.env.ASANA_API_TOKEN, process.env.ASANA_WORKSPACE_ID);
const metrics = {
    glyphAccuracy: 94.2,
    compilationSuccess: 97.1,
    spellsCompiled: 42,
    copyTechniquePrecision: 89.5,
};

await client.createTask(
    `Glyph Mastery Report - ${new Date().toISOString().split('T')[0]}`,
    process.env.ASANA_PROJECT_SPELLSIM,
    { customFields: mapper.mapSpellSimulatorMetrics(metrics) }
);
```

## Custom Fields

All custom fields use "bilingual" presentation: technical backing, magical names/descriptions.

| Field | Type | Technical Meaning | Magical Meaning |
|-------|------|------------------|-----------------|
| Resonance Score | Number (0-100) | Quality/performance metric | Soul alignment coefficient |
| Technique Mastery | Dropdown | Optimization level | Mastery grade (Novice→Master) |
| Soul Alignment | Text | Feature completeness | Thematic resonance descriptor |
| Copy Technique Success | Number (0-100%) | Sync/replication success | Technique precision |
| Last Reported | Date | Metric timestamp | When the resonance was measured |
| Metrics JSON | Text (hidden) | Raw metric blob | Technical backing data |

## Asana Structure

```
NWW Unified Resonance (Portfolio)
├── Shadow-Garden Voice Resonance (Portfolio)
│   └── Shadow-Garden Voice Bridge (Project)
├── GitMyNotes Technique Mastery (Portfolio)
│   └── GitMyNotes Sync Pipeline (Project)
└── Spell Simulator Soul Resonance (Portfolio)
    └── Wha-Spell Simulator Glyph Mastery (Project)
```

## Reporting Cadence

**Real-time + Aggregates (Hybrid)**
- Individual execution events → Asana tasks immediately
- Periodic (daily/weekly) rollup summaries
- Portfolio-level aggregate views

## Testing

```bash
# Test Asana connection
python -c "from asana_connector import AsanaClient, AsanaConfig; \
    config = AsanaConfig(); \
    client = AsanaClient(config.api_token, config.workspace_id); \
    print('✅ Connected!') if client.test_connection() else print('❌ Failed')"
```

## Troubleshooting

**"ASANA_API_TOKEN not set"**
- Ensure `ASANA_API_TOKEN` env var is set or pass via constructor
- Get token at: https://app.asana.com/0/my-apps

**"Invalid workspace_id"**
- Check `ASANA_WORKSPACE_ID` is correct (find at app.asana.com/0/<workspace-id>)
- Ensure PAT has access to workspace

**Rate limiting (429 errors)**
- Asana allows ~50 requests/min per token
- Client retries automatically with exponential backoff
- Check logs if persistent

## Development

### Running Bootstrap with Custom Config
```bash
python -m asana_connector.bootstrap \
    --token $ASANA_API_TOKEN \
    --workspace $ASANA_WORKSPACE_ID \
    --output /tmp/nww_config.json
```

### Testing API Client
```python
from asana_connector import AsanaClient

client = AsanaClient(api_token, workspace_id)

# List projects
projects = client.list_projects()
for p in projects:
    print(f"{p['name']} ({p['gid']})")

# Create a test task
task = client.create_task("Test Task", project_id)
print(f"Created: {task['gid']}")
```

## License
Part of the NWW integration suite. See main project README for details.
