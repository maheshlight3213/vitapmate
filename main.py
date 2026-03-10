from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio, os, httpx
from bs4 import BeautifulSoup

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

try:
    from vitap_vtop_client.client import VtopClient
    from vitap_vtop_client.exceptions import VtopLoginError
    VTOP_LIB = True
except ImportError:
    VTOP_LIB = False

VTOP_BASE = "https://vtop1.vitap.ac.in/vtop"
HEADERS = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}

class LoginReq(BaseModel):
    registration_number: str
    password: str

class DataReq(BaseModel):
    registration_number: str
    password: str
    sem_sub_id: str

async def vtop_session(reg, pwd):
    client = httpx.AsyncClient(base_url=VTOP_BASE, headers=HEADERS, follow_redirects=True, timeout=30.0, verify=False)
    for attempt in range(3):
        try:
            r = await client.get("/initialProcess")
            break
        except Exception as e:
            if attempt == 2:
                await client.aclose()
                raise HTTPException(503, f"Cannot reach VTOP: {e}")
            await asyncio.sleep(2)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    csrf = ""
    t = soup.find("input", {"name": "_csrf"})
    if t: csrf = t.get("value", "")
    else:
        m = soup.find("meta", {"name": "_csrf"})
        if m: csrf = m.get("content", "")
    data = {"uname": reg, "passwd": pwd, "_csrf": csrf, "authorizedID": reg}
    r2 = await client.post("/login", data=data)
    if "invalid" in r2.text.lower() or "wrong" in r2.text.lower():
        await client.aclose()
        raise HTTPException(401, "Wrong username or password")
    if "logout" not in r2.text.lower():
        r2 = await client.post("/doLogin", data=data)
        if "logout" not in r2.text.lower():
            await client.aclose()
            raise HTTPException(401, "Login failed - check your credentials")
    return client

async def scrape_profile(client, reg):
    try:
        r = await client.post("/processViewStudentProfile", data={"authorizedID": reg})
        soup = BeautifulSoup(r.text, "html.parser")
        d = {}
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                d[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
        return {
            "student_name": d.get("Student Name", reg),
            "registration_number": reg,
            "program": d.get("Programme", ""),
            "branch": d.get("Branch", ""),
            "semester": d.get("Semester", ""),
            "school": d.get("School", ""),
            "mentor": d.get("Faculty Mentor", ""),
            "email": d.get("Email", f"{reg.lower()}@vitapstudent.ac.in"),
            "cgpa": d.get("CGPA", ""),
            "credits_earned": d.get("Credits Earned", ""),
            "hostel": d.get("Hostel Block", ""),
            "dob": d.get("Date of Birth", ""),
        }
    except Exception as e:
        return {"student_name": reg, "registration_number": reg}

async def scrape_table(client, endpoint, reg, sem, mapper):
    r = await client.post(endpoint, data={"authorizedID": reg, "semesterSubId": sem})
    soup = BeautifulSoup(r.text, "html.parser")
    result = []
    for row in soup.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) >= 4:
            try:
                result.append(mapper(cells))
            except:
                continue
    return result

@app.get("/", response_class=HTMLResponse)
async def frontend():
    with open(os.path.join(os.path.dirname(__file__), "index.html")) as f:
        return f.read()

@app.get("/health")
async def health():
    return {"ok": True, "vtop_lib": VTOP_LIB}

@app.post("/login")
async def login(r: LoginReq):
    if VTOP_LIB:
        try:
            async with VtopClient(r.registration_number, r.password) as c:
                return {"success": True, "profile": await c.get_profile()}
        except: pass
    client = await vtop_session(r.registration_number, r.password)
    try:
        return {"success": True, "profile": await scrape_profile(client, r.registration_number)}
    finally:
        await client.aclose()

