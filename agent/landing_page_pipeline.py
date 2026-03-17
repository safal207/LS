"""Advanced landing-page runtime example with SEO and analytics enrichment."""

from __future__ import annotations

from .service_runtime import LLMStep, PreProcessor, Result, RuntimeStep, ServiceLayer, Task


class SEOStep:
    """Mock SEO enrichment step (replace with real SEO API integration)."""

    def execute(self, payload: str) -> str:
        seo_score = 85
        return f"{payload}\n[SEO Score: {seo_score}]"


class AnalyticsStep:
    """Mock analytics insight step (replace with product analytics provider)."""

    def execute(self, payload: str) -> str:
        analytics_summary = "Page should target tech-savvy audience."
        return f"{payload}\n[Analytics: {analytics_summary}]"


class LandingPagePostProcessor:
    """Structured post-processing for landing-page generation."""

    def __init__(self, task: Task):
        self.task = task

    def execute(self, raw_output: str) -> Result:
        return Result(
            task_type=self.task.task_type,
            raw_output=raw_output,
            result={
                "title": f"Landing Page for {self.task.input_data.get('product', 'Product')}",
                "sections": ["hero", "features", "testimonials", "cta"],
                "summary": raw_output,
            },
        )


def build_landing_page_steps(task: Task, service: ServiceLayer) -> list[RuntimeStep]:
    """Build production-style step chain for landing-page task."""

    return [
        PreProcessor(task),
        LLMStep(service.llm_service),
        SEOStep(),
        AnalyticsStep(),
        LandingPagePostProcessor(task),
    ]
