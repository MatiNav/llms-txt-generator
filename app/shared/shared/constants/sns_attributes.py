from shared.constants.render_mode import RenderModeValue


SNS_ATTRIBUTE_RENDER_MODE = "render_mode"


def build_render_mode_attribute(
    render_mode: RenderModeValue,
) -> dict[str, dict[str, str]]:
    return {
        SNS_ATTRIBUTE_RENDER_MODE: {
            "DataType": "String",
            "StringValue": render_mode,
        }
    }
