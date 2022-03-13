import re
from multiprocessing import Pool, Process
from os import environ
from typing import Dict, NamedTuple, Optional
from urllib import parse as urlparse
from urllib.parse import urlparse

from discord_interactions import (
    InteractionResponseType,
    InteractionType,
    verify_key_decorator,
)
from flask import Flask, current_app, jsonify, request, url_for
from requests import Session

from roxy.pixiv.common import fetch_gallery, fetch_user
from roxy.pixiv.proxy import blueprint as pixiv_blueprint

app = Flask(__name__)
app.register_blueprint(pixiv_blueprint, url_prefix="/pixiv")

session = Session()

for key in {
    "CLIENT_PUBLIC_KEY",
    "DISCORD_TOKEN",
    "PIXIV_SESSION_TOKEN",
}:
    app.config[key] = environ.get(key)


class Webhook(NamedTuple):
    id: int
    token: str

    @property
    def endpoint(self) -> str:
        return f"https://discord.com/api/v8/webhooks/{self.id}/{self.token}"


class Interaction(NamedTuple):
    application_id: int
    token: str

    @property
    def original_response_endpoint(self) -> str:
        return f"https://discord.com/api/v8/webhooks/{self.application_id}/{self.token}/messages/@original"

    @property
    def followup_endpoint(self) -> str:
        return f"https://discord.com/api/v8/webhooks/{self.application_id}/{self.token}"


class Channel(NamedTuple):
    id: int

    @property
    def webhooks_endpoint(self) -> str:
        return f"https://discord.com/api/v8/channels/{self.id}/webhooks"


def find_webhook(
    session: Session, application_id: int, channel: Channel
) -> Optional[Webhook]:
    response = session.get(
        channel.webhooks_endpoint,
        headers={"Authorization": f"Bot {current_app.config['DISCORD_TOKEN']}"},
    )

    for webhook in response.json():
        if webhook["application_id"] == application_id:
            return Webhook(id=webhook["id"], token=webhook["token"])

    return None


def setup_webhook(session: Session, channel: Channel) -> Webhook:
    response = session.post(
        channel.webhooks_endpoint,
        headers={"Authorization": f"Bot {current_app.config['DISCORD_TOKEN']}"},
        json={"name": "Previews"},
    )

    webhook = response.json()
    return Webhook(id=webhook["id"], token=webhook["token"])


def to_proxied_image_url(canonical: str) -> str:
    url = urlparse(canonical)

    # The leading slash breaks the Discord embeds.
    path = url.path[1:]

    return url_for("pixiv.handle_pixiv_image", path=path, _external=True)


pattern = re.compile(r"pixiv\S*?/artworks/(\d+)")


def handle_pixiv_gallery_request(id: str) -> Dict:
    session_token = current_app.config["PIXIV_SESSION_TOKEN"]

    gallery = fetch_gallery(id, session_token)
    gallery_url = gallery["extraData"]["meta"]["canonical"]

    tags = [
        tag.get("translation", {}).get("en", tag["tag"])
        for tag in gallery["tags"]["tags"]
    ]

    gallery_description_stem = " • ".join(tags)
    gallery_description = f"`{gallery_description_stem}`"

    author_id = gallery["userId"]
    author_page = f"https://www.pixiv.net/en/users/{author_id}"

    author = fetch_user(author_id, session_token)
    author_name = author["name"]

    match author:
        case {"imageBig": user_image_url} | {"image": user_image_url}:
            author_icon = to_proxied_image_url(user_image_url)
        case _:
            author_icon = None

    return {
        "url": gallery_url,
        "image": {"url": to_proxied_image_url(gallery["urls"]["original"])},
        "description": gallery_description,
        "color": 1942002,
        "timestamp": gallery["createDate"],
        "title": gallery["illustTitle"],
        "author": {
            "name": author_name,
            "url": author_page,
            "icon_url": author_icon,
        },
        "footer": {
            "text": f"Gallery with {gallery['pageCount']} page(s).",
            "icon_url": "https://www.pixiv.net/favicon.ico",
        },
    }


# TODO: Merge `interaction` dict and `Interaction`.
def handle_pixiv_interaction(interaction: Dict, interaction_: Interaction):
    webhook = find_webhook(
        session,
        interaction["application_id"],
        Channel(interaction["channel_id"]),
    ) or setup_webhook(
        session,
        Channel(interaction["channel_id"]),
    )

    sender_id = interaction["member"]["user"]["id"]
    sender_avatar = interaction["member"]["user"]["avatar"]

    sender_icon_url = (
        f"https://cdn.discordapp.com/avatars/{sender_id}/{sender_avatar}.png"
    )

    match interaction["member"]:
        case {"nick": nick} if nick:
            sender_name = nick
        case {"user": {"username": username}}:
            sender_name = username
        case _:
            sender_name = None

    match interaction["data"]:
        case {"options": [{"name": "urls", "value": urls}]}:
            urls = pattern.findall(urls)
        case _:
            urls = []

    # TODO: Check if using processes is actually beneficial.
    with Pool() as pool:
        embeds = pool.map(handle_pixiv_gallery_request, urls)

    session.post(
        webhook.endpoint,
        json={
            "avatar_url": sender_icon_url,
            "username": sender_name,
            "embeds": embeds,
        },
    )

    session.delete(interaction_.original_response_endpoint)


@app.route("/interactions", methods=["POST"])
@verify_key_decorator(app.config["CLIENT_PUBLIC_KEY"])
def interactions():
    interaction = Interaction(request.json["application_id"], request.json["token"])

    match request.json:
        case {"type": InteractionType.PING}:
            return jsonify({"type": InteractionResponseType.PONG})
        case {"type": InteractionType.APPLICATION_COMMAND, "data": {"name": "pixiv"}}:
            # Discord expects a response as soon as possible, so we need to run this
            # lengthy task on another process.
            task = Process(
                target=handle_pixiv_interaction,
                kwargs={"interaction": request.json, "interaction_": interaction},
            )
            task.start()
        case _:
            pass

    return jsonify(
        {"type": InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
    )


__all__ = ("app",)
