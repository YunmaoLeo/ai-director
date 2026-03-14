"""FastAPI endpoints for the director service."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.pipelines.generate_plan_pipeline import GeneratePlanPipeline
from app.services.file_manager import FileManager
from app.utils.json_utils import load_json, pydantic_to_json

api_app = FastAPI(title="Director Service API", version="0.1.0")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_file_manager = FileManager(settings.output_dir)


class GenerateRequest(BaseModel):
    scene_id: str
    intent: str


class GenerateResponse(BaseModel):
    directing_plan: dict
    trajectory_plan: dict
    validation_report: dict


@api_app.get("/api/scenes")
def list_scenes():
    """List available scene files."""
    return _file_manager.list_scenes(settings.scenes_dir)


@api_app.get("/api/scenes/{scene_id}")
def get_scene(scene_id: str):
    """Load a specific scene by ID."""
    scenes_dir = Path(settings.scenes_dir)
    # Search for scene file matching the ID
    for f in scenes_dir.glob("*.json"):
        try:
            data = load_json(f)
            if data.get("scene_id") == scene_id:
                return data
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found")


@api_app.post("/api/generate", response_model=GenerateResponse)
def generate_plan(req: GenerateRequest):
    """Run the full pipeline: scene → plan → trajectory → validation."""
    scenes_dir = Path(settings.scenes_dir)
    scene_path = None
    for f in scenes_dir.glob("*.json"):
        try:
            data = load_json(f)
            if data.get("scene_id") == req.scene_id:
                scene_path = f
                break
        except Exception:
            continue

    if scene_path is None:
        raise HTTPException(status_code=404, detail=f"Scene '{req.scene_id}' not found")

    pipeline = GeneratePlanPipeline(
        llm_provider="mock",
        output_dir=str(settings.output_dir),
        scenes_dir=str(settings.scenes_dir),
    )

    try:
        result = pipeline.run(str(scene_path), req.intent, save=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return GenerateResponse(
        directing_plan=pydantic_to_json(result.directing_plan),
        trajectory_plan=pydantic_to_json(result.trajectory_plan),
        validation_report=pydantic_to_json(result.validation_report),
    )


@api_app.get("/api/outputs")
def list_outputs():
    """List saved output files."""
    return _file_manager.list_outputs()


@api_app.get("/api/outputs/{filename}")
def get_output(filename: str):
    """Get a specific output file."""
    path = Path(settings.output_dir) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Output '{filename}' not found")
    return load_json(path)
