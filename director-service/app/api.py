"""FastAPI endpoints for the director service."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.models.scene_summary import SceneSummary
from app.pipelines.generate_plan_pipeline import GeneratePlanPipeline
from app.services.file_manager import FileManager
from app.services.llm_client import resolve_openai_chat_model, recommended_openai_chat_models
from app.utils.json_utils import load_json, pydantic_to_json

api_app = FastAPI(title="Director Service API", version="0.1.0")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_file_manager = FileManager(settings.output_dir, settings.scenes_dir)


class GenerateRequest(BaseModel):
    scene_id: str
    intent: str
    llm_provider: str | None = None
    llm_model: str | None = None


class GenerateResponse(BaseModel):
    directing_plan: dict
    trajectory_plan: dict
    validation_report: dict
    debug_scene_id: str | None = None
    debug_scene_file: str | None = None
    output_prefix: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_model_requested: str | None = None
    source_api: str | None = None
    saved_at: str | None = None


class VisionAnalysis(BaseModel):
    provider: str = "openai"
    model: str | None = None
    prompt: str | None = None
    analysis_text: str | None = None
    image_data_url: str | None = None


class UnityGenerateRequest(BaseModel):
    scene_id: str
    intent: str
    scene_summary: dict[str, Any]
    vision_analysis: VisionAnalysis | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


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

    llm_provider = req.llm_provider or settings.llm_provider
    llm_model_requested = req.llm_model or settings.llm_model
    llm_model = resolve_openai_chat_model(llm_model_requested) if llm_provider == "openai" else llm_model_requested
    pipeline = GeneratePlanPipeline(
        llm_provider=llm_provider,
        llm_model=llm_model,
        output_dir=str(settings.output_dir),
        scenes_dir=str(settings.scenes_dir),
    )
    prefix = _file_manager.build_run_prefix(req.scene_id)

    try:
        result = pipeline.run(str(scene_path), req.intent, save=True, prefix=prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    metadata = {
        "scene_id": req.scene_id,
        "intent": req.intent,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_model_requested": llm_model_requested,
        "source_api": "generate",
    }
    metadata_path = _file_manager.save_run_metadata(prefix, metadata)
    saved_at = load_json(metadata_path).get("created_at")

    return GenerateResponse(
        directing_plan=pydantic_to_json(result.directing_plan),
        trajectory_plan=pydantic_to_json(result.trajectory_plan),
        validation_report=pydantic_to_json(result.validation_report),
        output_prefix=prefix,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_model_requested=llm_model_requested,
        source_api="generate",
        saved_at=saved_at,
    )


@api_app.post("/api/unity/generate", response_model=GenerateResponse)
def generate_plan_from_unity(req: UnityGenerateRequest):
    """Save a Unity scene snapshot, then run the full pipeline using the uploaded scene."""
    llm_provider = req.llm_provider or settings.llm_provider
    llm_model_requested = req.llm_model or settings.llm_model
    llm_model = resolve_openai_chat_model(llm_model_requested) if llm_provider == "openai" else llm_model_requested
    pipeline = GeneratePlanPipeline(
        llm_provider=llm_provider,
        llm_model=llm_model,
        output_dir=str(settings.output_dir),
        scenes_dir=str(settings.scenes_dir),
    )

    try:
        scene = SceneSummary.model_validate(req.scene_summary)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid scene_summary: {e}")

    prefix = _file_manager.build_run_prefix(scene.scene_id, "unity")
    debug_scene_id = prefix.rstrip("_")
    scene.scene_id = debug_scene_id
    if scene.scene_name == "Unity Scene":
        scene.scene_name = f"Unity Snapshot {debug_scene_id}"

    if req.vision_analysis and req.vision_analysis.analysis_text:
        vision_text = req.vision_analysis.analysis_text.strip()
        if vision_text:
            scene.description = (
                f"{scene.description}\n\nVision analysis:\n{vision_text}"
                if scene.description
                else f"Vision analysis:\n{vision_text}"
            )

    debug_scene_path = _file_manager.save_scene_summary(scene)

    try:
        result = pipeline.run_scene(scene, req.intent, save=True, prefix=prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    metadata = {
        "scene_id": req.scene_id,
        "intent": req.intent,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_model_requested": llm_model_requested,
        "source_api": "unity_generate",
        "debug_scene_id": scene.scene_id,
        "debug_scene_file": debug_scene_path.name,
    }
    metadata_path = _file_manager.save_run_metadata(prefix, metadata)
    saved_at = load_json(metadata_path).get("created_at")

    return GenerateResponse(
        directing_plan=pydantic_to_json(result.directing_plan),
        trajectory_plan=pydantic_to_json(result.trajectory_plan),
        validation_report=pydantic_to_json(result.validation_report),
        debug_scene_id=scene.scene_id,
        debug_scene_file=debug_scene_path.name,
        output_prefix=prefix,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_model_requested=llm_model_requested,
        source_api="unity_generate",
        saved_at=saved_at,
    )


@api_app.get("/api/runs")
def list_runs():
    """List saved run bundles."""
    return _file_manager.list_runs()


@api_app.get("/api/runs/{prefix}", response_model=GenerateResponse)
def get_run(prefix: str):
    """Load a saved run bundle by output prefix."""
    try:
        bundle = _file_manager.load_run_bundle(prefix)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return GenerateResponse(**bundle)


@api_app.get("/api/llm/models")
def list_llm_models():
    """List recommended model ids for the current backend configuration."""
    provider = settings.llm_provider
    models = recommended_openai_chat_models() if provider == "openai" else ["mock"]
    return {
        "llm_provider": provider,
        "default_model": settings.llm_model,
        "recommended_models": models,
        "aliases": {
            "gpt-5": "gpt-5-chat-latest",
            "gpt-5.1": "gpt-5.1-chat-latest",
            "gpt-5.2": "gpt-5.2-chat-latest",
        },
    }


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
