from fastapi import FastAPI

from .routes import router

app = FastAPI(title="Epicrisis extraction API")
app.include_router(router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
