from typing import Literal, TypeAlias


RENDER_MODE_HTTP = "http"
RENDER_MODE_SPA = "spa"

ALLOWED_RENDER_MODES = (RENDER_MODE_HTTP, RENDER_MODE_SPA)

RenderModeValue: TypeAlias = Literal[RENDER_MODE_HTTP, RENDER_MODE_SPA]
