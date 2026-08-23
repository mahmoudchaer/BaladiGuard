from types import SimpleNamespace

from scripts.capacity.cloudwatch_capacity import collect_capacity_cloudwatch


class FakeCloudWatch:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_metric_statistics(self, **kwargs):
        self.calls.append(kwargs)
        stat = (kwargs.get("Statistics") or kwargs.get("ExtendedStatistics"))[0]
        if stat == "p95":
            return {"Datapoints": [{"ExtendedStatistics": {"p95": 123.5}}]}
        return {"Datapoints": [{stat: 2.0}]}


def test_collects_application_and_worker_metrics(monkeypatch):
    cloudwatch = FakeCloudWatch()
    monkeypatch.setitem(
        __import__("sys").modules,
        "boto3",
        SimpleNamespace(client=lambda *_args, **_kwargs: cloudwatch),
    )

    result = collect_capacity_cloudwatch(
        region="us-east-1",
        table_prefix="baladiguard-staging-",
        s3_bucket="capacity-bucket",
        environment="staging",
        ecs_cluster="baladiguard-staging",
    )

    assert result["application"]["HttpRequests"]["value"] == 2.0
    assert result["application"]["HttpRequestDurationP95"]["value"] == 123.5
    assert result["ecs"]["ai-worker"]["RunningTaskCount"]["value"] == 2.0
    assert any(
        call["Namespace"] == "ECS/ContainerInsights"
        and {dimension["Value"] for dimension in call["Dimensions"]}
        == {"baladiguard-staging", "baladiguard-staging-ai-worker"}
        for call in cloudwatch.calls
    )
