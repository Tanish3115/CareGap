# Password recovery

The login screen links to **Forgot password?** (`/forgot-password`). A user supplies their account email, opens the emailed link and chooses a new password on `/reset-password`. Successful recovery ends existing sessions and sends the user back to sign in. Patients, doctors and administrators use the same process; profiles, roles and professional verification do not change.

Request responses do not reveal whether an account exists or is active. Account lookup and delivery run in a background task after the generic response. The response reports `delivery: "local"` or `delivery: "email"` identically for known and unknown accounts. Local mode explicitly says no inbox email is being sent, and the UI displays the corresponding local-development notice instead of “Check your email.” No reset link or token is returned by the API. Requests are limited to five per minute and twenty per hour per IP; repeated mail to an account has a one-minute cooldown. Existing links remain valid when another is requested, until one is used or expires.

## Send reset links with Gmail on Render

CareGap sends from one Gmail or Google Workspace mailbox authorized by the app operator. Patients, doctors and administrators request a link for the address already registered with CareGap. The backend uses Google's HTTPS Gmail API, which works on Render's free tier with its SMTP port restrictions. [Gmail sending guide](https://developers.google.com/workspace/gmail/api/guides/sending) · [Render free web services](https://render.com/docs/free#outbound-smtp-traffic)

1. In the CareGap Google Cloud project, enable the Gmail API. Under **Google Auth Platform**, configure the app's branding and audience and add the `https://www.googleapis.com/auth/gmail.send` scope under **Data Access**. If your app is in external Testing, add the sender mailbox as a test user. [Enable Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com) · [Google consent setup](https://developers.google.com/workspace/guides/configure-oauth-consent) · [Gmail scope permissions](https://developers.google.com/workspace/gmail/api/auth/scopes)
2. Under **Clients**, create a **Desktop app** OAuth client for the setup command. Download its JSON to a private location outside the repository. [Create a desktop client](https://developers.google.com/workspace/guides/create-credentials#desktop-app)
3. From the CareGap repository, run the command below with the downloaded file's path. Enter the sending address and approve sending in Google's browser window using that mailbox. The setup command uses Google's OAuth library with a loopback callback and PKCE. [Google desktop OAuth flow](https://developers.google.com/identity/protocols/oauth2/native-app)

   ```powershell
   uv run scripts/authorize_gmail.py "C:\path\to\your-google-client.json"
   ```

4. The command prints the path of a private temporary `.env` file. In the **existing Render backend → Environment**, import its six settings. Update the matching keys if they already exist. Choose **Save only**, then **Manual Deploy → Deploy latest commit** from `main`. If the Gmail release already runs on Render, **Save and deploy** applies the settings to it. Remove the temporary file after the import. [Render environment settings](https://render.com/docs/configure-environment-variables)
5. Request a fresh link using a registered test account. A successful Google submission records `PASSWORD_RESET_EMAIL_ACCEPTED` with provider `gmail` after Gmail returns a message ID. Confirm receipt in the mailbox, follow **Reset your CareGap 360 password**, and sign in with the new password. An expired or reused link prompts for a new request. [Open CareGap password recovery](https://caregap360.vercel.app/forgot-password)

The generated settings are `PASSWORD_RESET_DELIVERY=gmail`, `PASSWORD_RESET_BASE_URL=https://caregap360.vercel.app`, `PASSWORD_RESET_FROM_EMAIL` and the three backend credentials `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`. Pass `--origin https://your-frontend.example` to the setup command if you host the frontend elsewhere. Keep these settings on the backend. After permission revocation, repeat the grant and update Render. A Google external Testing grant with this scope normally expires after seven days. For ongoing service use the appropriate Google production or Workspace internal audience and obtain a fresh grant. [Google refresh-token lifetime](https://developers.google.com/identity/protocols/oauth2#expiration)

If a request produces no mail, check the backend logs. A 404 on `POST /api/v1/auth/forgot-password` means the running backend needs the reset release. A 503 means delivery is disabled. After a request for a registered account, `Gmail authorization returned HTTP …` points to the sender grant. `Gmail message submission returned HTTP …` identifies a rejection at the sending step. If Gmail accepted the message, check the recipient's Spam folder or, for a managed mailbox, its mail quarantine.

## Send reset links with Resend

For an initial test to your own inbox, a custom domain is not required:

For a masked local setup prompt, run this from the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/configure_reset_email.py
```

It asks for a sender, frontend origin and hidden Resend API key, then updates only the four mail settings in `backend/.env`. Existing database and session-secret settings are preserved. The helper requires an interactive terminal, does not accept secrets as command arguments and does not print the key. It does not create a provider account or verify inbox delivery; restart the backend and send a real reset request after completing setup. The manual equivalent follows:

1. Create a [Resend account](https://resend.com/signup) using the inbox you want to test. With the `onboarding@resend.dev` test sender, Resend permits delivery only to the email associated with that Resend account. See the [test-sender restriction](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).
2. Create an API key in the [Resend API keys dashboard](https://resend.com/api-keys), with email-sending access. Copy it into local backend settings; do not put it in chat, frontend settings or Git.
3. Add or update these four values in `backend/.env`, preserving the existing database and session-secret settings:

   ```dotenv
   PASSWORD_RESET_DELIVERY=resend
   PASSWORD_RESET_BASE_URL=http://localhost:3000
   PASSWORD_RESET_FROM_EMAIL=onboarding@resend.dev
   RESEND_API_KEY=YOUR_PRIVATE_RESEND_KEY
   ```

4. Restart the backend so it loads the settings. Open `/forgot-password` and request a **new** link for the email associated with the Resend account. Check its inbox, spam folder and Resend delivery logs. Existing file-outbox messages are not retroactively emailed.

For delivery to other patients or doctors, verify a domain you control and use a sender at that domain. A patient's university email can be the recipient; it does not give control of the university's sending domain. Follow the production settings below when moving from localhost to the hosted app. Resend documents [domain verification](https://resend.com/docs/dashboard/domains/introduction) and [private API keys](https://resend.com/docs/dashboard/api-keys/introduction).

Tokens contain 32 cryptographically random bytes, expire after 30 minutes by default and are stored only as SHA-256 digests. The email URL carries the secret in a fragment, which is not sent to the frontend server. The reset page removes the fragment from browser history after loading and keeps the token only in memory. Reopening the original email link restores an unused link; reloading the cleaned page requires opening the email again. Reset links are constructed from the configured frontend origin, never incoming request headers.

Password changes, token consumption, invalidation of all other reset links, session revocation and the audit event commit together. Conditional database updates protect against replay and stale concurrent resets. Account deactivation also invalidates pending links. Patient erasure plans include the new token table. Audit events and application logs omit tokens, email bodies and provider error details. Passwords use the same bcrypt and 12–72 character/72 UTF-8 byte policy as registration.

The interface supports all six application languages. Recovery email messages are currently in English and contain no clinical records. The implementation follows the relevant controls in the [OWASP forgot-password guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

## Hosted delivery

For this repository's existing Vercel/Render deployment, follow [HOSTING_UPDATE.md](HOSTING_UPDATE.md). The live frontend origin is `https://caregap360.vercel.app`; local `.env` values do not update the hosted backend.

Production and public demo recovery is disabled by default until a sender is configured. Requests then show an unavailable message, rather than claiming to send mail. Set these **backend-only** environment variables to use the Resend HTTPS API:

```dotenv
PASSWORD_RESET_DELIVERY=resend
PASSWORD_RESET_BASE_URL=https://YOUR_FRONTEND.vercel.app
PASSWORD_RESET_FROM_EMAIL=accounts@YOUR_VERIFIED_DOMAIN
RESEND_API_KEY=YOUR_PRIVATE_PROVIDER_KEY
```

Use a sender/domain verified with the email provider. Enter the real key in the backend host's secret settings; never commit it or expose it with `NEXT_PUBLIC_*`. The frontend origin must be HTTPS in production. Resend delivery uses its [documented HTTPS email endpoint](https://resend.com/docs/api-reference/emails/send-email) with a bounded timeout. Its test sender may restrict recipients; verify real delivery to an intended test inbox before enabling recovery for users.

The HTTPS adapter is suitable for the existing Render setup because [free Render services block outbound SMTP ports 25, 465 and 587](https://render.com/docs/free). Do not assume a normal SMTP configuration will work on that tier. This change does not create a provider account, configure credentials, send an external test email or deploy the app.

On hosts that allow SMTP, use these backend settings instead:

```dotenv
PASSWORD_RESET_DELIVERY=smtp
PASSWORD_RESET_BASE_URL=https://YOUR_FRONTEND
PASSWORD_RESET_FROM_EMAIL=accounts@YOUR_DOMAIN
SMTP_HOST=YOUR_MAIL_HOST
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=YOUR_MAIL_USERNAME
SMTP_PASSWORD=YOUR_PRIVATE_MAIL_PASSWORD
```

For an implicit-TLS server, use `SMTP_SECURITY=tls` and its configured port. Both SMTP modes validate server certificates; plaintext delivery is not supported. Credentials stay in backend settings.

Delivery failures invalidate the corresponding token and produce only a generic operational log and audit event. The browser keeps a generic response to protect account privacy. Delivery is an in-process background task without automatic retry: a restart can interrupt an unsent message. Users can request another link after the cooldown. Monitor delivery failures and provider receipts when operating the service.

## Local development

Without an explicit delivery setting, development/test environments write `.eml` messages to `backend/storage/password-reset-outbox/`. This ignored directory is not served by any API. An operator can open the development message and use its link to exercise recovery with synthetic data. Never expose the directory or its contents publicly; these files contain live reset credentials until expiry. Remove local development mail when it is no longer needed. On Windows the files inherit local directory permissions; they are not a substitute for managed secret storage.

`PASSWORD_RESET_OUTBOX_DIR` can select another private development location, and `PASSWORD_RESET_BASE_URL` must match the frontend URL. Docker defaults to `http://localhost:3300`; direct development defaults to `http://localhost:3000`. Update the origin when changing ports. Docker development mail is inside the backend container at `/app/storage/password-reset-outbox/`. Production rejects the local outbox mode.

Migration `0020` creates the reset-token table without changing existing accounts, passwords or sessions. On PostgreSQL it also enables row-level security and revokes public/Supabase Data API role grants for that table; the existing backend table-owner connection retains access. Apply normal migrations before starting the updated backend:

```powershell
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
```

The container startup already applies migrations. Browser tests use a disposable database and a separate ignored synthetic mailbox; API tests use temporary mail directories and mock external providers. Real mailbox delivery still needs verification after provider configuration.
