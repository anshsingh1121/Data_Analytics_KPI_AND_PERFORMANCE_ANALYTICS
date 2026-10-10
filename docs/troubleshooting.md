# Troubleshooting & Diagnostics Guide

This guide covers common issues, root causes, and resolutions when operating the Data Certification KPI System.

---

## 1. API Connectivity & Authentication Issues

### Problem: HTTP 401 Unauthorized
- **Cause**: Invalid username or password in `.env`, or service account password expired.
- **Resolution**:
  1. Check `.env` settings: `API_USERNAME` and `API_PASSWORD`.
  2. Verify credentials in a standard browser or API client (e.g. Postman).
  3. Ensure account is not locked out in ServiceNow.

### Problem: HTTP 403 Forbidden
- **Cause**: Service account lacks read ACL on `cert_task` or `u_failed_data_certifications`.
- **Resolution**:
  1. Contact your ServiceNow administrator.
  2. Grant the account read permission on `cert_task` and the custom table `u_failed_data_certifications`.
  3. Verify access by running `python main.py test-connection`.

### Problem: SSL / TLS Certificate Validation Error
- **Cause**: Corporate SSL interception proxy (Zscaler, BlueCoat, etc.) replacing CA certificates.
- **Resolution**:
  1. Export corporate root CA certificate to `.pem`.
  2. Set environment variable `REQUESTS_CA_BUNDLE=C:\path\to\corporate_cert.pem`.
  3. Avoid setting `API_VERIFY_TLS=false` in production.

---

## 2. Field Mapping & Schema Mismatches

### Problem: `KeyError: 'due_date'` or Missing Field Warnings
- **Cause**: The ServiceNow instance uses custom column prefixes (e.g. `u_due_date` instead of `due_date`).
- **Resolution**:
  1. Run `python main.py discover-schema` to list remote fields.
  2. Open `config/field_mapping.yaml` and update the mapping:
     ```yaml
     cert_task:
       mappings:
         due_date: u_custom_due_date
     ```
  3. Re-run `python main.py pipeline`.

---

## 3. Data Processing & Timezones

### Problem: `Cannot subtract tz-naive and tz-aware datetime-like objects`
- **Cause**: Timestamp series parsed with timezone information subtracted from naive datetime.
- **Resolution**:
  1. The normalizer standardizes timestamps to timezone-naive datetimes in the configured timezone (`UTC` by default in `settings.yaml`).
  2. Ensure `normalizer.py` and `kpi_engine.py` use the internal `_to_dt()` helper.

---

## 4. Dashboard Startup Issues

### Problem: Streamlit Not Found or Command Error
- **Resolution**:
  Ensure the virtual environment is activated:
  ```bat
  .venv\Scripts\activate.bat
  streamlit run src/dashboard/app.py
  ```
  Or run via python module:
  ```bat
  .venv\Scripts\python -m streamlit run src/dashboard/app.py
  ```
