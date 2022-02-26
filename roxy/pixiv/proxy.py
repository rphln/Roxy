from urllib.parse import urljoin

from flask import Blueprint, Response, current_app

from roxy.pixiv.common import make_pixiv_headers, session

blueprint = Blueprint("pixiv", __name__)


@blueprint.route("/image/<path:path>", methods=["GET"])
def handle_pixiv_image(path: str) -> Response:
    canonical = urljoin("https://i.pximg.net/", path)
    authentication_headers = make_pixiv_headers(
        current_app.config["PIXIV_SESSION_TOKEN"]
    )

    response = session.get(canonical, stream=True, headers=authentication_headers)

    return Response(
        response.raw.stream(decode_content=False),
        direct_passthrough=True,
        status=response.status_code,
        headers=dict(response.raw.headers),
    )


__all__ = ("blueprint",)
