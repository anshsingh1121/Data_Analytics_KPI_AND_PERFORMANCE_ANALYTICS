# ServiceNow API Integration & Setup Guide

This guide describes how to configure an authorized integration with ServiceNow using the Table API.

---

## 1. Required ServiceNow Permissions

The service account used by this application must have read-only access to two tables and the data dictionary:

| Table | Required Role / ACL | Purpose |
|---|---|---|
| `cert_task` | `sn_audit_cert.certifier` or `itil` + read ACL | Extract certification tasks, state, due date, certifier |
| `u_failed_data_certifications` | Read ACL on custom table | Extract validation issues, failed attributes, resolution times |
| `sys_dictionary` | Read ACL on dictionary table | Schema discovery, field types, and labels |

> **Security Rule**: The service account must have **read-only** rights. The application never issues POST, PUT, PATCH, or DELETE calls against source records.

---

## 2. Setting Up Credentials in `.env`

1. Create your local `.env` file from `.env.example`:
   ```bat
   copy .env.example .env
   ```

2. Configure Basic Authentication (or OAuth):
   ```dotenv
   # API Connection
   API_BASE_URL=https://your-instance.service-now.com
   API_PROVIDER=servicenow
   API_AUTH_METHOD=basic

   # Basic Authentication
   API_USERNAME=svc_datacert_reader
   API_PASSWORD=YourSecurePasswordHere

   # Connection Parameters
   API_TIMEOUT_SECONDS=30
   API_PAGE_SIZE=500
   API_MAX_RETRIES=3
   API_VERIFY_TLS=true

   # Application Mode
   APP_MODE=live
   ```

---

## 3. Verifying the Connection

Run the diagnostic command:
```bat
python main.py test-connection
```

The tool will test:
1. TCP connectivity and TLS handshake.
2. HTTP status code for authentication (validating 401/403).
3. Access to `cert_task`.
4. Access to `u_failed_data_certifications`.

---

## 4. Discovering Schemas

Run the discovery tool:
```bat
python main.py discover-schema
```

This will inspect fields, detect custom prefixes (`u_`), and compare with `config/field_mapping.yaml`. If your instance uses different column names (e.g. `assigned_to` vs `certifier`), edit `config/field_mapping.yaml` accordingly.

---

## 5. Security Best Practices

- Never commit `.env` into version control (`.gitignore` excludes it).
- Maintain TLS verification enabled (`API_VERIFY_TLS=true`).
- Keep request batch sizes constrained via `API_PAGE_SIZE=500` to prevent memory spikes and rate-limiting.
