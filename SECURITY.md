# Security and production configuration

This document maps the Django security controls to the credentials and
infrastructure needed when publishing the app. It is not a security certification.

## Files to keep in GitHub

| File | Purpose |
| --- | --- |
| `.env.example` | Placeholder production variables. No working credentials; not loaded automatically. |
| `maritime/settings.py` | Environment secrets, allowed hosts, CSRF origins, secure cookies, HTTPS/HSTS, password validation and PostgreSQL. |
| `portal/middleware.py` | Login throttling, private-response caching controls, content security policy and browser permission restrictions. |
| `portal/views.py`, `portal/models.py`, `portal/admin.py` | Company isolation, roles, subscription access, revision checks, immutable snapshots and operator permissions. |
| `.gitignore`, `.dockerignore` | Exclude secrets, databases, logs, notes, keys and generated artifacts from source and build context. Do not remove previous commits from history. |
| `Dockerfile`, `maritime/serve.py`, `requirements-web.txt` | Non-root image, explicit Waitress proxy trust and pinned runtime dependencies. |
| `render.yaml`, `maritime/render.py` | Free Render service, exact host/origin, generated secret, HTTPS scheme and serialized PostgreSQL initialization. |
| `portal/trials.py`, `portal/models.py` | Single-use operator invitations, expiry/revocation, private trial workspaces and non-staff customer accounts. |
| `.github/workflows/verify.yml` | Tests, dependency audit, production settings check and container build; read-only repository permissions, no production secrets. |
| `.github/dependabot.yml` | Weekly dependency, Actions and container-base update proposals. Review and test updates. |
| `portal/tests/` | Tenant isolation, roles, CSRF, login throttling, exports, provisioning and calculation regressions. |
| `docs/DEPLOYMENT.md` | Release, proxy/HTTPS, provisioning, backup, maintenance and launch instructions. |

## Credentials and data to keep outside GitHub

Store actual values in the hosting provider's secret manager and inject them as
environment variables. The app does not automatically read `.env` files.

- `DJANGO_SECRET_KEY`: a unique, cryptographically random production secret of at
  least 50 characters. Never use the development fallback or an example value.
- `DATABASE_URL`: database username, password and connection details. Use a
  restricted runtime account and the provider's verified TLS setup.
- `RENDER_SECRET_KEY`: Render's generated 256-bit secret; the Render entry point
  derives the Django key from it. Keep it stable across deploys.
- `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL` and
  `BOOTSTRAP_ADMIN_PASSWORD`: temporary Render secrets for the first operator.
  Remove all three after the first successful sign-in. Startup never changes
  an existing operator's password or promotes an existing customer account.
- `EMAIL_HOST_PASSWORD` and SMTP credentials if outgoing email is added.
  Self-service email password reset is not implemented yet.
- Customer/operator passwords, database backups, private keys and certificates.
- `workspace.sqlite3`: local account and scenario data. Keep private backups;
  this is neither source code nor a production deployment asset.

`DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` are configuration rather
than secrets; set them to the actual production host and HTTPS origins.
Set `DJANGO_DEBUG=0`. With the supplied `python -m maritime.serve` entrypoint,
set `TRUST_PROXY_HTTPS=1` and `WAITRESS_TRUSTED_PROXY` to the immediate proxy's
IP address only when that proxy strips client-supplied forwarding headers and
sets its own HTTPS scheme. Wildcard trust is rejected. Only the scheme is trusted;
the direct peer IP remains the source for application login throttling.

Never paste credentials into issues, commits, screenshots or build logs. Revoke
and rotate exposed credentials; deleting a file alone is not sufficient.

## Before publishing

1. Configure HTTPS and managed PostgreSQL. Restrict the database and application
   port to intended services. Configure verified database TLS, encrypted backups
   and a tested restore procedure.
2. Inject production variables and run `python manage.py check --deploy --fail-level WARNING`
   in the release environment. Apply migrations once per release, then use the
   supplied Waitress/container entry point.
3. Restrict `/admin/` with a VPN or identity-aware proxy with MFA. The app itself
   does not implement MFA/SSO. Apply edge rate limits as well as app throttling.
4. Enable GitHub secret scanning/push protection and dependency alerts where
   available. Require passing checks and reviewed changes on the default branch.
   These settings are not activated simply by committing this file.
5. Confirm live host/CSRF/proxy behavior, tenant isolation, PostgreSQL restore,
   monitoring, retention and independent security review before external use.

Keep production secrets out of pull-request CI. A future deployment workflow
should use a protected environment and narrowly scoped deployment credentials.

## Reporting a vulnerability

Use the repository's private vulnerability reporting feature if enabled, or an
established private contact with the repository owner. Do not publish exploit
details or customer data in an issue. Private reporting and response commitments
must be configured by the owner before launch.

## References

- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use)
