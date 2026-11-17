from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3
import json
import uuid
import os
import re
from pathlib import Path

app = FastAPI(title="SQL Server to PostgreSQL Migration Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = str(Path(__file__).parent.parent / "migration.db")
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'created',
            risk_score INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS databases (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT,
            object_count INTEGER DEFAULT 0,
            risk_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS objects (
            id TEXT PRIMARY KEY,
            database_id TEXT,
            name TEXT,
            object_type TEXT,
            definition TEXT,
            complexity_score INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'low',
            flags TEXT,
            dependencies TEXT,
            linked_servers TEXT,
            FOREIGN KEY(database_id) REFERENCES databases(id)
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            decision TEXT,
            comment TEXT,
            created_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS linked_servers (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT,
            usage_count INTEGER DEFAULT 0,
            risk TEXT DEFAULT 'medium',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- Models ----------
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class CheckpointDecision(BaseModel):
    decision: str
    comment: Optional[str] = ""

# ---------- Helpers ----------
def analyze_sql(content: str, db_name: str) -> List[Dict]:
    """Deep analysis of SQL Server DDL / T-SQL"""
    objects = []
    # Simple but effective pattern matching for demo / production starter
    proc_pattern = re.compile(r'CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+\[?(\w+)\]?\.\[?(\w+)\]?', re.IGNORECASE)
    table_pattern = re.compile(r'CREATE\s+TABLE\s+\[?(\w+)\]?\.\[?(\w+)\]?', re.IGNORECASE)
    func_pattern = re.compile(r'CREATE\s+(?:OR\s+ALTER\s+)?FUNCTION\s+\[?(\w+)\]?\.\[?(\w+)\]?', re.IGNORECASE)

    # Linked server detection
    linked_pattern = re.compile(r'\[?(\w+)\]?\.\[?(\w+)\]?\.\[?(\w+)\]?\.\[?(\w+)\]?', re.IGNORECASE)

    for match in proc_pattern.finditer(content):
        schema, name = match.groups()
        full_name = f"{schema}.{name}"
        start = match.start()
        # Extract rough body
        body = content[start:start+2000]
        flags = []
        linked = []
        if re.search(r'\bMERGE\b', body, re.I): flags.append("MERGE")
        if re.search(r'\bPIVOT\b', body, re.I): flags.append("PIVOT")
        if re.search(r'OPENQUERY|OPENROWSET', body, re.I): flags.append("OPENQUERY")
        if re.search(r'xp_cmdshell|sp_OACreate', body, re.I): flags.append("EXTENDED_PROC")
        for lm in linked_pattern.finditer(body):
            parts = lm.groups()
            if parts[0] and parts[0].lower() not in ('dbo', 'sys', 'master'):
                linked.append(parts[0])

        complexity = len(body.splitlines()) // 10 + len(flags) * 15
        risk = "high" if complexity > 40 or "MERGE" in flags or linked else "medium" if complexity > 20 else "low"

        objects.append({
            "name": full_name,
            "object_type": "stored_procedure",
            "definition": body[:1500],
            "complexity_score": min(complexity, 100),
            "risk_level": risk,
            "flags": flags,
            "linked_servers": list(set(linked))
        })

    for match in table_pattern.finditer(content):
        schema, name = match.groups()
        objects.append({
            "name": f"{schema}.{name}",
            "object_type": "table",
            "definition": "",
            "complexity_score": 10,
            "risk_level": "low",
            "flags": [],
            "linked_servers": []
        })

    for match in func_pattern.finditer(content):
        schema, name = match.groups()
        objects.append({
            "name": f"{schema}.{name}",
            "object_type": "function",
            "definition": "",
            "complexity_score": 25,
            "risk_level": "medium",
            "flags": [],
            "linked_servers": []
        })

    return objects

def calculate_project_risk(project_id: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT risk_level, complexity_score FROM objects o JOIN databases d ON o.database_id = d.id WHERE d.project_id = ?", (project_id,))
    rows = c.fetchall()
    if not rows:
        return 0
    high = sum(1 for r in rows if r["risk_level"] == "high")
    medium = sum(1 for r in rows if r["risk_level"] == "medium")
    total = len(rows)
    score = min(100, int((high * 40 + medium * 15) / max(total, 1) * 2 + 20))
    c.execute("UPDATE projects SET risk_score = ?, updated_at = ? WHERE id = ?", (score, datetime.utcnow().isoformat(), project_id))
    conn.commit()
    conn.close()
    return score

# ---------- Endpoints ----------
@app.post("/api/projects")
def create_project(proj: ProjectCreate):
    pid = str(uuid.uuid4())
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (pid, proj.name, proj.description, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return {"id": pid, "name": proj.name}

@app.get("/api/projects")
def list_projects():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    proj = dict(c.fetchone() or {})
    c.execute("SELECT * FROM databases WHERE project_id = ?", (project_id,))
    proj["databases"] = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM checkpoints WHERE project_id = ? ORDER BY created_at", (project_id,))
    proj["checkpoints"] = [dict(r) for r in c.fetchall()]
    conn.close()
    return proj

@app.post("/api/projects/{project_id}/upload")
async def upload_ddl(project_id: str, file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    content = (await file.read()).decode("utf-8", errors="ignore")
    path = UPLOAD_DIR / f"{project_id}_{file.filename}"
    path.write_text(content)

    # Extract database names (simple heuristic)
    db_names = set(re.findall(r'USE\s+\[?(\w+)\]?', content, re.I)) or {"DefaultDB"}

    conn = get_db()
    c = conn.cursor()
    for db_name in db_names:
        db_id = str(uuid.uuid4())
        c.execute(
            "INSERT INTO databases (id, project_id, name, status) VALUES (?, ?, ?, ?)",
            (db_id, project_id, db_name, "analyzing")
        )
        objs = analyze_sql(content, db_name)
        for obj in objs:
            oid = str(uuid.uuid4())
            c.execute("""
                INSERT INTO objects (id, database_id, name, object_type, definition, complexity_score, risk_level, flags, linked_servers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (oid, db_id, obj["name"], obj["object_type"], obj["definition"],
                  obj["complexity_score"], obj["risk_level"], json.dumps(obj["flags"]), json.dumps(obj["linked_servers"])))

            for ls in obj["linked_servers"]:
                c.execute("""
                    INSERT OR IGNORE INTO linked_servers (id, project_id, name) VALUES (?, ?, ?)
                """, (str(uuid.uuid4()), project_id, ls))
                c.execute("UPDATE linked_servers SET usage_count = usage_count + 1 WHERE project_id = ? AND name = ?", (project_id, ls))

        c.execute("UPDATE databases SET object_count = ?, status = 'analyzed' WHERE id = ?", (len(objs), db_id))

    # Auto-create checkpoints
    checkpoints = [
        ("Type Mapping Review", "Review and approve SQL Server to PostgreSQL type mappings (BIT, MONEY, DATETIME, etc.)"),
        ("Linked Server Strategy", "Decide how to handle linked servers found in stored procedures"),
        ("High Risk Procedures", "Review stored procedures flagged as high complexity or containing MERGE / OPENQUERY"),
        ("Wave Plan Approval", "Approve the recommended migration wave sequence for multiple databases"),
    ]
    for title, desc in checkpoints:
        c.execute(
            "INSERT INTO checkpoints (id, project_id, title, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), project_id, title, desc, datetime.utcnow().isoformat())
        )

    conn.commit()
    conn.close()
    calculate_project_risk(project_id)
    return {"status": "analyzed", "databases": list(db_names)}

@app.get("/api/projects/{project_id}/objects")
def get_objects(project_id: str, object_type: Optional[str] = None, risk: Optional[str] = None):
    conn = get_db()
    c = conn.cursor()
    query = """
        SELECT o.*, d.name as database_name
        FROM objects o
        JOIN databases d ON o.database_id = d.id
        WHERE d.project_id = ?
    """
    params = [project_id]
    if object_type:
        query += " AND o.object_type = ?"
        params.append(object_type)
    if risk:
        query += " AND o.risk_level = ?"
        params.append(risk)
    query += " ORDER BY o.risk_level DESC, o.complexity_score DESC"
    c.execute(query, params)
    rows = []
    for r in c.fetchall():
        d = dict(r)
        d["flags"] = json.loads(d["flags"] or "[]")
        d["linked_servers"] = json.loads(d["linked_servers"] or "[]")
        rows.append(d)
    conn.close()
    return rows

@app.get("/api/projects/{project_id}/linked-servers")
def get_linked_servers(project_id: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM linked_servers WHERE project_id = ?", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

@app.post("/api/checkpoints/{checkpoint_id}/decide")
def decide_checkpoint(checkpoint_id: str, body: CheckpointDecision):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE checkpoints SET status = ?, decision = ?, comment = ? WHERE id = ?",
        ("approved" if body.decision == "approve" else "rejected", body.decision, body.comment, checkpoint_id)
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.get("/api/projects/{project_id}/report")
def get_report(project_id: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    proj = dict(c.fetchone())
    c.execute("SELECT COUNT(*) as cnt, object_type FROM objects o JOIN databases d ON o.database_id = d.id WHERE d.project_id = ? GROUP BY object_type", (project_id,))
    counts = {r["object_type"]: r["cnt"] for r in c.fetchall()}
    c.execute("SELECT COUNT(*) as high FROM objects o JOIN databases d ON o.database_id = d.id WHERE d.project_id = ? AND risk_level = 'high'", (project_id,))
    high = c.fetchone()["high"]
    conn.close()

    return {
        "project": proj,
        "summary": {
            "total_objects": sum(counts.values()),
            "by_type": counts,
            "high_risk_objects": high,
            "risk_score": proj["risk_score"],
            "recommendation": "Proceed with AWS Transform after resolving high-risk checkpoints" if proj["risk_score"] < 70 else "Significant manual work expected. Review linked servers and complex procedures first."
        },
        "generated_at": datetime.utcnow().isoformat()
    }

# Serve frontend
@app.get("/")
def serve_frontend():
    return FileResponse(Path(__file__).parent.parent / "frontend" / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
