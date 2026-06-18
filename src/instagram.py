import requests


GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


def create_story_container(ig_user_id: str, access_token: str, image_url: str) -> str:
    response = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "STORIES",
            "image_url": image_url,
            "access_token": access_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["id"]


def publish_container(ig_user_id: str, access_token: str, creation_id: str) -> dict:
    response = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
