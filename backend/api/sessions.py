"""REST admin + público — ver T2.5.

Contrato de endpoints (congelado en T0.5):

| Método   | Ruta                                              | Auth  | Uso                              |
|----------|----------------------------------------------------|-------|-----------------------------------|
| GET      | /healthz                                            | --    | Healthcheck                       |
| GET      | /api/public/sessions                                | --    | Lista pública: id, título, orador, idiomas, estado |
| POST     | /api/sessions                                       | admin | Crear sala                        |
| POST     | /api/sessions/{id}/start                            | admin | Arrancar                          |
| POST     | /api/sessions/{id}/stop                             | admin | Parar                             |
| DELETE   | /api/sessions/{id}                                  | admin | Borrar                            |
| GET      | /api/sessions                                       | admin | Estado completo + métricas        |
| POST     | /api/uploads                                        | admin | Subir mp3                         |
| GET      | /api/sessions/{id}/export.{srt,vtt,txt,md}?lang=    | --    | Exports                           |
| GET      | /api/sessions/{id}/knowledge                        | --    | Knowledge Pack                    |
| POST     | /api/sessions/{id}/ask                              | -- (rate limit) | Preguntale a la charla   |
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/healthz")
def healthz(request: Request) -> dict:
    return {"ok": True, "engine": request.app.state.settings.engine}


@router.get("/api/public/sessions")
def public_sessions(request: Request) -> list[dict]:
    return [s.public_info() for s in request.app.state.manager.list()]
