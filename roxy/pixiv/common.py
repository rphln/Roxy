from typing import Dict

from requests import Session

session = Session()


def make_pixiv_headers(session_token: str):
    return {
        "Accept-Language": "en",
        "Cookie": f"PHPSESSID={session_token}",
        "Referer": "https://www.pixiv.net/ajax",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36",
    }


def _fetch(endpoint: str, session_token: str) -> Dict:
    response = session.get(endpoint, headers=make_pixiv_headers(session_token))

    match response.json():
        case {"error": False, "body": body}:
            return body
        case {"error": True}:
            raise ValueError()
        case _:
            raise RuntimeError()


def fetch_user(id: int, session_token: str) -> Dict:
    return _fetch(
        f"https://www.pixiv.net/ajax/user/{id}",
        session_token,
    )


def fetch_gallery(id: int, session_token: str) -> Dict:
    return _fetch(
        f"https://www.pixiv.net/ajax/illust/{id}",
        session_token,
    )


def fetch_gallery_pages(id: int, session_token: str) -> Dict:
    return _fetch(
        f"https://www.pixiv.net/ajax/illust/{id}/pages",
        session_token,
    )


__all__ = ("fetch_gallery", "fetch_gallery_pages", "fetch_user")
