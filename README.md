# SQL Server → PostgreSQL Migration Engine

Local production-ready assessment and orchestration engine for SQL Server to PostgreSQL migrations, designed to work with **AWS Transform for SQL Server modernization**.

## Features

- Multi-database discovery and analysis
- Linked server detection inside stored procedures
- Risk scoring (Low / Medium / High)
- Object-level analysis (tables, procedures, functions)
- Human-in-the-loop checkpoints
- Assessment reports (JSON download)
- Clean modern UI
- Ready for AWS Transform integration

## Run Locally

```bash
git clone https://github.com/prashantlink/sql-server-to-postgresql-migration-engine.git
cd sql-server-to-postgresql-migration-engine
chmod +x run.sh
./run.sh
```

Open http://localhost:8000

## Workflow

1. Create a project
2. Upload a SQL Server DDL file (or AWS Transform extraction script output)
3. Review assessment, objects, linked servers, and risk scores
4. Approve or reject human-in-the-loop checkpoints
5. Download the assessment report
6. Continue in AWS Transform for actual schema + stored procedure conversion

## AWS Transform Configuration Guide

See [GUIDE.md](./GUIDE.md) for the full step-by-step guide on configuring and using AWS Transform for SQL Server modernization (Offline and Online workflows).

## Project Structure

```
migration-engine/
├── backend/           # FastAPI assessment engine
├── frontend/          # Modern UI (Tailwind + Alpine.js)
├── run.sh
├── GUIDE.md           # Full AWS Transform setup guide
└── README.md
```
