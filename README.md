# Revela

Site completo de prova e entrega de fotos — frontend e backend num serviço
só (o FastAPI serve tanto a API quanto o site). Você publica uma vez e já
tem tudo funcionando na mesma URL. Dois fluxos principais:

1. **Galeria com seleção** (o que já existia no protótipo): fotógrafo sobe fotos
   de um ensaio, define quantas estão inclusas no pacote e o valor da extra.
   O cliente entra com um código, marca as fotos e vê o valor adicional em
   tempo real.
2. **Evento com busca facial** (novo): fotógrafo sobe todas as fotos de um
   evento/campeonato de uma vez. Compartilha um **link público** (sem
   código). Qualquer pessoa entra, envia uma selfie e recebe só as fotos em
   que ela aparece.

Em **todos** os casos, o que é exibido publicamente é sempre a versão em
baixa resolução com marca d'água — o arquivo original em alta resolução fica
guardado no servidor e não é servido por nenhuma rota pública.

O reconhecimento facial usa a biblioteca open-source `face_recognition`
(baseada em dlib), rodando inteiramente no seu próprio servidor — sem
mensalidade nem custo por foto processada.

## Como está organizado

```
app/
  main.py         # cria o app, monta as rotas, serve o frontend e os arquivos estáticos
  config.py       # todas as variáveis de ambiente (nada de valor fixo no código)
  database.py     # conexão com o banco (SQLite local / Postgres em produção)
  models.py       # tabelas: fotógrafos, galerias, fotos, seleções, eventos, encodings faciais
  schemas.py      # formatos de entrada/saída da API
  security.py     # hash de senha + JWT
  deps.py         # dependência que valida o fotógrafo autenticado
  storage.py      # onde os arquivos são salvos e como as URLs públicas são montadas
  imaging.py      # redimensionamento + marca d'água (Pillow)
  face_engine.py  # extração e comparação de rostos (face_recognition)
  routers/
    auth.py       # cadastro / login do fotógrafo
    galleries.py  # fluxo de seleção com cobrança de extras
    events.py     # fluxo de evento com busca facial
frontend/
  index.html      # o site inteiro (fotógrafo + cliente), fala com a API por fetch()
```

O `index.html` é servido pela própria API (mesma origem, mesma porta) — não
existe CORS a configurar nem outro serviço pra publicar. Os links que você
compartilha com clientes já saem prontos: `/g/<código>` para galerias de
seleção e `/e/<slug>` para eventos com busca facial.

## Rodando localmente (pra testar antes de publicar)

Pré-requisitos: Docker instalado (mais simples — evita ter que compilar o
dlib manualmente na sua máquina).

```bash
cp .env.example .env
docker build -t revela-backend .
docker run --rm -p 8000:8000 --env-file .env -v $(pwd)/media:/app/media revela-backend
```

Depois abra `http://localhost:8000` — é o site completo, já no ar. Se quiser
mexer diretamente na API (pra depurar algo), `http://localhost:8000/docs` tem
uma tela interativa com todos os endpoints.

## Publicando de verdade (caminho mais simples: Railway)

Você pediu o caminho mais simples possível pra colocar no ar — o Railway é
uma boa escolha porque ele lê o `Dockerfile` sozinho, oferece Postgres com um
clique e permite anexar um volume persistente pelas configurações, sem
precisar escrever nenhum YAML de infraestrutura.

1. **Crie uma conta** em railway.app e um novo projeto.
2. **Suba este código pra um repositório no GitHub** (ou use o "Deploy from
   local directory" do Railway, se preferir não usar GitHub agora).
3. No projeto, clique em **"New" → "GitHub Repo"** e selecione o repositório.
   O Railway detecta o `Dockerfile` automaticamente e já builda.
4. Clique em **"New" → "Database" → "PostgreSQL"** dentro do mesmo projeto.
   Isso cria o banco e já disponibiliza a variável `DATABASE_URL` — no
   serviço do backend, em **Variables**, adicione uma referência a ela
   (`${{Postgres.DATABASE_URL}}`) ou copie o valor gerado.
5. **Importantíssimo — volume persistente para as fotos:** no serviço do
   backend, vá em **Settings → Volumes → New Volume**, monte em `/app/media`.
   Sem isso, toda vez que você fizer um novo deploy as fotos enviadas somem
   (o container é recriado do zero).
6. Em **Variables**, defina pelo menos:
   - `DATABASE_URL` (do passo 4)
   - `JWT_SECRET` (gere algo aleatório, ex: `openssl rand -hex 32`)
   - `MEDIA_ROOT=/app/media`
   - `WATERMARK_TEXT` (nome do seu estúdio, se quiser)
   - `CORS_ORIGINS` (o domínio do seu frontend quando ele estiver publicado;
     use `*` enquanto estiver testando)
7. O Railway vai te dar uma URL pública (`https://seu-projeto.up.railway.app`).
   Teste em `/health` — deve responder `{"status":"ok"}`. Em `/docs` você
   tem a documentação interativa da API já no ar.

A primeira build demora mais (uns 5–10 minutos) porque o dlib é compilado do
zero. As próximas builds usam cache e são bem mais rápidas.

## Sobre o reconhecimento facial (o que esperar)

- Funciona bem com selfies de frente, com boa iluminação.
- A tolerância de comparação (`FACE_MATCH_TOLERANCE`, padrão `0.6`) é o
  principal ajuste fino: baixar o valor reduz falsos positivos mas pode
  deixar de encontrar fotos em ângulos ruins; subir faz o oposto.
- A busca hoje compara a selfie contra **todos** os rostos já processados do
  evento, um a um. Para eventos de até alguns milhares de fotos isso roda em
  segundos. Se algum dia vocês tiverem eventos gigantes (dezenas de milhares
  de fotos), a evolução natural é indexar os vetores num banco com suporte a
  busca vetorial (ex: `pgvector` no Postgres) — o modelo de dados aqui já foi
  desenhado pra permitir essa migração sem redesenhar tudo.
- Processar o reconhecimento facial no upload deixa o envio de fotos mais
  lento (alguns segundos por foto). Isso é esperado rodando em CPU.

## Próximos passos sugeridos

- Cobrança de pagamento pelas fotos extras — combinamos de deixar pra uma
  próxima etapa.
- Endpoint autenticado de download do arquivo original em alta resolução
  (hoje só o fotógrafo tem acesso a esses arquivos em disco).
- Domínio próprio (o Railway já entrega um subdomínio `.up.railway.app`
  funcional, mas dá pra apontar um domínio seu depois em Settings → Networking).
