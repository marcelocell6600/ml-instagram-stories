from dataclasses import dataclass
from html.parser import HTMLParser
import json
import re
from html import unescape
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

import requests
from requests import HTTPError


@dataclass(frozen=True)
class Product:
    title: str
    price: float
    permalink: str
    thumbnail: str
    sold_quantity: int
    available_quantity: int
    marketplace: str = "Mercado Livre"


class ProductParseError(RuntimeError):
    def __init__(self, message: str, partial_product: Product | None = None) -> None:
        super().__init__(message)
        self.partial_product = partial_product


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


class ProductPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.ld_json: list[str] = []
        self.title = ""
        self._in_title = False
        self._in_ld_json = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag == "meta":
            key = attr_map.get("property") or attr_map.get("name") or attr_map.get("itemprop")
            content = attr_map.get("content")
            if key and content:
                self.meta[key.lower()] = unescape(content).strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and attr_map.get("type", "").lower() == "application/ld+json":
            self._in_ld_json = True
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_ld_json:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld_json:
            self._in_ld_json = False
            self.ld_json.append("".join(self._script_parts).strip())
            self._script_parts = []


def _with_affiliate_tag(url: str, affiliate_tag: str) -> str:
    if not affiliate_tag:
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query["utm_source"] = "instagram"
    query["utm_medium"] = "story"
    query["utm_campaign"] = affiliate_tag
    return urlunparse(parsed._replace(query=urlencode(query)))


def _extract_item_id(url: str) -> str | None:
    match = re.search(r"\b(MLB)[-]?(\d{8,})\b", url, flags=re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1).upper()}{match.group(2)}"


def _clean_title(value: str) -> str:
    return (
        value.replace(" | MercadoLivre", "")
        .replace(" | Mercado Livre", "")
        .replace(" - Mercado Livre", "")
        .replace(": Amazon.com.br", "")
        .replace("| Amazon.com.br", "")
        .replace("| Amazon", "")
        .replace("| Shopee Brasil", "")
        .strip()
    )


