# AWS Transform Configuration Guide
## SQL Server → Aurora PostgreSQL Migration

This guide covers how to configure and use **AWS Transform for SQL Server modernization** end-to-end.

---

## Prerequisites

- AWS account with **IAM Identity Center** enabled (recommended)
- Permissions to create Amazon Aurora PostgreSQL clusters
- SQL Server 2008 R2 through 2022 (any edition)
- Supported regions: `us-east-1`, `eu-central-1`, `eu-west-2`, `ap-south-1`, `ap-northeast-2`, `ap-northeast-1`, `ap-southeast-2`, `ca-central-1`

---

## Method 1: Offline Source (Recommended)

No direct network connection to SQL Server is required. Ideal for assessment + schema + stored procedure conversion.

### Steps

1. Sign in to the **AWS Management Console**
2. Search for and open **AWS Transform**
3. Choose **Microsoft Modernization** → **Create modernization job**
4. Select **SQL Server modernization**
5. Enter job name, description, and target region → **Create job**
6. In the agent chat, choose **Upload DDL files** (Offline Source)
7. Download the provided extraction script (`ExtractDatabaseMetadata.ps1`)
8. Run the script on your SQL Server machine (requires PowerShell 7+ and `sqlcmd`):

```powershell
.\ExtractDatabaseMetadata.ps1 -ServerInstance "your-sql-server" -Username "user" -Password "pass"
```

9. Upload the generated `.zip` file in the Transform console
10. AWS Transform performs Discovery → Assessment → Transformation Plan
11. Review and customize the **Transformation Plan**
12. Approve the plan to start conversion and Aurora deployment

---

## Method 2: Online Workflow (Full Schema + Data)

Requires SQL Server running on **EC2 or RDS** in the same AWS region.

### Steps

1. Create the modernization job (same as above)
2. Choose **Connect to SQL Server database**
3. Create a new **Database Connector**:
   - Connector name
   - SQL Server endpoint (EC2/RDS)
   - Port, database, username, password
4. AWS Transform validates connectivity and permissions
5. It discovers all databases on the instance
6. Select which databases to modernize
7. It uses **AWS DMS** for schema conversion + data migration
8. (Optional) Connect GitHub/GitLab/Bitbucket for .NET application transformation

### Required SQL Server Permissions

```sql
GRANT VIEW DEFINITION TO [transform_user];
GRANT VIEW DATABASE STATE TO [transform_user];
GRANT VIEW SERVER STATE TO [transform_user];
GRANT VIEW ANY DEFINITION TO [transform_user];
-- db_datareader only needed if you also want data migration
```

---

## Customizing the Transformation Plan

Before conversion starts, AWS Transform shows a **Transformation Plan**. You can:

- Override type mappings (e.g., `BIT` → `BOOLEAN`, `MONEY` → `NUMERIC(19,4)`)
- Change schema name mappings (`dbo` → `public`)
- Choose identity column strategy (`GENERATED ALWAYS` vs `BY DEFAULT`)
- Skip optional phases (synthetic data, application code transformation)
- Describe changes in plain English in the chat

### Default Type Mappings

| SQL Server     | PostgreSQL          |
|----------------|---------------------|
| BIT            | NUMERIC(1,0)        |
| MONEY          | NUMERIC(19,4)       |
| DATETIME       | TIMESTAMP(3)        |
| NVARCHAR/VARCHAR | CITEXT            |
| UNIQUEIDENTIFIER | UUID              |
| IMAGE          | BYTEA               |

---

## Important Limitations

| Item                        | Status              | Recommendation                          |
|-----------------------------|---------------------|-----------------------------------------|
| Linked Servers              | Not auto-converted  | Manual reconfiguration or `postgres_fdw`|
| Cross-database queries      | Flagged             | Review and refactor or consolidate      |
| SSIS / Agent Jobs           | Not supported       | Migrate separately                      |
| On-premises (direct Online) | Not supported       | Use Offline workflow or clone to EC2    |
| .NET Framework 4.x          | Not supported       | Upgrade to .NET 6+ first                |

---

## Recommended Workflow with This Engine

1. Use this local engine to perform deep assessment (especially linked servers and multi-DB risk)
2. Download the assessment report
3. Run the AWS Transform extraction script on your SQL Server
4. Upload the DDL zip to AWS Transform
5. Review and approve the Transformation Plan
6. Let AWS Transform convert schema and stored procedures
7. Use AWS DMS separately if you need to migrate real data

---

## Useful Links

- [AWS Transform Documentation](https://docs.aws.amazon.com/transform/latest/userguide/sql-server-modernization.html)
- [Offline Source Workflow](https://docs.aws.amazon.com/transform/latest/userguide/sql-server-create-job.html)
- [Online Workflow](https://docs.aws.amazon.com/transform/latest/userguide/sql-server-online-transformation.html)
