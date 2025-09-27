from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from api.routers.health import router as health_router
from api.routers.ingest import router as ingest_router
from api.routers.analyze import router as analyze_router

from api.routers import ingest_pdf # add import


app = FastAPI(title="CivicSense API", version="0.1.0")

@app.get("/", response_class=JSONResponse)
async def read_root(request: Request):
        """Root endpoint: returns HTML page with a button linking to /docs when the client accepts HTML.

        If the client prefers JSON (default for API clients), return a JSON message instead.
        """
        accept = request.headers.get("accept", "")
        html_content = """
        <!doctype html>
        <html>
            <head>
                <meta charset="utf-8" />
                <title>CivicSense API</title>
                <style>
                    body { font-family: Arial, sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; background:#f7f7f7 }
                    .card { background:white; padding:24px; border-radius:8px; box-shadow:0 6px 18px rgba(0,0,0,0.08); text-align:center }
                    .btn { display:inline-block; padding:12px 20px; background:#007ACC; color:white; text-decoration:none; border-radius:6px }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Welcome to the CivicSense API</h1>
                    <p>Click the button to open the interactive API docs.</p>
                    <a class="btn" href="/docs" target="_blank">Open API Docs (Swagger)</a>
                </div>
            </body>
        </html>
        """

        # If the client wants HTML, send HTML; otherwise JSON
        if "text/html" in accept.lower() or "*/*" in accept:
                return HTMLResponse(content=html_content)

        return JSONResponse({"message": "Welcome to the CivicSense API! Please refer to /docs for API documentation."})

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(analyze_router)
app.include_router(ingest_pdf.router)