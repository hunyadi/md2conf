import base64
import os
import zlib
from typing import Literal

import requests


def get_kroki_server() -> str:
    """
    Returns the URL to the Kroki server.

    Use `docker` to run a [Kroki](https://kroki.io/) server in a container:
    ```
    docker run -p8000:8000 yuzutech/kroki
    ```
    """

    return os.getenv("KROKI_SERVER_URL", "https://kroki.io")


def render(source: str, output_format: Literal["png", "svg"] = "png") -> bytes:
    compressed_source = zlib.compress(source.encode("utf-8"), 9)
    encoded_source = base64.urlsafe_b64encode(compressed_source).decode("ascii")
    kroki_server = get_kroki_server()
    kroki_url = f"{kroki_server}/mermaid/{output_format}/{encoded_source}"
    response = requests.get(kroki_url)

    if response.status_code == 200:
        if output_format == "png":
            return response.content
        else:
            return response.text.encode("utf-8")
    else:
        raise RuntimeError(
            f"failed to render Mermaid diagram; HTTP status code: {response.status_code}"
        )
