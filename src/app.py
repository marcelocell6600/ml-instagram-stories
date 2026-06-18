from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
from urllib.parse import parse_qs
import html
import mimetypes

from main import _story_output_path
from mercadolivre import Product, product_from_link
from story_image import create_story


PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"
STORIES_DIR = OUTPUT_DIR / "stories"


def _html_escape(value: str) -> str:
    return html.escape(value, quote=True)


def _story_url(path: Path) -> str:
    return f"/stories/{path.name}"


def _download_url(filename: str) -> str:
    return f"/download/{filename}"


def _render_page(
    message: str = "",
    image_url: str = "",
    file_path: str = "",
    link_url: str = "",
    error: str = "",
    form: dict[str, str] | None = None,
) -> bytes:
    form = form or {}
    link_value = _html_escape(form.get("link", ""))
    title_value = _html_escape(form.get("title", ""))
    price_value = _html_escape(form.get("price", ""))
    thumbnail_value = _html_escape(form.get("thumbnail", ""))
    details_open = " open" if error or title_value or price_value or thumbnail_value else ""

    status = ""
    if error:
        status = f'<p class="status error">{_html_escape(error)}</p>'
    elif message:
        status = f'<p class="status ok">{_html_escape(message)}</p>'

    preview = ""
    if image_url:
        link_block = ""
        if link_url:
            link_block = f"""
            <div class="copy-link">
              <label for="story-link">Link para o sticker do Instagram</label>
              <div class="copy-row">
                <input id="story-link" type="text" readonly value="{_html_escape(link_url)}">
                <button class="copy-button" type="button" onclick="copyStoryLink()">Copiar</button>
              </div>
            </div>
            """
        image_actions = f"""
        <div class="image-actions">
          <a class="action-button" href="{_html_escape(image_url)}" target="_blank">Abrir imagem</a>
          <a class="action-button" href="{_html_escape(_download_url(Path(image_url).name))}">Baixar JPG</a>
        </div>
        """
        preview = f"""
        <section class="preview">
          <img src="{_html_escape(image_url)}" alt="Story gerado">
          <div class="result">
            <span>Arquivo salvo</span>
            <strong>{_html_escape(file_path)}</strong>
            {image_actions}
            {link_block}
          </div>
        </section>
        """

    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Story Mercado Livre</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Arial, Segoe UI, sans-serif;
      background: #f7d800;
      color: #242424;
    }}
    .shell {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 34px 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
      gap: 28px;
      align-items: start;
    }}
    header {{
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0;
      font-size: 38px;
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .panel {{
      background: #ffffff;
      border: 2px solid #242424;
      border-radius: 8px;
      padding: 22px;
      box-shadow: 8px 8px 0 #242424;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 700;
      font-size: 15px;
    }}
    input {{
      width: 100%;
      height: 48px;
      border: 2px solid #242424;
      border-radius: 6px;
      padding: 0 12px;
      font: inherit;
      background: #fffef2;
    }}
    .row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 150px;
      gap: 12px;
      margin-top: 16px;
    }}
    .field {{
      margin-top: 16px;
    }}
    details {{
      margin-top: 16px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
    }}
    button {{
      margin-top: 20px;
      width: 100%;
      height: 52px;
      border: 0;
      border-radius: 6px;
      background: #00a650;
      color: #ffffff;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }}
    .image-actions {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 10px;
    }}
    .action-button {{
      display: grid;
      place-items: center;
      min-height: 42px;
      border-radius: 6px;
      background: #242424;
      color: #ffffff;
      font-weight: 800;
      text-decoration: none;
    }}
    .copy-link {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    .copy-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 96px;
      gap: 8px;
    }}
    .copy-row input {{
      height: 42px;
      font-size: 14px;
    }}
    .copy-button {{
      margin: 0;
      height: 42px;
      font-size: 14px;
    }}
    .status {{
      margin: 16px 0 0;
      padding: 12px;
      border-radius: 6px;
      font-weight: 700;
    }}
    .ok {{ background: #e5f7ed; color: #075c31; }}
    .error {{ background: #ffe7e7; color: #8a1010; }}
    .preview {{
      display: grid;
      gap: 14px;
    }}
    .preview img {{
      width: 100%;
      max-height: calc(100vh - 140px);
      object-fit: contain;
      background: #242424;
      border-radius: 8px;
      border: 2px solid #242424;
    }}
    .result {{
      background: #ffffff;
      border: 2px solid #242424;
      border-radius: 8px;
      padding: 14px;
      display: grid;
      gap: 6px;
    }}
    .result span {{
      font-size: 13px;
      font-weight: 700;
      color: #666666;
    }}
    .result strong {{
      font-size: 14px;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 860px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        font-size: 30px;
      }}
      .row {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section>
      <header>
        <h1>Story Mercado Livre</h1>
      </header>
      <form class="panel" method="post" action="/generate">
        <label for="link">Link do Mercado Livre</label>
        <input id="link" name="link" type="url" required autofocus value="{link_value}" placeholder="https://www.mercadolivre.com.br/...">

        <details{details_open}>
          <summary>Ajustes manuais</summary>
          <div class="row">
            <div>
              <label for="title">Titulo</label>
              <input id="title" name="title" type="text" value="{title_value}">
            </div>
            <div>
              <label for="price">Preco</label>
              <input id="price" name="price" type="number" min="0" step="0.01" value="{price_value}">
            </div>
          </div>
          <div class="field">
            <label for="thumbnail">Imagem</label>
            <input id="thumbnail" name="thumbnail" type="text" value="{thumbnail_value}">
          </div>
        </details>

        <button type="submit">Gerar Story</button>
        {status}
      </form>
    </section>
    {preview}
  </main>
  <script>
    async function copyStoryLink() {{
      const input = document.getElementById('story-link');
      if (!input) return;
      input.select();
      await navigator.clipboard.writeText(input.value);
    }}
  </script>
</body>
</html>"""
    return page.encode("utf-8")


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/stories/"):
            self._serve_story(download=False)
            return
        if self.path.startswith("/download/"):
            self._serve_story(download=True)
            return

        self._send_html(_render_page())

    def do_POST(self) -> None:
        if self.path != "/generate":
            self.send_error(404)
            return

        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = parse_qs(body)

        link = form.get("link", [""])[0].strip()
        title = form.get("title", [""])[0].strip()
        price = form.get("price", [""])[0].strip()
        thumbnail = form.get("thumbnail", [""])[0].strip()

        try:
            try:
                product = product_from_link(link)
            except Exception:
                if not title or not price:
                    raise
                product = Product(title, float(price.replace(",", ".")), link, thumbnail, 0, 1)

            if title:
                product = Product(title, product.price, product.permalink, product.thumbnail, 0, 1)
            if price:
                product = Product(product.title, float(price.replace(",", ".")), product.permalink, product.thumbnail, 0, 1)
            if thumbnail:
                product = Product(product.title, product.price, product.permalink, thumbnail, 0, 1)

            output_path = PROJECT_DIR / _story_output_path(str(OUTPUT_DIR), product.title, None)
            create_story(product, output_path)
            output_path.with_suffix(".txt").write_text(product.permalink, encoding="utf-8")
            self._send_html(
                _render_page(
                    message="Story pronto.",
                    image_url=_story_url(output_path),
                    file_path=str(output_path),
                    link_url=product.permalink,
                )
            )
        except Exception as exc:
            self._send_html(
                _render_page(
                    error=str(exc),
                    form={
                        "link": link,
                        "title": title,
                        "price": price,
                        "thumbnail": thumbnail,
                    },
                )
            )

    def _serve_story(self, download: bool) -> None:
        prefix = "/download/" if download else "/stories/"
        filename = Path(self.path.split(prefix, 1)[1]).name
        path = (STORIES_DIR / filename).resolve()
        if STORIES_DIR.resolve() not in path.parents or not path.exists():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        if download:
            self.send_header("content-disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="host do servidor local")
    parser.add_argument("--port", default=int(os.getenv("PORT", "5055")), type=int, help="porta do servidor local")
    args = parser.parse_args()

    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"App aberto em http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
