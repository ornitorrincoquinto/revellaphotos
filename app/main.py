import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .database import Base, engine
from .storage import ensure_dirs
from .routers import auth, galleries, events

# Cria as tabelas automaticamente se ainda não existirem. Pra um projeto que
# vai evoluir bastante, o ideal futuro é migrar para o Alembic (migrações
# versionadas), mas isso é suficiente pra colocar o produto de pé agora.
Base.metadata.create_all(bind=engine)
ensure_dirs()

app = FastAPI(
    title="Revela API",
    description="Backend de prova e entrega de fotos, com seleção paga por extras e busca de fotos por reconhecimento facial.",
    version="1.0.0",
)

origins = [o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve as imagens de pré-visualização (baixa resolução + marca d'água).
# Os arquivos originais em alta resolução NÃO são servidos aqui — ficam fora
# do StaticFiles, acessíveis só via lógica autenticada (a implementar quando
# o fluxo de pagamento/entrega final for definido).
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

app.include_router(auth.router)
app.include_router(galleries.router)
app.include_router(events.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend (site) servido pelo mesmo serviço, pra ficar tudo num deploy só.
# Precisa ser a ÚLTIMA rota registrada: como é um catch-all (qualquer caminho
# que não bateu com nada acima cai aqui), se viesse antes ele "roubaria" as
# rotas da API. O JS do frontend decide o que mostrar olhando a URL
# (ex: /e/<slug> abre a busca facial do evento, /g/<codigo> abre a galeria).
# ---------------------------------------------------------------------------
FRONTEND_INDEX = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    if os.path.exists(FRONTEND_INDEX):
        return FileResponse(FRONTEND_INDEX)
    return {"detail": "Frontend não encontrado — verifique se a pasta frontend/ foi copiada no build."}
