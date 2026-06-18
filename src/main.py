from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
import re

from config import load_config
from instagram import create_story_container, publish_container
from mercadolivre import Product, pick_product, product_from_link, search_products
from story_image import create_story
from uploader import upload_story


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "story"


def _story_output_path(output_dir: str, title: str, output: str | None) -> Path:
    if output:
        return Path(output)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{_slugify(title)}.jpg"
    return Path(output_dir) / "stories" / filename


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="gera a imagem, mas nao publica")
    parser.add_argument("--sample", action="store_true", help="usa produto ficticio para testar o layout")
    parser.add_argument("--title", help="titulo do produto para gerar story manual")
    parser.add_argument("--price", type=float, help="preco do produto para gerar story manual")
    parser.add_argument("--link", help="link do produto para gerar story manual")
    parser.add_argument("--from-link", help="link do Mercado Livre para puxar dados automaticamente")
    parser.add_argument("--thumbnail", default="", help="URL ou caminho local da imagem do produto")
    parser.add_argument("--output", help="caminho completo do JPG gerado")
    args = parser.parse_args()

    config = load_config()
    if args.from_link:
        product = product_from_link(args.from_link)
    else:
        product = None

    manual_fields = [args.title, args.price, args.link]
    if product is None and any(value is not None for value in manual_fields):
        missing_manual = []
        if not args.title:
            missing_manual.append("--title")
        if args.price is None:
            missing_manual.append("--price")
        if not args.link:
            missing_manual.append("--link")
        if missing_manual:
            raise RuntimeError(f"Informe tambem: {', '.join(missing_manual)}")

        product = Product(
            title=args.title,
            price=args.price,
            permalink=args.link,
            thumbnail=args.thumbnail,
            sold_quantity=0,
            available_quantity=1,
        )
    elif product is None and args.sample:
        product = Product(
            title="Produto de exemplo para story de afiliado",
            price=199.90,
            permalink="https://www.mercadolivre.com.br/",
            thumbnail="",
            sold_quantity=0,
            available_quantity=1,
        )
    elif product is None:
        products = search_products(
            site_id=config.ml_site_id,
            query=config.ml_query,
            limit=config.ml_limit,
            min_price=config.ml_min_price,
            max_price=config.ml_max_price,
            access_token=config.ml_access_token,
            affiliate_tag=config.ml_affiliate_tag,
        )
        product = pick_product(products)

    output_path = _story_output_path(config.output_dir, product.title, args.output)
    create_story(product, output_path)

    print(f"Produto: {product.title}")
    print(f"Preco: R$ {product.price:.2f}")
    print(f"Link: {product.permalink}")
    print(f"Story gerado: {output_path.resolve()}")

    if args.dry_run:
        print("Dry-run ativo: nada foi publicado no Instagram.")
        return

    missing = []
    if not config.ig_user_id:
        missing.append("IG_USER_ID")
    if not config.ig_access_token:
        missing.append("IG_ACCESS_TOKEN")
    if not config.upload_endpoint and not config.public_base_url:
        missing.append("PUBLIC_BASE_URL ou UPLOAD_ENDPOINT")
    if missing:
        raise RuntimeError(f"Configure antes de publicar: {', '.join(missing)}")

    image_url = ""
    if config.upload_endpoint:
        image_url = upload_story(config.upload_endpoint, config.upload_secret, output_path)
        print(f"Story enviado: {image_url}")

    if not image_url:
        image_url = f"{config.public_base_url}/{output_path.name}"

    creation_id = create_story_container(config.ig_user_id, config.ig_access_token, image_url)
    result = publish_container(config.ig_user_id, config.ig_access_token, creation_id)
    print(f"Publicado: {result}")


if __name__ == "__main__":
    main()
