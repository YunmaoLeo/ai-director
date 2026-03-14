# Project Specification for Code Agent
# Project Name: director-service
# Language Requirement: All source code, comments, identifiers, filenames, logs, schemas, and internal documentation must be in English only.

## 1. Project Context

We are building an AI Director system for a Unity-based static scene project.

The full repository contains two top-level folders:

- `director-service/` -> Python-based planning and debugging tools
- `unity-director-scene/` -> Unity project for future scene playback and camera execution

At this stage, focus on `director-service` only.

Do NOT implement Unity integration yet.

The purpose of `director-service` is to generate a structured cinematic directing plan from:
1. a user intent
2. a structured scene summary

The service should also support a fast local debugging workflow through a frontend preview tool, so that daily development does not depend on launching Unity.

---

## 2. Core Goal

Build a standalone Python project named `director-service` that can:

1. Load a scene summary JSON file
2. Accept a user intent
3. Build an LLM prompt
4. Generate a structured directing plan
5. Validate the plan
6. Convert the plan into a continuous camera trajectory specification
7. Save outputs as JSON
8. Provide a local frontend debugging tool for quick iteration and preview
9. Be developed and tested without Unity

This is an offline planning and preview system for now, not a real-time runtime control system.

---

## 3. Product Vision

We do NOT want a node-selection camera system based on manually authored candidate camera points.

Instead, we want a more AI-driven approach:

- the scene is described structurally
- the LLM acts as a high-level director
- the system computes cinematic affordances from scene geometry and semantics
- a trajectory solver generates actual continuous camera paths

The LLM should not output arbitrary raw transforms directly as the primary logic source.
It should output cinematic goals, shot semantics, motion intentions, and constraints.

The lower-level planning system should translate that output into continuous camera movement.

---

## 4. Main Design Principle

The LLM should not be responsible for precise geometric computation.

Instead, the system should separate responsibilities into three layers:

### 4.1 Director Layer
Handled by the LLM.

Responsibilities:
- interpret user intent
- choose cinematic goals
- decide shot order
- choose pacing
- define motion style
- define composition constraints
- define subject focus
- define reveal / emphasis strategy

### 4.2 Spatial Intelligence Layer
Handled by deterministic algorithms and heuristics.

Responsibilities:
- parse scene summary
- reason about free space
- reason about visibility
- reason about occlusion risk
- derive cinematic affordances for objects and regions
- compute feasible camera poses
- solve continuous trajectories

### 4.3 Execution Layer
Out of scope for now, future Unity responsibility.

Responsibilities:
- load directing plan and solved trajectory
- move the camera
- provide runtime playback

For this phase, build only Layer 1 and Layer 2, plus a frontend debugging tool.

---

## 5. Required Development Direction

We explicitly do NOT want:
- manually placed candidate camera nodes as the core planning mechanism
- an LLM that only selects from fixed camera points
- Unity-only debugging workflow

We DO want:
- continuous-space camera planning
- object-aware cinematic reasoning
- scene affordance analysis
- fast browser-based or local frontend-based preview tooling

---

## 6. System Overview

The `director-service` should have the following pipeline:

### Step 1: Load Scene Summary
Load a structured JSON description of a scene.

### Step 2: Build Scene Cinematic Abstraction
From the scene summary, derive a more cinematic representation:
- semantic regions
- important objects
- object relations
- approximate free space
- visibility characteristics
- suggested composition affordances
- region-level and object-level filming opportunities

### Step 3: Intent Interpretation
Take the user's intent, such as:
- "Give me an overall preview of this room"
- "Reveal the window after focusing on the desk"
- "Create a slow cinematic exploration of the room"

### Step 4: LLM Directing Plan
The LLM generates a high-level directing plan:
- shot sequence
- cinematic goals
- subject focus
- movement intent
- pacing
- shot constraints

### Step 5: Plan Validation
Validate:
- structural schema
- scene references
- semantic consistency
- duration sanity
- allowed enums
- object targets existence

