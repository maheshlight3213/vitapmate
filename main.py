from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio, os

try:
    from vitap_vtop_client.client import VtopClient
    from vitap_vtop_client.exceptions import VtopLoginError
    VTOP_OK = True
except ImportError:
    VTOP_OK = False

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class LoginReq(BaseModel):
    registration_number: str
    password: str

class DataReq(BaseModel):
    registration_number: str
    password: str
    sem_sub_id: str

@app.get("/", response_class=HTMLResponse)
async def frontend():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path) as f:
        return f.read()

@app.get("/health")
async def health():
    return {"ok": True, "vtop": VTOP_OK}

@app.post("/login")
async def login(r: LoginReq):
    if not VTOP_OK:
        raise HTTPException(503, "vtop client not installed")
    try:
        async with VtopClient(r.registration_number, r.password) as c:
            return {"success": True, "profile": await c.get_profile()}
    except VtopLoginError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/attendance")
async def attendance(r: DataReq):
    if not VTOP_OK:
        raise HTTPException(503, "vtop client not installed")
    try:
        async with VtopClient(r.registration_number, r.password) as c:
            return {"success": True, "attendance": await c.get_attendance(sem_sub_id=r.sem_sub_id)}
    except VtopLoginError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/timetable")
async def timetable(r: DataReq):
    if not VTOP_OK:
        raise HTTPException(503, "vtop client not installed")
    try:
        async with VtopClient(r.registration_number, r.password) as c:
            return {"success": True, "timetable": await c.get_timetable(sem_sub_id=r.sem_sub_id)}
    except VtopLoginError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/marks")
async def marks(r: DataReq):
    if not VTOP_OK:
        raise HTTPException(503, "vtop client not installed")
    try:
        async with VtopClient(r.registration_number, r.password) as c:
            return {"success": True, "marks": await c.get_marks(sem_sub_id=r.sem_sub_id)}
    except VtopLoginError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/exam_schedule")
async def exams(r: DataReq):
    if not VTOP_OK:
        raise HTTPException(503, "vtop client not installed")
    try:
        async with VtopClient(r.registration_number, r.password) as c:
            return {"success": True, "exam_schedule": await c.get_exam_schedule(sem_sub_id=r.sem_sub_id)}
    except VtopLoginError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
