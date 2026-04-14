from shared.queue.sns_client import SNSClient


def normalize_strategy(strategy_name: str | None) -> str:
    if strategy_name == "playwright":
        return "playwright"
    return "http"


async def publish_route_message(
    routing_topic_client: SNSClient,
    fetch_topic_arn: str,
    strategy_name: str | None,
    run_id: str,
    site_id: str,
    page_url: str,
    page_depth: int,
) -> str:
    strategy_value = normalize_strategy(strategy_name)
    await routing_topic_client.publish_message(
        topic_arn=fetch_topic_arn,
        payload={
            "run_id": run_id,
            "site_id": site_id,
            "url": page_url,
            "depth": page_depth,
        },
        message_attributes={
            "strategy": {
                "DataType": "String",
                "StringValue": strategy_value,
            }
        },
    )
    return strategy_value
