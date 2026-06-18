from io import BytesIO
from pathlib import Path
import textwrap
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests

from mercadolivre import Product


STORY_SIZE = (1080, 1920)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/system/fonts/Roboto-Regular.ttf",
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _download_image(url: str) -> Image.Image | None:
    if not url:
        return None

    response = requests.get(url.replace("-I.jpg", "-O.jpg"), timeout=30)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def _load_product_image(source: str) -> Image.Image | None:
    if not source:
        return None

    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return _download_image(source)

    image_path = Path(source)
    if image_path.exists():
        return Image.open(image_path).convert("RGB")

    return None


def create_story(product: Product, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", STORY_SIZE, "#f7d800")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 1080, 260), fill="#242424")
    draw.text((70, 78), "Oferta Mercado Livre", font=_font(58), fill="#ffffff")

    product_image = _load_product_image(product.thumbnail)
    if product_image:
        product_image.thumbnail((760, 620))
        x = (STORY_SIZE[0] - product_image.width) // 2
        image.paste(product_image, (x, 340))
    else:
        draw.rounded_rectangle((180, 360, 900, 900), radius=32, fill="#fff3a6")
        draw.text((270, 580), "Imagem do produto", font=_font(52), fill="#4a4200")

    title_font = _font(52)
    title_lines = textwrap.wrap(product.title, width=28)[:4]
    y = 990
    for line in title_lines:
        draw.text((70, y), line, font=title_font, fill="#222222")
        y += 66

    price = f"R$ {product.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    draw.rounded_rectangle((70, 1265, 1010, 1435), radius=34, fill="#00a650")
    draw.text((120, 1310), price, font=_font(76), fill="#ffffff")

    qr = qrcode.make(product.permalink).convert("RGB").resize((260, 260))
    draw.rounded_rectangle((70, 1488, 370, 1788), radius=24, fill="#ffffff")
    image.paste(qr, (90, 1508))
    draw.text((410, 1545), "Escaneie o QR code", font=_font(44), fill="#222222")
    draw.text((410, 1608), "ou use o link do story", font=_font(44), fill="#222222")

    draw.text((70, 1830), "Produto sujeito a disponibilidade e alteracao de preco.", font=_font(28), fill="#555555")

    image.save(output_path, quality=92)
    return output_path
