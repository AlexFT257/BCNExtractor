import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_norm_manager
from api.routers import instituciones, normas

app = FastAPI(
    title="BCNExtractor API",
    description="API para consulta de normas legales chilenas extraídas desde la BCN.",
    version="1.0.0",
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["sistema"])
def health_check():
    try:
        # Verifica que la DB responde, no solo que el proceso está vivo
        manager = get_norm_manager()
        stats = manager.get_stats()
        return {
            "status": "ok",
            "database": "ok",
            "normas_total": stats["total"],
        }
    except Exception as e:
        from fastapi import Response

        return Response(
            content=f'{{"status": "error", "detail": "{str(e)}"}}',
            status_code=503,
            media_type="application/json",
        )


app.include_router(normas.router)
app.include_router(instituciones.router)
