import pytest

from agent.landing_page_pipeline import build_landing_page_steps
from agent.service_runtime import EchoLLMService, ParallelTaskExecutionError, ServiceLayer


def test_service_layer_executes_default_runtime_pipeline():
    service = ServiceLayer(EchoLLMService())

    task = service.create_task("landing_page", {"product": "agent platform"})
    result = service.execute_task(task)

    assert result.task_type == "landing_page"
    assert "LLM output for:" in result.result["content"]
    assert result.result["input"]["product"] == "agent platform"


def test_custom_landing_pipeline_adds_seo_and_analytics():
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


def test_parallel_landing_generation_with_custom_steps_preserves_order():
    service = ServiceLayer(EchoLLMService())
    tasks = [
        service.create_task("landing_page", {"product": "AI Agent Platform EN", "language": "en"}),
        service.create_task("landing_page", {"product": "AI Agent Platform RU", "language": "ru"}),
        service.create_task("landing_page", {"product": "AI Agent Platform ES", "language": "es"}),
    ]

    results = service.execute_tasks_parallel(tasks, steps_builder=build_landing_page_steps, max_workers=3)

    assert [item.task_type for item in results] == ["landing_page", "landing_page", "landing_page"]
    assert [item.result["title"] for item in results] == [
        "Landing Page for AI Agent Platform EN",
        "Landing Page for AI Agent Platform RU",
        "Landing Page for AI Agent Platform ES",
    ]
    assert all("[SEO Score: 85]" in item.result["summary"] for item in results)
    assert all("[Analytics: Page should target tech-savvy audience.]" in item.result["summary"] for item in results)


def test_parallel_landing_generation_raises_when_worker_fails():
    service = ServiceLayer(EchoLLMService())
    tasks = [
        service.create_task("landing_page", {"product": "ok"}),
        service.create_task("landing_page", {"product": "fail"}),
    ]

    class ExplodingStep:
        def execute(self, payload):
            raise RuntimeError("boom")

    def failing_builder(task, _service):
        if task.input_data["product"] == "fail":
            return [ExplodingStep()]
        return build_landing_page_steps(task, service)

    with pytest.raises(ParallelTaskExecutionError, match="index=1") as exc_info:
        service.execute_tasks_parallel(tasks, steps_builder=failing_builder, max_workers=1)

    assert exc_info.value.task_index == 1
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "boom" in str(exc_info.value.__cause__)
