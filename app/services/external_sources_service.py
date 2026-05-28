from dataclasses import dataclass

from app.config import settings


@dataclass
class ExternalExerciseResult:
    name: str
    source: str
    image_url: str | None = None
    summary: str | None = None


class ExternalSourcesService:
    """Integration point for future open exercise APIs or approved data sources."""

    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = settings.enable_external_sources if enabled is None else enabled

    def search_exercises(self, query: str) -> list[ExternalExerciseResult]:
        if not self.enabled or not query.strip():
            return []

        # Keep this disabled by default. Future integrations should use official APIs,
        # preserve attribution, and fail closed without breaking the local app.
        return []
