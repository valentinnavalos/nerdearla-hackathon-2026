"""WS ingest / captions / admin / audio — ver T1.11 / T2.6.

Contrato de endpoints (congelado en T0.5):

| Método | Ruta                        | Auth  | Uso                             |
|--------|------------------------------|-------|-----------------------------------|
| WS     | /ws/ingest/{id}?token=       | admin | Audio del mic                    |
| WS     | /ws/captions/{id}?lang=      | --    | Subtítulos                       |
| WS     | /ws/admin?token=             | admin | Snapshot de estado cada 1 s      |
"""
