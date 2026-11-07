# GitHub publication commands

This records the commands used for the publication requested on 7 November 2026. The destination is `https://github.com/Tanish3115/CareGap.git`, branch `main`. Runtime credentials, databases, patient documents, backups, dependencies, build output and the unrelated local `README.zip` are excluded. Hosting is a separate operation.

Commands run from `C:\Users\tanis\OneDrive\Documents\CareGap` unless a different directory is shown. The sequence below describes this publication; commit hashes and remote results are verified after the push.

| Command | Meaning |
| --- | --- |
| `$env:GIT_CONFIG_COUNT='0'` | Clears inherited command-scope Git configuration entries in this shell. It does not change saved Git settings. |
| `git -c safe.directory=C:/Users/tanis/OneDrive/Documents/CareGap ...` | Trusts this workspace for this command because the Windows sandbox has a different owner identity. The following Git commands use this prefix. |
| `git status --short` | Lists modified, new and deleted files before publication. |
| `git branch -vv` | Shows the current branch and its upstream relationship. |
| `git remote -v` | Confirms the existing GitHub fetch/push destination. |
| `git log -5 --oneline` | Shows recent local commits. |
| `git fetch origin --prune` | Downloads current GitHub branch history and removes stale remote references, without changing application files. |
| `git ls-remote --symref origin HEAD` | Identifies GitHub's default branch and checks the server's current commit. |
| `git branch -r` | Lists downloaded remote branches. |
| `git log --oneline --left-right HEAD...origin/main` | Shows commits unique to the local branch and GitHub main. |
| `git diff --stat HEAD..origin/main` | Summarizes differences between those committed versions; it excludes uncommitted work. |
| `git show --stat d3c3a53` | Inspects the remote archive-upload commit before integrating its history. |
| `git diff --stat dc1923e..origin/main` | Confirms the two remote archive commits have no net source changes relative to the common ancestor. |
| `git ls-files` | Lists currently tracked files for the publication review. |
| `git check-ignore -- <paths>` | Confirms private environments, runtime data, archives and build directories are ignored. |
| `git add -- <reviewed source paths>` | Stages the reviewed source, tests, templates and documentation. The actual path list comes from the verified source-package manifest; ignored generated files are excluded. |
| `git diff --cached --stat` | Reviews the staged change summary. |
| `git diff --cached --check` | Checks staged changes for whitespace errors and conflict markers. |
| `git -c user.name='CareGap Development' -c user.email='development@caregap.local' commit -m 'Publish CareGap application workflows and deployment tooling'` | Records the staged project using an explicit local commit identity without changing global settings. |
| `git -c user.name='CareGap Development' -c user.email='development@caregap.local' merge origin/main --no-edit` | Preserves GitHub's existing commits while integrating the latest local project. |
| `git push origin HEAD:main` | Uploads the resulting history to GitHub main using a normal push. It does not force-rewrite remote history. |
| `git rev-parse HEAD` | Gets the complete local commit identifier. |
| `git ls-remote origin refs/heads/main` | Checks that GitHub main points to the same commit after publication. |

Verification commands used for this publication:

```powershell
# Creates and verifies a source-only archive in ignored .tools/handover.
.\backend\.venv\Scripts\python.exe scripts/package_handover.py

# Checks Python lint and formatting from backend.
Set-Location backend
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff format --check app tests
.\.venv\Scripts\python.exe -m pytest -q
Set-Location ..

# Checks frontend source, types and complete translation catalogs.
Set-Location frontend
npm run lint
npm run typecheck
npm run check:locales
Set-Location ..
```

Additional read-only commands include `Get-Content` (read project configuration/documentation), `Get-Command gh` (check whether GitHub CLI is installed), and `rg` (search files). A private local audit compares staged files with configured secret values and rejects private-key material, credential token patterns and unapproved data artifacts; it reports file names and counts without exposing secrets.

GitHub authentication uses the machine's existing Git credential mechanism. Passwords/tokens are not embedded in command lines or repository URLs. If the branch changes again during publication, fetch and integrate those changes before retrying; never force-push to bypass them.

The source allowlist and private-value audit were run with these local helper commands:

```powershell
.\backend\.venv\Scripts\python.exe .tools/publication_git.py stage
.\backend\.venv\Scripts\python.exe .tools/publication_git.py audit
```

`stage` reads the verified archive manifest, skips ignored generated files, scans approved sources and stages them in small batches with `git add -- <paths>`. `audit` checks every staged/tracked file and every outgoing commit for private paths, configured credential values, credential patterns and unapproved application-data artifacts. The helper is intentionally kept under ignored `.tools`; it reads private environment values locally without publishing them. The credential scan passed for 311 tracked files and the one previously unpushed local commit before this publication commit.
