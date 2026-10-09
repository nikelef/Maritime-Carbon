# Free Render beta

The repository includes `render.yaml` for one **Free** Python web service in
Frankfurt. Use the `main` branch of `nikelef/Maritime-Carbon`. The blueprint does
not create a paid service or a Render database.

Accounts and saved calculations live in an external PostgreSQL database. Use a
free Neon project for a continuing beta: Render's own free PostgreSQL databases
expire after 30 days. Free hosting has usage limits and is intended for a small
test group. Render sleeps after 15 minutes without incoming traffic; opening
the app after that can take about a minute. Test realistic calculations before
inviting a larger group.

## Create the free service

1. Create a **Free** project at [Neon](https://console.neon.tech/), choosing a
   Frankfurt region if offered. In **Connect**, turn **Connection pooling off**
   and copy the direct PostgreSQL connection string. Startup migrations use a
   session lock, so this setup requires a direct connection. Keep the SSL
   parameters, and keep this secret out of GitHub.
2. Open [Render Blueprints](https://dashboard.render.com/blueprints) in your
   existing workspace. Choose **New Blueprint Instance**, select the connected
   `nikelef/Maritime-Carbon` GitHub repository, and use `main` and `render.yaml`.
3. Confirm that the proposed web service says **Free**, then enter these secrets
   when Render prompts:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | The free Neon **direct** PostgreSQL connection string. |
   | `BOOTSTRAP_ADMIN_USERNAME` | A new username for your operator account. |
   | `BOOTSTRAP_ADMIN_EMAIL` | Your email address. |
   | `BOOTSTRAP_ADMIN_PASSWORD` | A unique password of at least 12 characters. |

   The blueprint generates `RENDER_SECRET_KEY`. Do not replace it with a
   placeholder. The service derives a stable 64-character Django key from its
   generated 256-bit value. Its exact Render hostname and HTTPS CSRF origin are
   configured automatically; a custom domain is optional.
4. Apply the blueprint and wait for the initial deployment. The build collects
   static files and checks production settings. Startup applies migrations under
   a PostgreSQL advisory lock and creates the initial operator. Overlapping
   releases cannot migrate or provision simultaneously. Subsequent deploys do
   not reset an existing operator's password or promote a customer account.
5. Open the service's assigned `https://...onrender.com` address. Check
   `/health/`, `/accounts/login/` and `/admin/`. Sign in to `/admin/` with the
   operator account you selected. This privileged account manages trials; each
   invited customer gets a separate, non-staff account.
6. Remove **all three** `BOOTSTRAP_ADMIN_*` variables from the web service's
   Environment page after confirming the first sign-in. Keep `DATABASE_URL` and
   `RENDER_SECRET_KEY`. Removing the bootstrap variables does not remove the
   administrator. You can change its password through the operator console.

Choose only Free plans. Render documents that services without a payment method
are suspended rather than billed when applicable free usage allowances are
exceeded. Do not upgrade a plan or add paid resources to keep a demo running.

## If the service was created with Docker

An existing **Free Docker** service can use the same setup without creating a
second service. The Docker launcher detects Render and runs `maritime.render`
before loading Django. Keep the Docker Command empty to use the Dockerfile's
default, or set it explicitly to `python -m maritime.render`.

The blueprint's environment variables are only applied when using a Blueprint.
For a manually created service, open its **Environment** page and add
`DJANGO_DEBUG=0`, the direct Neon `DATABASE_URL`, the three `BOOTSTRAP_ADMIN_*`
variables above, and a persistent secret. Set `DJANGO_SECRET_KEY` to a
cryptographically random value of at least 50 characters, using a password
manager's generator or Python's `secrets.token_urlsafe(64)`. Alternatively, use
`RENDER_SECRET_KEY` with the blueprint's generated 256-bit value. Keep secrets out of GitHub and
redeploy after saving the environment. Do not enable debug mode to bypass a
missing key. After the first sign-in, remove the bootstrap variables as above.

If startup reports `Set DJANGO_SECRET_KEY` from `maritime.serve`, deploy the
latest `main` commit or set the Docker Command to `python -m maritime.render`.
If it reports a missing `RENDER_SECRET_KEY`, add the persistent secret described
above. A successful Docker image build does not configure these runtime values.

## Invite someone to register

1. In `/admin/`, open **Trial invitations** and choose **Add**.
2. Enter the person's email and company name. Defaults are a 30-day free trial,
   one account, three vessels per case, and seven days to use the invitation.
   You can adjust these values before sending the invitation.
3. Save, then right-click **Copy this invitation link address to send to the
   recipient** and copy the link address. Send it yourself by email or message.
4. The person opens the link and selects their name, username and password.
   Registration creates their private company workspace and an editable case
   containing one fictional example vessel. No payment information is requested,
   and no automatic email service is needed.

The invitation is a private bearer link: share it only with its intended
recipient. It can be used once and cannot be redeemed after its expiry or
revocation. Registered trial users are company administrators, with the chosen
seat and vessel limits; they are never platform staff. Trial access lasts the
configured number of calendar days, including the registration day. The
operator can renew access using **Companies** in `/admin/`.

The public `/demo/` remains available without registration. Customer inputs,
passwords, databases and invitation links are not committed to GitHub. Password
recovery is still handled by the operator; self-service email reset is not
connected.

## HTTPS and database operation

The Render entry point is `python -m maritime.render`; the default Docker/Waitress
launcher also selects it automatically on Render. It runs only when Render's
platform flag and a valid `onrender.com` hostname are present, rejects debug mode
and requires PostgreSQL.
It binds to Render's `PORT`. Render's public load balancer redirects HTTP to
HTTPS; the app sets its WSGI scheme to HTTPS and drops forwarded headers rather
than accepting arbitrary proxy addresses. Login throttling retains the direct
peer IP, and individual username limits still apply behind the shared proxy.

Back up the external database separately before relying on saved work. Free
plans are not an availability or backup guarantee. Customer reports remain
attached to their original calculation inputs and engine version.

References: [Render Free](https://render.com/docs/free),
[Render Django deployment](https://render.com/docs/deploy-django),
[Render environment variables](https://render.com/docs/environment-variables),
[Render blueprint specification](https://render.com/docs/blueprint-spec),
[Render billing FAQ](https://render.com/docs/faq),
[Neon Free plan](https://neon.com/blog/neon-free-plan-1-gb-per-project).
