import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_start = time.time()

app = FastAPI(title="Creative Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Import and register routes after app is created to avoid circular imports
# Use absolute imports for Vercel compatibility (relative imports fail in serverless)
from routes.upload import router as upload_router
from routes.rescore import router as rescore_router

app.include_router(upload_router, prefix="/api")
app.include_router(rescore_router, prefix="/api")


@app.get("/api/health")
def health():
    uptime = round(time.time() - _start, 1)
    return {"status": "ok", "uptime_s": uptime}


from routes.diagnostics import router as diag_router
from routes.splits import router as splits_router

app.include_router(diag_router, prefix="/api")
app.include_router(splits_router, prefix="/api")
