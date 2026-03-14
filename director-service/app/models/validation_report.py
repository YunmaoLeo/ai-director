from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    level: str  # "error" or "warning"
    category: str  # "structural", "scene_reference", "semantic", "trajectory"
    message: str
    field: str = ""


class ValidationReport(BaseModel):
    is_valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