### Step 6: Trajectory Solving
Convert each shot intent into a feasible continuous camera trajectory.
The solver should use:
- scene bounds
- free-space constraints
- visibility heuristics
- subject framing goals
- smoothness constraints
- motion style constraints

### Step 7: Save Outputs
Save:
- raw directing plan
- solved trajectory plan
- validation report

### Step 8: Frontend Preview
Provide a frontend debugging UI for:
- loading scene summary
- entering intent
- running generation
- viewing shot sequence
- viewing JSON output
- viewing an approximate top-down trajectory preview
- viewing object layout and camera route overlay
- comparing multiple generated plans quickly

---

## 7. Continuous-Space Planning Approach

The project must not depend on pre-authored camera nodes.

Instead, use a continuous-space planning approach.

The input scene should provide enough structural information for the system to derive:
- room bounds
- major object positions
- free space approximations
- target regions
- directional relationships

The directing plan should remain semantic.
The actual camera poses and path points should be solved later.

This means:

### The LLM should output:
- what to show
- in what order
- how to move
- what to emphasize
- what to avoid
- pacing and mood constraints

### The solver should determine:
- actual camera positions
- actual path curves
- exact heading/orientation
- valid distances
- valid heights
- smooth timing-compatible motion

---

## 8. Example of Desired Division of Labor

### LLM output example
A shot may say:

- goal: establish the room layout
- subject: room
- shot_type: wide
- movement: slow_forward
- duration: 4.0
- constraints:
  - keep sofa, desk, and window visible
  - avoid high angle
  - maintain calm pacing

### Solver output example
The solver may compute:

- start_position: [x1, y1, z1]
- end_position: [x2, y2, z2]
- look_at_target: [x3, y3, z3]
- fov: 55
- path_type: bezier
- sampled_path_points: [...]
- average_speed: ...
- visibility_score: ...
- smoothness_score: ...

This separation is essential.

---

## 9. Development Scope for This Phase

Implement the `director-service` as a standalone Python project with:

- schemas and models
- sample scene files
- cinematic abstraction pipeline
- prompt builder
- LLM client abstraction
- directing plan generator
- validator
- trajectory solver
- output persistence
- frontend debugging tool
- tests
- documentation

Do not implement Unity integration yet.

---

## 10. Recommended Project Structure

Create the following structure under `director-service/`:

director-service/
- app/
  - __init__.py
  - main.py
  - config.py
  - models/
    - __init__.py
    - enums.py
    - scene_summary.py
    - cinematic_scene.py
    - directing_plan.py
    - trajectory_plan.py
    - validation_report.py
  - services/
    - __init__.py
    - prompt_builder.py
    - llm_client.py
    - directing_plan_generator.py
    - plan_validator.py
    - scene_abstraction.py
    - affordance_analyzer.py
    - trajectory_solver.py
    - file_manager.py
  - pipelines/
    - __init__.py
    - generate_plan_pipeline.py
  - utils/
    - __init__.py
    - logger.py
    - json_utils.py
    - geometry_utils.py
- frontend/
  - package.json
  - src/
    - main.tsx
    - App.tsx
    - components/
    - panels/
    - lib/
    - types/
  - public/
- prompts/
  - system_prompt.txt
  - user_prompt_template.txt
- schemas/
  - scene_summary.schema.json
  - cinematic_scene.schema.json
  - directing_plan.schema.json
  - trajectory_plan.schema.json
- scenes/
  - apartment_living_room.json
  - office_room.json
  - corridor_scene.json
- outputs/
  - .gitkeep
- tests/
  - test_scene_abstraction.py
  - test_prompt_builder.py
  - test_plan_validator.py
  - test_trajectory_solver.py
  - test_pipeline.py
- .env.example
- .gitignore
- README.md
- pyproject.toml

---

## 11. Technology Recommendations

