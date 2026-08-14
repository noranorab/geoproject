from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wildfirewatch.api.routers import detections, scenes

app = FastAPI(title="WildfireWatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenes.router)
app.include_router(detections.router)


@app.get("/health")
def health():
    return {"status": "ok"}