def _normal_price(value: str) -> float:
    cleaned = re.sub(r"[^0-9,.]", "", value).strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _first_regex(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return unescape(match.group(1)).strip()
    return ""


def _amazon_price_from_html(html: str) -> str:
    direct_price = _first_regex(
        [
            r'id=["\']priceblock_(?:our|deal|sale)price["\'][^>]*>\s*(R\$\s*[\d\.,]+)',
            r'id=["\']price_inside_buybox["\'][^>]*>\s*(R\$\s*[\d\.,]+)',
            r'"displayPrice"\s*:\s*"([^"]+)"',
            r'"priceToPay"[^}]*"displayString"\s*:\s*"([^"]+)"',
            r'class=["\']a-offscreen["\'][^>]*>\s*(R\$\s*[\d\.,]+)',
        ],
        html,
    )
    if direct_price:
        return direct_price

    split_match = re.search(
        r'class=["\']a-price-whole["\'][^>]*>\s*([\d\.]+)[^<]*<.*?'
        r'class=["\']a-price-fraction["\'][^>]*>\s*(\d{2})',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if split_match:
        return f"{split_match.group(1)},{split_match.group(2)}"

    return ""


def _amazon_image_from_html(html: str) -> str:
    image = _first_regex(
        [
            r'id=["\']landingImage["\'][^>]*(?:data-old-hires|src)=["\']([^"\']+)',
            r'"hiRes"\s*:\s*"([^"]+)"',
            r'"large"\s*:\s*"([^"]+)"',
            r'"mainUrl"\s*:\s*"([^"]+)"',
        ],
        html,
    )
    return image.replace("\\/", "/")


def _parser_from_response(response: requests.Response) -> ProductPageParser:
    parser = ProductPageParser()
    parser.feed(response.text)
    return parser


def _product_from_parsed_page(
    url: str,
    html: str,
    parser: ProductPageParser,
    marketplace: str,
) -> Product:
    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.meta.get("title")
        or parser.title.strip()
    )
    image = parser.meta.get("og:image") or parser.meta.get("twitter:image") or parser.meta.get("image") or ""
    price_text = (
        parser.meta.get("product:price:amount")
        or parser.meta.get("price")
        or parser.meta.get("twitter:data1")
        or ""
    )

    for script in parser.ld_json:
        try:
            data = json.loads(unescape(script))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            title = title or str(item.get("name") or "")
            image_value = item.get("image")
            if not image and isinstance(image_value, str):
                image = image_value
            if not image and isinstance(image_value, list) and image_value:
                image = str(image_value[0])
            price_text = price_text or str(offers.get("price") or "")

    if not title:
        title = _first_regex(
            [
                r'id=["\']productTitle["\'][^>]*>(.*?)<',
                r'"name"\s*:\s*"([^"]+)"',
                r'"title"\s*:\s*"([^"]+)"',
            ],
            html,
        )
    if not image:
        image = _first_regex(
            [
                r'"hiRes"\s*:\s*"([^"]+)"',
                r'"large"\s*:\s*"([^"]+)"',
                r'"imageUrl"\s*:\s*"([^"]+)"',
                r'"image"\s*:\s*"([^"]+)"',
            ],
            html,
        ).replace("\\/", "/")
    if marketplace == "Amazon" and not image:
        image = _amazon_image_from_html(html)
    if not price_text:
        price_text = _first_regex(
            [
                r'"price"\s*:\s*"?([0-9]+(?:[,.][0-9]+)?)"?',
                r'"priceAmount"\s*:\s*"?([0-9]+(?:[,.][0-9]+)?)"?',
                r'class=["\']a-offscreen["\'][^>]*>\s*(R\$[^<]+)',
                r'"current_price":\{"value":([0-9.]+)',
            ],
            html,
        )
    if marketplace == "Amazon" and not price_text:
        price_text = _amazon_price_from_html(html)

    if not title or not price_text:
        partial = None
        if title or image:
            partial = Product(
                title=_clean_title(title) if title else "",
                price=0,
                permalink=url,
                thumbnail=image,
                sold_quantity=0,
                available_quantity=1,
                marketplace=marketplace,
            )
        if title and not price_text:
            raise ProductParseError(
                "Consegui ler o produto, mas a Amazon nao enviou o preco. Informe o preco manualmente.",
                partial,
            )
        raise ProductParseError("Nao consegui ler titulo e preco desse link. Informe os dados manualmente.", partial)

    return Product(
        title=_clean_title(title),
        price=_normal_price(str(price_text)),
        permalink=url,
        thumbnail=image,
        sold_quantity=0,
        available_quantity=1,
        marketplace=marketplace,
    )


def _decode_json_text(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return unescape(value)


def _from_social_html(html: str, permalink: str) -> Product | None:
    card_match = re.search(
        r'"metadata":\{.*?"id":"(MLB\d+)".*?'
        r'"pictures":\{.*?"pictures":\[\{"id":"([^"]+)".*?'
        r'"type":"title".*?"text":"([^"]+)".*?'
        r'"current_price":\{"value":([0-9.]+)',
        html,
        flags=re.DOTALL,
    )
    if not card_match:
        return None

    image_id = card_match.group(2)
    title = _decode_json_text(card_match.group(3))
    price = float(card_match.group(4))
    thumbnail = f"https://http2.mlstatic.com/D_Q_NP_2X_{image_id}-V.webp"

    return Product(
        title=_clean_title(title),
        price=price,
        permalink=permalink,
        thumbnail=thumbnail,
        sold_quantity=0,
        available_quantity=1,
        marketplace="Mercado Livre",
    )


def _from_item_api(item_id: str, permalink: str) -> Product:
    response = requests.get(
        f"https://api.mercadolibre.com/items/{item_id}",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    pictures = data.get("pictures") or []
    thumbnail = ""
    if pictures:
        thumbnail = pictures[0].get("secure_url") or pictures[0].get("url") or ""
    if not thumbnail:
        thumbnail = data.get("secure_thumbnail") or data.get("thumbnail") or ""

    return Product(
        title=data["title"],
        price=float(data["price"]),
        permalink=permalink,
        thumbnail=thumbnail,
        sold_quantity=int(data.get("sold_quantity", 0)),
        available_quantity=int(data.get("available_quantity", 0)),
        marketplace="Mercado Livre",
    )


def _from_html(url: str, marketplace: str = "Mercado Livre") -> Product:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    social_product = _from_social_html(response.text, url)
    if social_product:
        return social_product

    return _product_from_parsed_page(url, response.text, _parser_from_response(response), marketplace)


def _marketplace_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "amazon." in host or "amzn." in host:
        return "Amazon"
    if host in {"amzn.to", "www.amzn.to", "link.amazon", "www.link.amazon"}:
        return "Amazon"
    if "shopee." in host:
        return "Shopee"
    if "mercadolivre." in host or "mercadolibre." in host or "meli.la" in host:
        return "Mercado Livre"
    return "Oferta"


def marketplace_from_link(url: str) -> str:
    return _marketplace_from_url(url)


def _amazon_direct_product_url(url: str) -> str:
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", urlparse(url).path, flags=re.IGNORECASE)
    if not match:
        return ""
    return f"https://www.amazon.com.br/dp/{match.group(1).upper()}"


def _from_amazon_link(url: str, response: requests.Response) -> Product:
    try:
        product = _product_from_parsed_page(
            response.url or url,
            response.text,
            _parser_from_response(response),
            "Amazon",
        )
    except ProductParseError as exc:
        direct_url = _amazon_direct_product_url(response.url or url)
        if not direct_url or direct_url == response.url:
            raise
        direct_response = requests.get(direct_url, headers=HEADERS, timeout=30)
        direct_response.raise_for_status()
        try:
            product = _product_from_parsed_page(
                direct_url,
                direct_response.text,
                _parser_from_response(direct_response),
                "Amazon",
            )
        except ProductParseError as direct_exc:
            if direct_exc.partial_product:
                raise direct_exc
            raise exc
    image = product.thumbnail or _amazon_image_from_html(response.text)
    return Product(product.title, product.price, url, image, 0, 1, "Amazon")


def _shopee_ids(url: str) -> tuple[str, str] | None:
    patterns = [
        r"\.i\.(\d+)\.(\d+)",
        r"/product/(\d+)/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    return None


def _from_shopee_api(url: str, final_url: str) -> Product | None:
    ids = _shopee_ids(final_url) or _shopee_ids(url)
    if not ids:
        return None
    shop_id, item_id = ids
    headers = dict(HEADERS)
    headers["Referer"] = final_url
    response = requests.get(
        "https://shopee.com.br/api/v4/item/get",
        params={"shopid": shop_id, "itemid": item_id},
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        return None
    data = response.json().get("data") or {}
    if not data:
        return None

    price_value = data.get("price") or data.get("price_min") or 0
    price = float(price_value) / 100000
    images = data.get("images") or []
    image_hash = images[0] if images else data.get("image", "")
    thumbnail = f"https://down-br.img.susercontent.com/file/{image_hash}" if image_hash else ""

    return Product(
        title=data.get("name", "Produto Shopee"),
        price=price,
        permalink=url,
        thumbnail=thumbnail,
        sold_quantity=int(data.get("historical_sold", 0) or 0),
        available_quantity=int(data.get("stock", 1) or 1),
        marketplace="Shopee",
    )


def _from_shopee_link(url: str, final_url: str, response: requests.Response) -> Product:
    api_product = _from_shopee_api(url, final_url)
    if api_product:
        return api_product
    return _product_from_parsed_page(
        url,
        response.text,
        _parser_from_response(response),
        "Shopee",
    )


def product_from_link(url: str) -> Product:
    response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    response.raise_for_status()
    final_url = response.url
    marketplace = _marketplace_from_url(final_url or url)

    if marketplace == "Amazon":
        return _from_amazon_link(url, response)
    if marketplace == "Shopee":
        return _from_shopee_link(url, final_url, response)

    item_id = _extract_item_id(final_url) or _extract_item_id(url)

    social_product = _from_social_html(response.text, url)
    if social_product:
        return social_product

    if item_id:
        try:
            return _from_item_api(item_id, url)
        except requests.RequestException:
            pass

    return _from_html(final_url, marketplace)


def search_products(
    site_id: str,
    query: str,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    access_token: str,
    affiliate_tag: str,
) -> list[Product]:
    params: dict[str, str | int] = {"q": query, "limit": limit}
    if min_price is not None or max_price is not None:
        lower = "*" if min_price is None else str(min_price)
        upper = "*" if max_price is None else str(max_price)
        params["price"] = f"{lower}-{upper}"

    headers = dict(HEADERS)
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    response = requests.get(
        f"https://api.mercadolibre.com/sites/{site_id}/search",
        params=params,
        headers=headers,
        timeout=30,
    )
    try:
        response.raise_for_status()
    except HTTPError as exc:
        if response.status_code == 403:
            raise RuntimeError(
                "Mercado Livre retornou 403 Forbidden. Configure ML_ACCESS_TOKEN no .env."
            ) from exc
        raise

    products = []
    for item in response.json().get("results", []):
        products.append(
            Product(
                title=item["title"],
                price=float(item["price"]),
                permalink=_with_affiliate_tag(item["permalink"], affiliate_tag),
                thumbnail=item.get("thumbnail", ""),
                sold_quantity=int(item.get("sold_quantity", 0)),
                available_quantity=int(item.get("available_quantity", 0)),
            )
        )

    return products


def pick_product(products: list[Product]) -> Product:
    if not products:
        raise RuntimeError("Nenhum produto encontrado para os filtros configurados.")

    return sorted(
        products,
        key=lambda product: (product.sold_quantity, product.available_quantity),
        reverse=True,
    )[0]
