# Automacao Mercado Livre para Stories do Instagram

Projeto simples para buscar produtos no Mercado Livre, gerar uma imagem vertical de story e publicar no Instagram usando a API oficial.

## Requisitos

- Python 3.10+
- Conta Instagram profissional, do tipo Business ou Creator
- Conta conectada a uma Pagina do Facebook
- App Meta com permissao de publicacao no Instagram
- Um access token valido do Instagram Graph API
- Um access token do Mercado Livre, caso a busca publica retorne `403 Forbidden`
- Uma URL publica para hospedar a imagem do story antes da publicacao

Observacao: o Instagram Graph API publica midias a partir de URLs publicas. Arquivo local no celular nao basta para publicacao automatica via API.

## Instalar

```sh
cd ~/storage/shared/Projetos/ml-instagram-stories
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edite o arquivo `.env` com suas configuracoes.

## Abrir o app local

No Windows, de dois cliques em:

```text
abrir_app.bat
```

Ou rode pelo terminal:

```sh
.\.venv\Scripts\python.exe src\app.py
```

Depois acesse:

```text
http://127.0.0.1:5055
```

Cole o link do Mercado Livre e clique em `Gerar Story`. O app tenta puxar titulo, preco e imagem automaticamente, gera o QR Code com o proprio link e salva o JPG em `output/stories`.

## Usar pelo celular na mesma rede Wi-Fi

Este e o melhor caminho para postar no Instagram pelo celular sem instalar Python no telefone.

No Windows, de dois cliques em:

```text
abrir_no_celular.bat
```

Depois descubra o IP do computador:

```powershell
ipconfig
```

Procure o `Endereco IPv4` da rede Wi-Fi, por exemplo `192.168.0.25`.

No navegador do celular, abra:

```text
http://192.168.0.25:5055
```

Use o app pelo celular, gere o story, salve a imagem no telefone e publique no Instagram com o sticker de link.

Se o celular nao abrir, confira se PC e celular estao na mesma rede Wi-Fi e permita o Python no Firewall do Windows.

## Usar de qualquer lugar, sem depender do PC

Para usar fora de casa, o melhor caminho e hospedar este app como um web app online. Assim voce abre pelo navegador do celular, cola o link do Mercado Livre, gera o story, baixa o JPG no celular e posta pelo Instagram.

O projeto ja esta preparado para hospedagens que usam a variavel `PORT`, como Render, Railway, Fly.io e servicos parecidos.

Arquivos incluidos para deploy:

```text
Procfile
render.yaml
```

### Deploy sugerido no Render

1. Crie um repositorio no GitHub com este projeto.
2. Acesse o Render.
3. Crie um novo `Web Service`.
4. Conecte o repositorio do GitHub.
5. Use:

```text
Build Command: pip install -r requirements.txt
Start Command: python -B src/app.py --host 0.0.0.0
```

Depois do deploy, o Render vai gerar uma URL parecida com:

```text
https://ml-instagram-stories.onrender.com
```

Abra essa URL no celular e use normalmente.

Observacao: os stories gerados ficam temporariamente no servidor. Sempre baixe o JPG no celular logo depois de gerar.

## Rodar direto no Android

No Android, o caminho mais simples e usar Termux:

```sh
pkg update
pkg install python git
cd /sdcard/Download/ml-instagram-stories
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python src/app.py --host 127.0.0.1 --port 5055
```

Depois abra no navegador do proprio Android:

```text
http://127.0.0.1:5055
```

## Rodar direto no iPhone

No iPhone, rodar este projeto localmente e mais limitado porque ele depende de Python com bibliotecas de imagem. O fluxo recomendado no iOS e usar o app rodando no PC pela rede Wi-Fi, abrir pelo Safari do iPhone, salvar o story no rolo da camera e postar no Instagram.

## Gerar story pelo terminal

Este e o fluxo mais simples: o script gera um JPG vertical pronto para story e salva em `output/stories`.

Com apenas o link do Mercado Livre:

```sh
python src/main.py --dry-run --from-link "https://www.mercadolivre.com.br/..."
```

Com dados manuais:

```sh
python src/main.py --dry-run --title "Produto em oferta" --price 199.90 --link "https://www.mercadolivre.com.br/"
```

Com imagem do produto por URL:

```sh
python src/main.py --dry-run --title "Produto em oferta" --price 199.90 --link "https://www.mercadolivre.com.br/" --thumbnail "https://exemplo.com/produto.jpg"
```

Com imagem salva no computador:

```sh
python src/main.py --dry-run --title "Produto em oferta" --price 199.90 --link "https://www.mercadolivre.com.br/" --thumbnail "C:\Users\SeuUsuario\Pictures\produto.jpg"
```

Cada execucao cria um arquivo novo em `output/stories`, sem sobrescrever o anterior.

## Testar sem produto real

```sh
python src/main.py --dry-run
```

Isso busca um produto e gera uma imagem local.

Para testar apenas o layout, sem chamar a API do Mercado Livre:

```sh
python src/main.py --sample --dry-run
```

## Publicar

Para publicar automaticamente, a imagem gerada precisa estar acessivel em uma URL publica.

Voce tem duas opcoes:

- `UPLOAD_ENDPOINT`: o script envia a imagem para o Wix e usa a URL retornada.
- `PUBLIC_BASE_URL`: voce hospeda a imagem por outro caminho e informa a pasta publica.

Exemplo:

```sh
PUBLIC_BASE_URL=https://seu-dominio.com/stories python src/main.py
```

O script vai tentar publicar `https://seu-dominio.com/stories/story.jpg`.

Com upload automatico:

```env
UPLOAD_ENDPOINT=https://www.marcelocell.com.br/_functions/storyUpload
UPLOAD_SECRET=troque-por-uma-senha-forte
```

## Endpoint Wix Velo

No painel do Wix, ative o Velo e crie/edite o arquivo `backend/http-functions.js`.

Cole o endpoint abaixo e publique o site:

```js
import { ok, forbidden, serverError } from 'wix-http-functions';
import { mediaManager } from 'wix-media-backend';

const UPLOAD_SECRET = 'troque-por-uma-senha-forte';

export async function post_storyUpload(request) {
  try {
    if (request.headers['x-upload-secret'] !== UPLOAD_SECRET) {
      return forbidden({ body: { error: 'forbidden' } });
    }

    const body = await request.body.buffer();
    const fileName = `story-${Date.now()}.jpg`;
    const uploaded = await mediaManager.upload(
      '/stories',
      body,
      fileName,
      {
        mediaOptions: {
          mimeType: 'image/jpeg',
          mediaType: 'image'
        },
        metadataOptions: {
          isPrivate: false,
          isVisitorUpload: false
        }
      }
    );

    return ok({ body: { url: uploaded.fileUrl } });
  } catch (error) {
    return serverError({ body: { error: String(error) } });
  }
}
```

Depois teste:

```sh
python src/main.py --sample --dry-run
```

## Rodar todos os dias no Termux

Uma opcao simples e usar `cronie`:

```sh
pkg install cronie
crond
crontab -e
```

Exemplo para rodar todo dia as 9h:

```cron
0 9 * * * cd /data/data/com.termux/files/home/storage/shared/Projetos/ml-instagram-stories && . .venv/bin/activate && python src/main.py
```
