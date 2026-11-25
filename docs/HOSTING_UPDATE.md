# Update the existing hosted application

The target is the existing app at https://caregap360.vercel.app, using the persistent Render backend, Supabase database/private storage and Redis. Use the existing projects and credentials. The root `render.yaml` and `deploy/free-demo` branch describe a separate disposable demo; the persistent backend configuration is `infra/hosting/render.yaml`.

## Release changes

- Patient and doctor digital cards appear at the top right after login. Cards download as 1050 × 600 PNGs with 300 DPI metadata, equivalent to a 3.5 × 2 inch visiting card. Doctors can view a patient's identity card while authorized patient consent is active; download rechecks access.
- Login now links to `/forgot-password`. `/reset-password` accepts an expiring, single-use email link. Completing a reset revokes existing sessions and pending links. All three account roles use the same recovery flow.
- Migration `0020` adds reset-token storage without replacing accounts, password hashes, sessions or documents. PostgreSQL migration also enables row-level security and removes public/Data API role privileges from this table. The backend uses its existing table-owner connection.

## Configure mail in Render

CareGap sends customer email from `admin.caregap@gmail.com`. Authorize this mailbox with the Gmail setup command and import its six settings into the existing persistent Render backend. Keep the Google credentials in that backend's environment. The Blueprint specifies the sending address and leaves the delivery mode under operator control. Once the sender grant is ready, deploy the latest `main` commit and request a fresh link for a registered test account. [Gmail setup and delivery verification](PASSWORD_RECOVERY.md#send-reset-links-with-gmail-on-render)

## Deploy the release

1. Publish the reviewed source to the repository's `main` branch. Keep `.env`, `.tools`, databases, files and mail outboxes excluded. Wait for the application checks for that commit.
2. In the existing Render persistent service, deploy that exact commit from `main`. Its start command remains `python -m app.hosted`; startup applies migration `0020` before launching the API and workers. Automatic deployment is disabled in the supplied Blueprint, so a GitHub push alone does not update this backend.
3. Confirm the Render deployment is live and `/ready` returns 200. Do not start the disposable demo or create another database to perform an update.
4. Redeploy the same commit in the existing Vercel project. Root directory remains `frontend`; preserve its current `API_PROXY_TARGET` pointing at the persistent Render backend. The proxy target is used during the Next.js build. Vercel Git integration may already have built the new commit; confirm its production deployment matches the release.
5. Open https://caregap360.vercel.app/login and verify the forgot-password link. Use an existing registered test account to request a **new** reset email, inspect the provider's delivery status and confirm arrival in the intended mailbox. An HTTP 202 response hides account existence and is not proof that mail was delivered.
6. Confirm the emailed link opens `https://caregap360.vercel.app/reset-password`, completes a reset once and signs out previous sessions. Confirm the account's digital card appears after sign-in and downloads at the expected dimensions. Verify consent expiry/revocation denies a doctor's subsequent patient-card download.

Recovery is disabled on production until configured. No provider can guarantee inbox placement; sender authentication and mailbox filtering still apply. Existing local file-outbox messages are not sent retroactively. Additional setup and failure behavior are in [PASSWORD_RECOVERY.md](PASSWORD_RECOVERY.md).

## Rollback

Retain the prior Render and Vercel deployment identifiers. Migration `0020` is additive, so an application rollback can leave the new table in place; it does not require deleting any account or document. A previous backend reporting a required schema revision of `0019` may fail readiness after migration, so use a compatibility rollback build that accepts `0020`. Do not run a database downgrade as an automatic rollback: it removes pending reset links. If a database downgrade is deliberately chosen during maintenance, stop the updated API and workers first and preserve the existing database backup procedure.
