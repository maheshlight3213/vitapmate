from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import os

# Try to import the vtop client
try:
    from vitap_vtop_client.client import VtopClient
    from vitap_vtop_client.exceptions import VitapVtopClientError, VtopLoginError
    VTOP_AVAILABLE = True
except ImportError:
    VTOP_AVAILABLE = False
    print("WARNING: vitap-vtop-client not installed. Install with: pip install git+https://github.com/Udhay-Adithya/vitap-vtop-client.git@main")

app = FastAPI(title="VITAPMate API", version="1.0.0")

# Allow all origins so your iPhone Safari can call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    registration_number: str
    password: str

class DataRequest(BaseModel):
    registration_number: str
    password: str
    sem_sub_id: str  # e.g. "AP2024252" for Fall 2024-25

# ── Helper: get current semester ID ──────────────────────────────────────────

def guess_sem_id() -> str:
    """Return current semester sub ID based on current month."""
    from datetime import datetime
    now = datetime.now()
    year = now.year
    month = now.month
    # Fall semester: July-Nov => "AP{year}{year+1}2"
    # Winter semester: Dec-Apr => "AP{year-1}{year}5" or similar
    if 7 <= month <= 11:
        return f"AP{year}{str(year+1)[-2:]}2"
    elif month <= 4:
        return f"AP{year-1}{str(year)[-2:]}5"
    else:
        return f"AP{year}{str(year+1)[-2:]}2"

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "vtop_client": VTOP_AVAILABLE}

@app.get("/sem_id")
async def get_sem_id():
    return {"sem_sub_id": guess_sem_id()}

@app.post("/login")
async def login(req: LoginRequest):
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            profile = await client.get_profile()
            return {"success": True, "profile": profile}
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/attendance")
async def get_attendance(req: DataRequest):
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            data = await client.get_attendance(sem_sub_id=req.sem_sub_id)
            return {"success": True, "attendance": data}
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/timetable")
async def get_timetable(req: DataRequest):
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            data = await client.get_timetable(sem_sub_id=req.sem_sub_id)
            return {"success": True, "timetable": data}
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/marks")
async def get_marks(req: DataRequest):
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            data = await client.get_marks(sem_sub_id=req.sem_sub_id)
            return {"success": True, "marks": data}
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/exam_schedule")
async def get_exam_schedule(req: DataRequest):
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            data = await client.get_exam_schedule(sem_sub_id=req.sem_sub_id)
            return {"success": True, "exam_schedule": data}
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/grades")
async def get_grades(req: LoginRequest):
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            data = await client.get_grade_history()
            return {"success": True, "grades": data}
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/all")
async def get_all_data(req: DataRequest):
    """Fetch everything in parallel — fastest for initial load."""
    if not VTOP_AVAILABLE:
        raise HTTPException(503, "vitap-vtop-client not installed on server")
    try:
        async with VtopClient(req.registration_number, req.password) as client:
            profile, attendance, timetable, marks, exams, grades = await asyncio.gather(
                client.get_profile(),
                client.get_attendance(sem_sub_id=req.sem_sub_id),
                client.get_timetable(sem_sub_id=req.sem_sub_id),
                client.get_marks(sem_sub_id=req.sem_sub_id),
                client.get_exam_schedule(sem_sub_id=req.sem_sub_id),
                client.get_grade_history(),
                return_exceptions=True
            )
            return {
                "success": True,
                "profile": profile if not isinstance(profile, Exception) else None,
                "attendance": attendance if not isinstance(attendance, Exception) else [],
                "timetable": timetable if not isinstance(timetable, Exception) else {},
                "marks": marks if not isinstance(marks, Exception) else [],
                "exam_schedule": exams if not isinstance(exams, Exception) else [],
                "grades": grades if not isinstance(grades, Exception) else None,
            }
    except VtopLoginError as e:
        raise HTTPException(401, f"Login failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

# ── Serve the frontend HTML ───────────────────────────────────────────────────

frontend_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
