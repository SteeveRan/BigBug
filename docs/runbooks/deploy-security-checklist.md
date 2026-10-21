# Runbook: Deploy Security Checklist

Checklist for deploying BigBug to a production-like environment. Architecture decisions live in the [ADR registry](../adr/README.md) (auth: ADR-0003, RBAC: ADR-0004, secrets encryption: ADR-0010).

## Pre-deploy

- [ ] **Unique `SECRET_KEY` and `ENCRYPTION_KEY` generated per environment** — never reused across environments, never committed:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"                                  # SECRET_KEY
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" # ENCRYPTION_KEY
  ```
- [ ] `.env` is NOT in git (check `.gitignore` covers it; `.env.example` is the only committed env file).
- [ ] PostgreSQL reachable only from the Docker/cluster network — no public port.
- [ ] Redis reachable only from the Docker/cluster network — no public port.
- [ ] HTTPS terminated at the reverse proxy (nginx/traefik); plain HTTP not exposed except loopback.
- [ ] Firewall allows only 80/443 inbound.

## Notes

- `ENCRYPTION_KEY` rotation invalidates all stored provider credentials (Fernet) — re-enter secrets after rotating.
- SSL verification of external integrations is per-provider (`verify_ssl`); disable only for self-signed dev stands.