@app.post("/attendance")
async def attendance(r: DataReq):
    if VTOP_LIB:
        try:
            async with VtopClient(r.registration_number, r.password) as c:
                return {"success": True, "attendance": await c.get_attendance(sem_sub_id=r.sem_sub_id)}
        except: pass
    client = await vtop_session(r.registration_number, r.password)
    try:
        def mapper(c):
            att, tot = int(c[4]) if c[4].isdigit() else 0, int(c[5]) if c[5].isdigit() else 0
            return {"course_code": c[1], "course_title": c[2], "course_type": c[3],
                    "faculty": c[6] if len(c)>6 else "", "slot": c[7] if len(c)>7 else "",
                    "attended": att, "total": tot, "percentage": round(att/tot*100,1) if tot else 0}
        data = await scrape_table(client, "/processViewStudentAttendance", r.registration_number, r.sem_sub_id, mapper)
        return {"success": True, "attendance": data}
    finally:
        await client.aclose()

@app.post("/timetable")
async def timetable(r: DataReq):
    if VTOP_LIB:
        try:
            async with VtopClient(r.registration_number, r.password) as c:
                return {"success": True, "timetable": await c.get_timetable(sem_sub_id=r.sem_sub_id)}
        except: pass
    client = await vtop_session(r.registration_number, r.password)
    try:
        resp = await client.post("/processViewTimeTable", data={"authorizedID": r.registration_number, "semesterSubId": r.sem_sub_id})
        soup = BeautifulSoup(resp.text, "html.parser")
        tt = {"MON":[],"TUE":[],"WED":[],"THU":[],"FRI":[],"SAT":[]}
        dm = {"Monday":"MON","Tuesday":"TUE","Wednesday":"WED","Thursday":"THU","Friday":"FRI","Saturday":"SAT"}
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                c = [x.get_text(strip=True) for x in row.find_all("td")]
                if len(c) >= 4 and c[0] in dm:
                    tt[dm[c[0]]].append({"time":c[1],"course":c[2],"slot":c[3],
                        "venue":c[4] if len(c)>4 else "","faculty":c[5] if len(c)>5 else "",
                        "type":"LAB" if "LAB" in c[2].upper() else "TH"})
        return {"success": True, "timetable": tt}
    finally:
        await client.aclose()

@app.post("/marks")
async def marks(r: DataReq):
    if VTOP_LIB:
        try:
            async with VtopClient(r.registration_number, r.password) as c:
                return {"success": True, "marks": await c.get_marks(sem_sub_id=r.sem_sub_id)}
        except: pass
    client = await vtop_session(r.registration_number, r.password)
    try:
        def mapper(c):
            return {"course_code":c[1],"course_title":c[2],
                    "cat1_marks":c[3],"cat1_max":"50","cat2_marks":c[4],"cat2_max":"50",
                    "assignment_marks":c[5] if len(c)>5 else "0","assignment_max":"20",
                    "da_marks":c[6] if len(c)>6 else "0","da_max":"20",
                    "quiz_marks":c[7] if len(c)>7 else "0","quiz_max":"10"}
        data = await scrape_table(client, "/processViewStudentMarks", r.registration_number, r.sem_sub_id, mapper)
        return {"success": True, "marks": data}
    finally:
        await client.aclose()

@app.post("/exam_schedule")
async def exams(r: DataReq):
    if VTOP_LIB:
        try:
            async with VtopClient(r.registration_number, r.password) as c:
                return {"success": True, "exam_schedule": await c.get_exam_schedule(sem_sub_id=r.sem_sub_id)}
        except: pass
    client = await vtop_session(r.registration_number, r.password)
    try:
        def mapper(c):
            return {"course_code":c[1],"course_title":c[2],"exam_type":c[3],
                    "date":c[4] if len(c)>4 else "","time":c[5] if len(c)>5 else "",
                    "venue":c[6] if len(c)>6 else "","seat_number":c[7] if len(c)>7 else ""}
        data = await scrape_table(client, "/processViewExamSchedule", r.registration_number, r.sem_sub_id, mapper)
        return {"success": True, "exam_schedule": data}
    finally:
        await client.aclose()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
