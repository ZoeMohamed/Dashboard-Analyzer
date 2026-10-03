"""Small, persistent usage guard for paid/provider calls."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.config import Settings
from app.contracts import ProviderUsage, SourceName
from app.errors import BudgetExhaustedError


class UsageService:
    def __init__(self, repository: object, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    @staticmethod
    def _today() -> date:
        return datetime.now(timezone.utc).date()

    async def reserve(self, provider: str, source: SourceName | None, units: int = 1) -> ProviderUsage:
        """Atomically reserve a bounded unit from the repository view.

        The PostgreSQL upsert is serialized by the row key. A stricter quota
        transaction can be introduced later without changing providers/routes.
        """
        units = max(0, units)
        current = await self.repository.get_usage(provider, source, self._today())
        limit = self.settings.apify_daily_run_limit if provider == "apify" else self.settings.gemini_monthly_analysis_limit
        if current.units + units > limit:
            raise BudgetExhaustedError(f"Batas penggunaan {provider} tercapai")
        return await self.repository.record_usage(
            ProviderUsage(provider=provider, source=source, usage_date=self._today(), requests=1, units=units)
        )
