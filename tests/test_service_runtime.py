from agent.service_runtime import EchoLLMService, Result, RuntimeBuilder, ServiceLayer


class LandingPostProcessor:
    def execute(self, raw_output: str) -> Result:
        return Result(
            task_type="landing_page",
            raw_output=raw_output,
            result={
                "title": "Пример Landing",
                "sections": ["hero", "features", "cta"],
            },
        )


def test_service_layer_executes_default_runtime_pipeline():
    service = ServiceLayer(EchoLLMService())

    task = service.create_task("landing_page", {"product": "agent platform"})
    result = service.execute_task(task)

    assert result.task_type == "landing_page"
    assert "LLM output for:" in result.result["content"]
    assert result.result["input"]["product"] == "agent platform"


def test_runtime_builder_supports_custom_postprocessor():
    service = ServiceLayer(EchoLLMService())
    task = service.create_task("landing_page", {"product": "agent platform"})

    runtime = RuntimeBuilder(
        task,
        service.llm_service,
        steps=[
            runtime_step
            for runtime_step in RuntimeBuilder(task, service.llm_service).build_pipeline()[:-1]
        ]
        + [LandingPostProcessor()],
    )

    result = runtime.run()

    assert result.result["title"] == "Пример Landing"
    assert result.result["sections"] == ["hero", "features", "cta"]