### Backend
Use:
- Python 3.11+
- pydantic v2
- typer for CLI
- pytest for tests

Optional:
- FastAPI later if needed
- numpy if helpful for geometry calculations
- shapely only if truly necessary; avoid over-complicating geometry early

### Frontend
Use a lightweight local development stack:
- React
- TypeScript
- Vite

The frontend is for debugging and preview only, not for final product polish.

---

## 12. Frontend Debugging Tool Requirement

A frontend debugging tool is required because development should not depend on Unity for every iteration.

This tool is important and should be treated as part of the MVP.

### The frontend should support:

1. Load a scene summary file
2. Display parsed scene information
3. Show objects and room bounds in a simplified top-down view
4. Enter or edit an intent
5. Trigger plan generation
6. Display the generated directing plan
7. Display the solved trajectory plan
8. Show a top-down 2D preview of the camera route
9. Show object positions and camera route overlay
10. Let the user inspect shots individually
11. Let the user compare multiple generated outputs
12. Allow quick reruns without Unity

### Frontend goals
The frontend is for:
- debugging scene understanding
- debugging prompting
- debugging plan structure
- debugging trajectory solving
- visually inspecting whether the generated route is plausible

### Frontend non-goals
The frontend does not need:
- 3D rendering
- photoreal graphics
- Unity-level playback
- advanced animation polish

A clean 2D top-down scene and trajectory preview is enough for the first version.

---

## 13. Scene Summary Design

The scene summary is the structured description of the scene.
It should remain compact and semantic.

Implement a Pydantic model named `SceneSummary`.

### Required top-level fields
- scene_id: string
- scene_name: string
- scene_type: string
- description: string
- bounds: object
- objects: array
- relations: array
- free_space: optional simplified region data

### Bounds
Fields:
- width: float
- length: float
- height: float

### SceneObject
Fields:
- id: string
- name: string
- category: string
- position: [float, float, float]
- size: [float, float, float]
- forward: optional [float, float, float]
- importance: float
- tags: list[string] = optional

### SpatialRelation
Fields:
- type: string
- source: string
- target: string

### FreeSpace
Keep this simple in the first version.
It may contain:
- walkable_regions
- blocked_regions
- preferred_open_regions

Do not over-engineer real navigation yet.

---

## 14. Cinematic Scene Abstraction

Implement a derived representation called `CinematicScene`.

This is generated from `SceneSummary` and is used as a better LLM input.

`CinematicScene` should include:

- scene_id
- semantic_regions
- primary_subjects
- secondary_subjects
- object_groups
- spatial_summary
- cinematic_affordances
- visibility_hints
- framing_hints

### Example derived concepts
- entrance area
- desk area
- seating area
- window area
- likely overview regions
- good reveal subjects
- detail-worthy objects
- objects with strong contextual relationships

This representation should be more useful to the LLM than raw object lists.

---

## 15. Affordance Analysis

Implement a service named `affordance_analyzer.py`.

Its purpose is to derive cinematic opportunities from scene structure.

Examples:
- window is suitable for reveal and backlit framing
- desk is suitable for medium and detail framing
- sofa area is suitable for anchored composition
- room center supports overall layout coverage
- doorway-facing direction may support layered framing

These affordances may initially be generated through rules and heuristics.
Do not wait for advanced ML.

The goal is to translate raw scene layout into director-friendly hints.

---

## 16. Directing Plan Design

Implement a Pydantic model named `DirectingPlan`.

This is the semantic high-level output of the LLM.

### Top-level fields
- plan_id: string
- scene_id: string
- intent: string
- summary: string
- total_duration: float
- shots: list[Shot]

### Shot fields
- shot_id: string
- goal: string
- subject: string
- shot_type: string
- movement: string
- duration: float
- pacing: string
- constraints: object
- rationale: string

### Suggested enums

ShotType:
- establishing
- wide
- medium
- close_up
- detail
- reveal

