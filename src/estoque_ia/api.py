import hmac
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from estoque_ia import __version__
from estoque_ia.agente import (
    Agente,
    ClienteLLM,
    ClienteOllama,
    ErroClienteLLM,
    Resposta,
)
from estoque_ia.config import Config, carregar_config
from estoque_ia.db import conectar
from estoque_ia.ferramentas import resumo_estoque


class PerguntarBody(BaseModel):
    pergunta: str = Field(min_length=1, max_length=1000)

    def model_post_init(self, __context) -> None:
        if self.pergunta.strip() == "":
            raise ValueError
        object.__setattr__(self, "pergunta", self.pergunta.strip())


def _abrir_banco(cfg: Config) -> sqlite3.Connection:
    """Abre uma conexão nova; banco ausente vira 503, não stack trace."""
    if not Path(cfg.db_path).exists():
        raise HTTPException(status_code=503, detail="Banco nao encontrado. Rode o seed.")
    try:
        return conectar(cfg.db_path, somente_leitura=True)
    except sqlite3.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Banco nao encontrado. Rode o seed.",
        ) from exc


def criar_app(
    config: Config | None = None,
    cliente: ClienteLLM | None = None,
) -> FastAPI:
    app = FastAPI(title="Estoque IA")
    cfg = config or carregar_config()

    @app.get("/saude")
    def saude() -> dict:
        # Healthcheck de propósito: não toca no banco nem no Ollama.
        return {"status": "ok", "versao": __version__}

    @app.get("/resumo")
    def resumo() -> dict:
        conn = _abrir_banco(cfg)
        try:
            return resumo_estoque(conn)
        finally:
            conn.close()

    @app.post("/perguntar")
    def perguntar(
        body: PerguntarBody,
        x_api_token: str | None = Header(default=None),
    ) -> dict:
        if cfg.api_token:
            # compare_digest evita vazar o token por diferença de tempo.
            if x_api_token is None or not hmac.compare_digest(
                str(x_api_token),
                str(cfg.api_token),
            ):
                raise HTTPException(status_code=401, detail="Token invalido.")

        # Uma conexão por requisição: sem estado compartilhado entre perguntas.
        conn = _abrir_banco(cfg)

        try:
            cl = cliente

            # O cliente é caro de criar; fica no app.state e é reutilizado.
            if cl is None:
                if not hasattr(app.state, "cliente"):
                    app.state.cliente = ClienteOllama(base_url=cfg.ollama_base_url)
                cl = app.state.cliente

            ag = Agente(
                conn=conn,
                cliente=cl,
                modelo=cfg.modelo,
                max_iteracoes=cfg.max_iteracoes,
            )

            try:
                r: Resposta = ag.perguntar(body.pergunta)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from exc
            except ErroClienteLLM as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Erro ao consultar o Ollama.",
                ) from exc

            ferramentas_usadas = [
                {
                    "nome": c.nome,
                    "argumentos": c.argumentos,
                    "erro": c.erro,
                    "resultado": getattr(c, "resultado", None),
                }
                for c in r.ferramentas_usadas
            ]

            return {
                "resposta": r.texto,
                "ferramentas_usadas": ferramentas_usadas,
                "incompleta": r.incompleta,
            }
        finally:
            conn.close()

    @app.get("/")
    def raiz() -> FileResponse:
        static_path = Path(__file__).parent / "static" / "index.html"
        return FileResponse(static_path)

    return app


app = criar_app()
