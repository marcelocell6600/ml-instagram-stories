from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
import requests

from mercadolivre import Product


STORY_SIZE = (1080, 1920)
BLACK = "#050507"
PANEL = "#0c0d12"
WHITE = "#f7f7fb"
MUTED = "#b8bfd5"
BLUE = "#00a7ff"
PURPLE = "#b22cff"
MAGENTA = "#ff2bd6"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
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


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
    width, height = _text_size(draw, text, font)
    x = box[0] + ((box[2] - box[0]) - width) // 2
    y = box[1] + ((box[3] - box[1]) - height) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, start_size: int, max_width: int, min_size: int = 28) -> ImageFont.ImageFont:
    size = start_size
    while size > min_size:
        font = _font(size)
        if _text_size(draw, text, font)[0] <= max_width:
            return font
        size -= 4
    return _font(min_size)


def _wrapped_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(lines)) < len(text):
        lines[-1] = lines[-1].rstrip(".") + "..."
    return lines


def _draw_glow_line(base: Image.Image, points: list[tuple[int, int]], color: str, width: int) -> None:
    glow = Image.new("RGBA", STORY_SIZE, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for extra, alpha in ((30, 45), (18, 70), (8, 110)):
        glow_draw.line(points, fill=color + f"{alpha:02x}", width=width + extra, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(glow)
    draw = ImageDraw.Draw(base)
    draw.line(points, fill=color, width=width, joint="curve")


def _draw_neon_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, outline: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 8, y1 + 8, x2 + 8, y2 + 8), radius=radius, fill="#000000")
    draw.rounded_rectangle(box, radius=radius, fill=PANEL)
    draw.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), radius=radius - 2, outline=outline, width=3)


def _draw_brand(draw: ImageDraw.ImageDraw, marketplace: str) -> None:
    draw.text((68, 54), "MARCELO CELL", font=_font(52), fill=WHITE)
    draw.text((72, 116), "OFERTAS TECH", font=_font(25), fill=BLUE)
    chip = marketplace.upper() if marketplace else "OFERTA"
    chip_font = _fit_font(draw, chip, 26, 260, 18)
    draw.rounded_rectangle((732, 58, 1012, 116), radius=18, outline=PURPLE, width=3, fill="#08060d")
    _center_text(draw, (732, 58, 1012, 116), chip, chip_font, WHITE)
    draw.line((68, 170, 1012, 170), fill="#252737", width=2)


def create_story(product: Product, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGBA", STORY_SIZE, BLACK)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 1080, 1920), fill=BLACK)
    draw.ellipse((450, 320, 1280, 1180), outline="#171a2a", width=18)
    _draw_glow_line(image, [(0, 250), (330, 250), (500, 250), (650, 238), (760, 198), (870, 100)], PURPLE, 5)
    _draw_glow_line(image, [(110, 1458), (330, 1428), (580, 1436), (810, 1486), (1068, 1454)], BLUE, 5)
    _draw_glow_line(image, [(260, 1540), (520, 1576), (820, 1562), (1080, 1512)], MAGENTA, 4)
    _draw_brand(draw, product.marketplace)

    product_image = _load_product_image(product.thumbnail)
    _draw_neon_box(draw, (82, 245, 998, 1008), 34, BLUE)
    draw.rounded_rectangle((112, 278, 968, 975), radius=28, fill="#f8f8fb")
    if product_image:
        product_image.thumbnail((790, 640))
        x = (STORY_SIZE[0] - product_image.width) // 2
        y = 310 + (620 - product_image.height) // 2
        image.paste(product_image.convert("RGBA"), (x, y))
    else:
        draw.text((270, 590), "Imagem do produto", font=_font(52), fill="#222222")

    title_font = _font(48)
    title_lines = _wrapped_lines(draw, product.title, title_font, 920, 3)
    y = 1040
    for line in title_lines:
        draw.text((70, y), line, font=title_font, fill=WHITE)
        y += 58

    price = f"R$ {product.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    draw.rounded_rectangle((72, 1228, 1008, 1396), radius=26, fill="#090b10", outline=PURPLE, width=3)
    draw.text((110, 1252), "OFERTA ESPECIAL", font=_font(30), fill=BLUE)
    price_font = _fit_font(draw, price, 86, 850, 58)
    draw.text((108, 1292), price, font=price_font, fill=WHITE)
    draw.line((106, 1398, 974, 1398), fill=MAGENTA, width=4)

    qr = qrcode.make(product.permalink).convert("RGB").resize((260, 260))
    draw.rounded_rectangle((72, 1450, 410, 1788), radius=28, fill="#ffffff", outline=BLUE, width=4)
    image.paste(qr.convert("RGBA"), (111, 1489))
    draw.rounded_rectangle((430, 1450, 1008, 1788), radius=28, fill="#050507")
    draw.text((452, 1492), "ESCANEIE", font=_font(52), fill=WHITE)
    draw.text((452, 1552), "o QR code", font=_font(42), fill=MUTED)
    draw.text((452, 1625), "ou toque no link", font=_font(42), fill=BLUE)
    draw.text((452, 1680), "do sticker", font=_font(42), fill=PURPLE)

    draw.rounded_rectangle((36, 1810, 1044, 1890), radius=24, fill="#07080c", outline="#272a3a", width=2)
    draw.text((70, 1830), "MARCELO CELL", font=_font(30), fill=WHITE)
    draw.text((310, 1833), "Ofertas sujeitas a disponibilidade e alteracao de preco.", font=_font(24), fill=MUTED)

    image.convert("RGB").save(output_path, quality=94)
    return output_path
