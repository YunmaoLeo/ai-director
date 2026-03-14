# Director Service

AI cinematic directing pipeline for Unity scenes. Generates camera directing plans from scene descriptions and user intent, then solves them into continuous camera trajectories — all without Unity.

## Architecture

```
Scene JSON → Scene Abstraction → LLM Directing Plan → Trajectory Solver → Output JSON
                                                                            ↓
                                                                    Frontend Preview
```

### Three-Layer Design

1. **Director Layer** (LLM): Interprets user intent, chooses shot sequence, defines cinematic goals, pacing, and constraints. Outputs semantic plans, not raw coordinates.

2. **Spatial Intelligence Layer** (Deterministic): Parses scene geometry, computes cinematic affordances, solves continuous camera trajectories with collision avoidance and heuristic scoring.

3. **Execution Layer** (Future Unity): Out of scope for this phase.

### Why No Unity Required

The frontend debugging tool provides a 2D top-down preview of scenes and camera trajectories. Daily iteration on directing logic, prompt engineering, and trajectory solving can happen entirely in the browser.

## Quick Start

### Backend

```bash
cd director-service

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run the pipeline via CLI
python -m app.main generate-plan \
  --scene scenes/apartment_living_room.json \
  --intent "Give me an overview of this room" \
  --mock

# Start the API server
python -m app.main serve
```

### Frontend

```bash
cd director-service/frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev
```

Open http://localhost:5173, select a scene, enter an intent, and generate a plan.

### Run Tests

```bash
cd director-service
python -m pytest tests/ -v
```

## CLI Commands

### `generate-plan`

```
python -m app.main generate-plan --scene <path> --intent <text> [--output-dir outputs] [--mock]
```

Runs the full pipeline and saves 3 JSON files to the output directory:
- `directing_plan.json` — semantic shot sequence
- `trajectory_plan.json` — solved camera trajectories with sampled points
- `validation_report.json` — structural, scene-reference, and semantic validation

### `serve`

```
python -m app.main serve [--host 0.0.0.0] [--port 8000] [--reload]
```

Starts the FastAPI server with endpoints:
- `GET /api/scenes` — list available scenes
- `GET /api/scenes/{id}` — load a scene
- `POST /api/generate` — run the pipeline (`{"scene_id": "...", "intent": "..."}`)
- `GET /api/outputs` — list output files

## Sample Scenes

| Scene | Dimensions | Objects |
|-------|-----------|---------|
| `apartment_living_room` | 6x8x3m | sofa, desk, coffee_table, lamp, window, door |
| `office_room` | 5x6x3m | desk, monitor, chair, shelf, whiteboard, window |
| `corridor_scene` | 2x12x3m | door, wall_lamp_1, wall_lamp_2, picture, end_window |

## Frontend Panels

| Panel | Purpose |
|-------|---------|
| **Scene** (A) | Scene metadata, object list, top-down object map |
| **Abstraction** (B) | Subjects, shot types, movements used |
| **Intent** (C) | Text input, generate button, example intents, history |
| **Directing Plan** (D) | Shot cards with badges, timeline bar |
| **Trajectory** (E) | Top-down canvas with trajectory overlay, per-shot metrics |
| **Output** (F) | JSON viewer, validation report, compare previous results |

## Project Structure

```
director-service/
├── app/
│   ├── main.py              # Typer CLI
│   ├── api.py               # FastAPI endpoints
│   ├── config.py             # Pydantic settings
│   ├── models/               # Pydantic data models
│   ├── services/             # Business logic
│   ├── pipelines/            # Pipeline orchestration
│   └── utils/                # Helpers (geometry, JSON, logging)
├── frontend/                 # React + TypeScript + Vite
├── prompts/                  # LLM prompt templates
├── schemas/                  # JSON Schema files
├── scenes/                   # Sample scene files
├── outputs/                  # Generated outputs
└── tests/                    # pytest test suite
```

## Current Limitations

- Uses a mock LLM client (template-based shot recipes) — real LLM integration is a pluggable extension
- Trajectory solver operates in 2.5D (XZ plane + Y height), not full 3D
- Collision avoidance uses simple AABB pushback
- Metrics are heuristic approximations
- No real-time playback — the frontend shows static trajectory previews

## Future Unity Integration

The output JSON files (`directing_plan.json`, `trajectory_plan.json`) are designed to be loaded by a Unity runtime that:
1. Reads the trajectory plan
2. Moves a camera along the sampled path points
3. Applies look-at targeting and FOV settings
4. Provides real-time playback
