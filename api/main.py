from fastapi import FastAPI

from api.routers import instituciones, normas

app = FastAPI(
    title="BCNExtractor API",
    description="API para consulta de normas legales chilenas extraídas desde la BCN.",
    version="1.0.0",
)

app.include_router(normas.router)
app.include_router(instituciones.router)