# Deployment and commercial operation

The repository supplies the customer application, database migrations, tests and
container definition. No production account, public domain or payment provider
has been connected. The initial commercial workflow is manually invoiced company
subscriptions with operator-controlled entitlements.

## Local preview

Run `./run-local.ps1 -Install` on Windows. It uses a project virtual environment,
migrates the local SQLite database and serves loopback only. `/demo/` is a public
read-only example built from fictional inputs; it does not access customer cases.
The local database is ignored by Git and is not a production backup.

## Production architecture

Use a managed PostgreSQL service and a Python/container host behind a trusted
HTTPS reverse proxy. Select a hosting region and contractual data-processing
terms appropriate for your customers. Django/Waitress serves the application;
WhiteNoise serves versioned static files. This Python/database application is not
a static-site deployment. See [SECURITY.md](../SECURITY.md) for the security-file map.

Set variables described in `.env.example` through the host's secret manager:

- `DJANGO_DEBUG=0`;
- a random `DJANGO_SECRET_KEY` of at least 50 characters;
- exact `DJANGO_ALLOWED_HOSTS` and HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`;
- a PostgreSQL `DATABASE_URL`, normally with certificate-verified TLS configured
  to the database provider's requirements;
- `TRUST_PROXY_HTTPS=1` and `WAITRESS_TRUSTED_PROXY` set to the immediate reverse
  proxy's actual IPv4 or IPv6 peer address, only if that proxy strips incoming
  forwarded headers and sets `X-Forwarded-Proto` itself. Pass the original public
  `Host` header and restrict direct application-port access to that proxy.

Do not copy the example placeholder secret. Startup rejects absent/obvious
placeholder secrets, missing explicit hosts and SQLite in production. `.env`
files are not automatically loaded by Python; the host must inject variables.

Build with `docker build -t maritime-carbon .`. The image runs as a non-root
user and excludes customer databases and secrets.
Its entrypoint is `python -m maritime.serve`, listening on port 8000 with four
Waitress threads. This bootstrap validates proxy configuration and explicitly
trusts only `X-Forwarded-Proto` from the configured peer; other forwarded headers
are removed. Waitress sets the validated WSGI scheme for Django, avoiding an HTTPS
redirect loop. The application retains the direct peer IP for login throttling.
When HTTPS proxy trust is enabled, a missing/invalid proxy address, hostname,
network range or wildcard causes startup to fail. For direct local HTTP, use
`DJANGO_DEBUG=1`, `TRUST_PROXY_HTTPS=0` and leave `WAITRESS_TRUSTED_PROXY` unset.
If using another WSGI entrypoint, configure equivalent peer validation and scheme
translation there; Django deliberately does not trust raw forwarded headers.
Before opening traffic, run the following once as a release job with production
environment variables, using the same release image:

```text
python manage.py migrate --noinput
python manage.py check --deploy --fail-level WARNING
python manage.py createsuperuser
```

Static collection is already part of the image build. Keep schema migrations
out of individual worker startup to prevent concurrent migration races.
Point the host's health check at `/health/` using the configured trusted scheme
and host. It checks database connectivity and returns no customer information.
The Docker build and an actual PostgreSQL deployment still require validation in
the chosen hosting environment; local acceptance tests use SQLite.

## Sell and provision access

After agreeing the customer's subscription/trial and payment arrangements:

```text
python manage.py provision_company --company "Customer Ship Management" --username "customer.admin" --email "admin@customer.example" --status active --days 365 --seats 5 --vessels 20
```

The password is entered through a secure terminal prompt, checked with Django's
password validators and stored as a hash. Do not put it in command arguments,
source control or logs. For controlled automation, `--password-env VARIABLE_NAME`
reads a secret supplied by your provisioning system. No email is sent by the app.

The initial user is a company administrator, not a platform administrator. The
customer administrator can create analysts/viewers/administrators, deactivate
colleagues, and see recent company activity. One user account belongs to one
company. Customer URLs enforce company membership independently of UUID secrecy.

Use the operator console at `/admin/` to renew `access_until`, set active/trial/
suspended status, or change seat/vessel entitlements. Expiry is inclusive in UTC.
There is no grace period, checkout, automated invoice collection or billing webhook.
Do not describe the product as integrated with Stripe/Paddle or another provider.

For password recovery, verify the person's identity through the agreed customer
support process, then use Django's operator password-change controls or
`python manage.py changepassword USERNAME`. Require the customer to select a new
unique password. Self-service email reset and MFA/SSO are not currently implemented.

## Security and maintenance

The application includes Django password hashing, CSRF protection, secure
production cookies, HTTPS/HSTS, a same-origin content policy, role enforcement,
database-backed login throttles, revision checks and tenant-filtered exports.
Anonymous and authenticated login failures are generic. Both operator and customer
sign-in are throttled; add edge rate limits before exposing the service publicly.
The application uses the direct peer IP, never an untrusted forwarded address;
behind a shared proxy, configure appropriate edge limits to avoid a shared-IP
bucket denying legitimate users after repeated failures.

Protect the operator console with a VPN, an identity-aware proxy with MFA, or
equivalent privileged-access controls. The application itself does not add MFA.
Treat platform staff as trusted across all customer companies. Use a separate
database owner for migrations and least-privilege runtime credentials where practical.

Each calculation stores its source inputs, results, rule/source version, author,
timestamp and SHA-256 input fingerprint. Application routes and the admin console
do not permit editing calculation snapshots. This is not cryptographic tamper-
proof storage against a database administrator. For a stronger retention contract,
export records to immutable storage and govern database/operator access.

Configure encrypted automated PostgreSQL backups, retention and tested restores.
Keep secrets separate from database backups, monitor errors/availability, and
avoid logging request bodies, passwords or exported customer inputs. Run:

```text
python manage.py clearsessions
python manage.py purge_login_buckets
```

as periodic maintenance. Expired throttle buckets are removed after one day;
define a separate customer-data retention/deletion procedure under your contract.
Business records are protected against casual deletion; do not improvise cascading
production deletes. Export and test a targeted retention migration when required.

Review dependency advisories and regulatory sources regularly. Upgrade through
the test suite and a staged deployment. Keep engine/ruleset versions attached to
each changed calculation contract. Results do not silently adopt later rules.

The optimizer is synchronous and limited to 20 ships/case. Benchmark realistic
customer horizons on the chosen host. Larger fleets, many simultaneous calculations,
or interactive procurement optimization warrant a job queue and revised capacity
planning; do not remove the limits without measuring.

## Before the first paid external customer

Complete a production PostgreSQL migration/restore drill, HTTPS and access tests,
and a scoped security review. Independently reconcile representative customer
calculations with their monitoring plan and a maritime regulatory specialist.
Agree the permitted product scope, contract/liability terms, privacy notice,
data-processing agreement, retention policy, support and incident process. These
documents are business/legal decisions, not generated certifications.

The implemented invoicing-based account model can support a controlled pilot.
Broad sales as a universal or verifier-approved compliance optimizer would exceed
the implemented and verified scope. See `REGULATORY_BASIS.md` for the exact limits.
