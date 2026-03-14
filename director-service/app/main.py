"""CLI entry point using Typer."""

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="AI Director Service — cinematic directing pipeline")


@app.command()
def generate_plan(
    scene: Path = typer.Option(..., help="Path to scene summary JSON file"),
    intent: str = typer.Option(..., help="User intent text"),
    output_dir: Path = typer.Option("outputs", help="Output directory"),
    mock: bool = typer.Option(False, help="Use mock LLM client"),
):
    """Generate a cinematic directing plan from a scene and intent."""
    from app.pipelines.generate_plan_pipeline import GeneratePlanPipeline

    from app.config import settings

    provider = "mock" if mock else settings.llm_provider
    pipeline = GeneratePlanPipeline(
        llm_provider=provider,
        output_dir=str(output_dir),
    )
    result = pipeline.run(str(scene), intent)

    typer.echo(f"\nPlan generated: {len(result.directing_plan.shots)} shots, "
               f"{result.directing_plan.total_duration}s total")
    typer.echo(f"Validation: {'PASS' if result.validation_report.is_valid else 'FAIL'}")
    if result.validation_report.errors:
        for err in result.validation_report.errors:
            typer.echo(f"  ERROR: {err.message}")
    if result.validation_report.warnings:
        for warn in result.validation_report.warnings:
            typer.echo(f"  WARN: {warn.message}")
    typer.echo(f"\nOutputs saved to {output_dir}/")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
):
    """Start the FastAPI development server."""
    import uvicorn
    uvicorn.run("app.api:api_app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
