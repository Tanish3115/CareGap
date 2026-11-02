# Free, disposable hosted demonstration

This image runs the existing Next.js UI, FastAPI API, OCR worker and file-cleanup worker in one container. It is a synthetic-only preview and provisions no paid database, disk, messaging or AI service. It does not replace the normal PostgreSQL Compose deployment or clinical/production review.

`render.yaml` selects Render's free web-service plan and disables automatic deploys. Render supplies the `onrender.com` address and HTTPS; a purchased domain is unnecessary. Current service creation still requires a Render account/connection and access to the reviewed source or image. The instruction not to push to GitHub remains in force.

Render's free filesystem is ephemeral and free web services spin down after inactivity. This demo intentionally creates a new temporary SQLite database, private file directory and random session secret on every process start. All demo users/files/sessions reset after a restart. Existing database URLs, storage paths and external processing credentials are overridden by the launcher. No existing CareGap database or vault is mounted or uploaded. The translated banner makes these limits visible. See [Render's free-service limits](https://render.com/docs/free) and [generated service addresses](https://render.com/docs/environment-variables).

## Run the exact deployment image locally

```powershell
docker build -f infra/free-demo/Dockerfile -t caregap-free-demo:local .
docker run -d --name caregap-free-demo --memory=512m --cpus=1 -p 127.0.0.1:3600:10000 -e CAREGAP_DEMO_ORIGIN=http://127.0.0.1:3600 caregap-free-demo:local
```

Open http://127.0.0.1:3600 and register a synthetic patient. There are no default administrator credentials. This container has no host volume mounts. Stop it when finished. The normal application remains at http://localhost:3300.

The hosted launcher reads `RENDER_EXTERNAL_URL`; local testing requires the explicit loopback origin above. Arbitrary HTTP origins, URL credentials, path/query/fragment origins and privileged ports are rejected. Public HTTPS uses Secure/HttpOnly application sessions. Child processes are supervised; failure stops the container, and shutdown terminates them before removing temporary data. Uvicorn listens only on container loopback; Next exposes the platform's `PORT` and forwards the API on the same origin.

## Deploy after account access and source publication are authorized

1. Connect/sign in to Render. Select a free web service or the root `render.yaml` Blueprint.
2. Use the reviewed current source or a reviewed image, not an outdated GitHub revision. No source has been pushed by the assistant. Publishing a new GitHub deployment branch requires the user's explicit permission under the existing no-push instruction.
3. Select Docker, root build context `.`, Dockerfile `infra/free-demo/Dockerfile`, **Free**, port `10000` and health path `/api/v1/health`. Keep automatic deploys off. Do not add a paid disk/database or real provider credentials to this disposable demo.
4. Verify the returned HTTPS URL, demo banner, registration/session behavior, upload/processing, scoped access, deletion/cleanup and restart reset. Do not infer publication from a successful local build.

The source build uses the root `.dockerignore` plus explicit runtime copies. Private environment files, databases, vaults, dependency/build directories, test results, Git history and unreviewed application data artifacts are excluded. Only the three named synthetic research artifacts are included.

A 512 MB local smoke covers startup, registration/login, upload/download, denied anonymous access, OCR processing and durable file cleanup. That bounded result does not promise capacity for every large scan or concurrent workload. Retaining real records requires independently reviewed persistent hosting, database/object storage, keys, backups, retention, incident response and clinical/privacy/security assurance. Free-demo reset behavior is not an approved erasure or retention procedure for real patients.
