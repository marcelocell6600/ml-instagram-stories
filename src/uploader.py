from pathlib import Path

import requests


def upload_story(endpoint: str, secret: str, image_path: Path) -> str:
    headers = {"content-type": "image/jpeg"}
    if secret:
        headers["x-upload-secret"] = secret

    with image_path.open("rb") as image_file:
        response = requests.post(
            endpoint,
            headers=headers,
            data=image_file,
            timeout=60,
        )

    response.raise_for_status()
    data = response.json()
    image_url = data.get("url") or data.get("fileUrl")
    if not image_url:
        raise RuntimeError(f"Upload respondeu sem URL da imagem: {data}")
    return image_url