Movement:
- static
- slow_forward
- slow_backward
- lateral_slide
- arc
- pan
- orbit

Pacing:
- calm
- steady
- dramatic
- deliberate

### Constraint examples
- keep_objects_visible
- avoid_high_angle
- avoid_occlusion
- preserve_context
- end_on_subject
- maintain_room_readability

The LLM must not output final numeric path points in this model.

---

## 17. Trajectory Plan Design

Implement a Pydantic model named `TrajectoryPlan`.

This is the solved continuous camera plan derived from the directing plan.

### Top-level fields
- plan_id: string
- scene_id: string
- total_duration: float
- trajectories: list[ShotTrajectory]

### ShotTrajectory fields
- shot_id: string
- start_position: [float, float, float]
- end_position: [float, float, float]
- look_at_position: [float, float, float]
- fov: float
- path_type: string
- sampled_points: list[[float, float, float]]
- duration: float
- metrics: object

### Metrics examples
- visibility_score
- smoothness_score
- framing_score
- occlusion_risk
- clearance_score

The frontend should be able to visualize this plan.

---

## 18. Planning Strategy

Use this pipeline:

### 18.1 Scene abstraction
Convert the raw scene summary into a cinematic scene representation.

### 18.2 Intent to directing plan
Use the LLM to generate a semantic directing plan.

### 18.3 Directing plan to trajectory
Use deterministic solving to compute actual camera motion.

This separation is required.

Do not collapse everything into one LLM call that produces arbitrary coordinates.

---

## 19. LLM Integration Strategy

Implement an abstraction in `llm_client.py`.

The rest of the system must not depend on a specific model provider.

Provide:
- a mock implementation for local testing
- a pluggable real implementation for later

### Prompt files
Create:
- `prompts/system_prompt.txt`
- `prompts/user_prompt_template.txt`

The prompt should instruct the LLM to:
- act as a cinematic director
- reason only from the provided scene abstraction
- produce a coherent semantic shot plan
- avoid inventing scene elements
- output structured JSON only
- avoid low-level numeric camera transforms

---

## 20. Trajectory Solver Requirements

Implement `trajectory_solver.py`.

This solver should convert semantic shots into continuous trajectories.

The first version can be heuristic and approximate.
It does not need to be physically perfect.

### Solver responsibilities
- find reasonable start and end positions
- maintain subject visibility
- preserve motion smoothness
- satisfy shot style constraints
- avoid obviously implausible paths
- generate sampled path points for visualization

### Solver notes
The first version can operate in simplified 2D or 2.5D space.
A top-down approximation is acceptable for MVP.

Do not over-complicate with full robotics planning in version 1.

---

## 21. Validation Rules

Implement `plan_validator.py`.

Validation should check:

### Structural validation
- required fields
- enum validity
- positive durations
- correct references

### Scene reference validation
- subject references exist
- referenced objects exist
- scene_id matches input scene

### Semantic validation
- summary is present
- at least one shot exists
- intent is preserved
- shot sequence is coherent enough

### Trajectory validation
- sampled points exist
- duration is positive
- fov is in an allowed range
- path is inside broad scene bounds if possible

Return:
- success flag
- errors
- warnings

---

## 22. CLI Requirements

Implement a Typer-based CLI in `app/main.py`.

### Required command
`generate-plan`

Arguments:
- `--scene` path to scene summary JSON
- `--intent` text instruction
- `--output-dir` optional output directory
- `--mock` optional flag for mock LLM mode

### Expected behavior
The command should:
1. load scene summary
2. derive cinematic scene abstraction
3. generate directing plan
4. validate directing plan
5. solve trajectory plan
6. validate trajectory plan
7. save outputs
8. print result summary

### Expected output files
Store:
- directing_plan.json
- trajectory_plan.json
- validation_report.json

---

## 23. Frontend Requirements

Implement a lightweight local frontend for rapid debugging.

### Recommended pages or panels

