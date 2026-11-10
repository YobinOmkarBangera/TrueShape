"""TrueShape API (FastAPI). Start with:  python run.py"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .service import Store, SCENARIOS, STARTS
from . import engine as E
from . import simulator as Sim

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app = FastAPI(title="TrueShape API", version="2.0",
              description="Merchant-business mismatch monitoring. Team Dhurandhar, Follow The Money 2026.")
_store: Optional[Store] = None


def S() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _check_merchant(mid):
    if mid not in S().res:
        raise HTTPException(404, f"No shop with id {mid}.")


def _check_group(category, city):
    if category not in Sim.CATEGORIES:
        raise HTTPException(400, f"Unknown category. Use one of: {', '.join(Sim.CATEGORIES)}.")
    if city not in Sim.CITIES:
        raise HTTPException(400, f"Unknown city. Use one of: {', '.join(Sim.CITIES)}.")


@app.get("/api/health")
def health():
    return {"ok": True, "shops": len(S().merchants), "today": S().iso(S().today)}


@app.get("/api/meta")
def meta():
    return S().meta()


@app.get("/api/overview")
def overview():
    return S().overview()


@app.get("/api/profiles")
def profiles():
    return S().profiles()


@app.get("/api/results")
def results():
    return S().results()


@app.get("/api/merchants/{mid}")
def merchant(mid: str):
    _check_merchant(mid)
    return S().merchant(mid)


class Reply(BaseModel):
    reason: str


@app.post("/api/merchants/{mid}/reply")
def reply(mid: str, body: Reply):
    _check_merchant(mid)
    if body.reason not in E.REPLIES:
        raise HTTPException(400, f"Unknown answer. Use one of: {', '.join(E.REPLIES)}.")
    return S().reply(mid, body.reason)


class Simulate(BaseModel):
    category: str
    city: str
    scenario: str
    start: str = "mid"
    seed: Optional[int] = None


@app.post("/api/simulate")
def simulate(body: Simulate):
    _check_group(body.category, body.city)
    if body.scenario not in [s[0] for s in SCENARIOS[body.category]]:
        raise HTTPException(400, "That scenario does not exist for this category.")
    if body.start not in STARTS:
        raise HTTPException(400, f"Unknown start. Use one of: {', '.join(STARTS)}.")
    return S().simulate(body.category, body.city, body.scenario, body.start, body.seed)


@app.get("/api/sample.csv")
def sample():
    return Response(S().sample_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sample_shop_M004.csv"})


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), category: str = Form("bakery"), city: str = Form("Hyderabad")):
    _check_group(category, city)
    raw = await file.read()
    if len(raw) > 30 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 30 MB. Upload one shop's payments.")
    try:
        return S().analyze(raw, file.filename or "upload.csv", category, city)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Could not read that file. Upload a CSV with timestamp, amount_inr and payer_id columns.")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
