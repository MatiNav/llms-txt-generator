from shared.constants.render_mode import RenderModeValue
from shared.constants.sns_attributes import build_render_mode_attribute
from shared.queue.sns_client import SNSClient


async def publish_route_message(
    routing_topic_client: SNSClient,
    fetch_topic_arn: str,
    render_mode: RenderModeValue,
    run_id: str,
    page_id: str,
    site_id: str,
    page_url: str,
    page_depth: int,
) -> None:
    await routing_topic_client.publish_message(
        topic_arn=fetch_topic_arn,
        payload={
            "run_id": run_id,
            "page_id": page_id,
            "site_id": site_id,
            "url": page_url,
            "depth": page_depth,
            "render_mode": render_mode,
        },
        message_attributes=build_render_mode_attribute(render_mode),
    )
