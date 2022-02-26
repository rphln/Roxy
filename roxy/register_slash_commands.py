from os import environ
from pprint import pprint

import requests


class ApplicationCommandOptionType:
    STRING = 3


discord_token = environ["DISCORD_TOKEN"]
discord_application_id = 271420969967550464

url = f"https://discord.com/api/v8/applications/{discord_application_id}/commands"

json = {
    "name": "pixiv",
    "description": "Sends a Pixiv image preview.",
    "options": [
        {
            "name": "urls",
            "description": "The URLs of the galleries.",
            "type": ApplicationCommandOptionType.STRING,
            "required": True,
        }
    ],
}

headers = {"Authorization": f"Bot {discord_token}"}
r = requests.post(url, headers=headers, json=json)
pprint(r.json())
