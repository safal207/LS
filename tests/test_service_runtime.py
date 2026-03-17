from agent.landing_page_pipeline import build_landing_page_steps
from agent.service_runtime import EchoLLMService, ServiceLayer


def test_service_layer_executes_default_runtime_pipeline() -> None:
    service = ServiceLayer(EchoLLMService())

    task = service.create_task("landing_page", {"product": "agent platform"})
    result = service.execute_task(task)

    assert result.task_type == "landing_page"
    assert "LLM output for:" in result.result["content"]
    assert result.result["input"]["product"] == "agent platform"


def test_custom_landing_pipeline_adds_seo_and_analytics() -> None:
    service = ServiceLayer(EchoLLMService())
    task = service.create_task("landing_page", {"product": "AI Agent Platform"})

    result = service.execute_task_with_steps(task, build_landing_page_steps(task, service))

    assert result.result == {
        "title": "Landing Page for AI Agent Platform",
        "sections": ["hero", "features", "testimonials", "cta"],
        "summary": (
            "LLM output for: task=landing_page;input={'product': 'AI Agent Platform'}\n"
            "[SEO Score: 85]\n"
            "[Analytics: Page should target tech-savvy audience.]"
        ),
    }