#### Panel A: Scene Viewer
- show scene metadata
- show object list
- show object categories
- show spatial relations
- show a top-down map of the room

#### Panel B: Cinematic Abstraction Viewer
- show semantic regions
- show primary subjects
- show affordances
- show derived scene summary for the LLM

#### Panel C: Intent Input
- text box for user intent
- run button
- history of previous intents

#### Panel D: Directing Plan Viewer
- show shots in order
- show shot types
- show subjects
- show durations
- show rationales

#### Panel E: Trajectory Preview
- top-down 2D path visualization
- shot-colored path segments
- object positions
- look target markers
- approximate camera direction indicators

#### Panel F: Output Inspector
- raw JSON viewer
- validation report viewer
- compare last N outputs

### Frontend technical notes
A simple local frontend is enough.
This tool is for iteration speed, not final polish.

---

## 24. Sample Data Requirements

Create at least 3 sample scene files:

### apartment_living_room.json
Include:
- sofa
- desk
- coffee table
- lamp
- window
- door

### office_room.json
Include:
- desk
- monitor
- chair
- shelf
- whiteboard
- window

### corridor_scene.json
Include:
- door
- wall lamp
- framed picture
- endpoint
- narrow hallway structure

Also create at least 3 sample intents per scene in documentation or test fixtures.

---

## 25. Testing Requirements

Use pytest.

Implement at least:

### test_scene_abstraction.py
Test that scene abstraction produces:
- semantic regions
- primary subjects
- affordances

### test_prompt_builder.py
Test that prompt construction includes:
- intent
- cinematic scene abstraction
- output rules

### test_plan_validator.py
Test valid and invalid directing plans.

### test_trajectory_solver.py
Test that the solver returns:
- valid sampled points
- valid duration
- scene-bounded path approximations

### test_pipeline.py
Test the end-to-end flow in mock mode:
- load scene
- abstract scene
- generate plan
- solve trajectory
- validate
- save

---

## 26. README Requirements

Write a clear English README.md.

It should explain:
- project purpose
- architecture
- why Unity is not required for daily iteration
- how to run backend CLI
- how to run frontend
- sample workflow
- current limitations
- future Unity integration direction

---

## 27. Implementation Priorities

Build in this order:

### Phase 1
- project structure
- core models
- sample scenes
- schemas

### Phase 2
- scene abstraction
- affordance analysis
- prompt builder
- mock LLM client

### Phase 3
- directing plan generator
- validator
- trajectory solver
- output persistence

### Phase 4
- CLI
- frontend preview tool
- tests
- README

### Phase 5
- optional real LLM integration hooks

Do not begin with Unity or advanced rendering.

---

## 28. Non-Goals for This Phase

Do NOT implement:
- Unity runtime integration
- Cinemachine integration
- final production UI
- real-time camera control
- full 3D renderer in the debug frontend
- physics-accurate path planning
- authentication
- database
- cloud deployment

---

## 29. Code Quality Expectations

The code must be:
- modular
- typed where practical
- testable
- readable
- easy to extend

Avoid:
- hardcoded provider logic everywhere
- giant monolithic files
- premature optimization
- over-complex geometry systems in v1

---

## 30. Expected First Deliverable

The first usable deliverable should support this workflow:

1. run the frontend locally
2. load a sample scene
3. inspect the scene abstraction
4. enter an intent
5. generate a semantic directing plan
6. solve a continuous trajectory plan
7. inspect the route in a top-down preview
8. inspect validation results
9. save outputs to disk

This deliverable must work without Unity.

---

## 31. Final Instruction to the Agent

Please scaffold and implement the full `director-service` project according to this specification.

Start with:
1. project structure
2. backend models and schemas
3. sample scene files
4. scene abstraction and affordance analysis
5. mock directing plan generation
6. trajectory solving
7. CLI
8. frontend debug preview tool
9. tests
10. README

All implementation content must be in English only.
