# Keyless GitHub Actions deployment setup

Status: source prepared for review only. No cloud resources or IAM bindings have been changed, and no deployment has been run by this change. Do not execute the provisioning commands or enable deployment until the owner approves the permissions below.

The workflow is `.github/workflows/deploy-firebase.yml`. It deploys only the existing static Hosting configuration in `firebase.json` (site `xbox-twitch-recorder`, directory `public/`). It does not build a backend, initialize Firebase, create a project, modify OAuth settings, or change DNS. Existing configuration and website files remain unchanged.

## Permissions to approve

An administrator will create a dedicated service account and dedicated Workload Identity pool/provider in the **existing** project `xbox-twitch-recorder`.

* Deployment service account: `github-hosting-deploy@xbox-twitch-recorder.iam.gserviceaccount.com`.
* `roles/firebasehosting.admin` on this project: the predefined Hosting deployment role, allowing Hosting versions/releases and site administration. It covers all Hosting sites in this project, not just this domain. No Editor, Owner, Firebase Admin, Storage Admin, or backend deployment roles.
* `roles/serviceusage.serviceUsageConsumer` on this project: allows use of enabled APIs under the project's quota. It cannot enable APIs.
* `roles/iam.workloadIdentityUser` **on this service account only**, for the GitHub repository ID principal set in the dedicated pool. This permits short-lived service account impersonation; no Service Account Token Creator role or JSON key is needed.
* Enable the IAM, IAM Credentials, Security Token Service, Firebase Management, and Firebase Hosting APIs if not already enabled.

The provisioning operator needs permission to enable APIs, create service accounts, create Workload Identity pools/providers, and update the project and service-account IAM policies (for example Service Usage Admin, Service Account Admin, Workload Identity Pool Admin, and Project IAM Admin, scoped to this existing project). These are setup privileges for the human operator, **never deployment-account roles**. Use an existing authorized operator; this guide does not grant those roles.

The provider restricts tokens by immutable repository and owner IDs, repository name, `main` branch, the exact workflow path, and the `firebase-production` environment subject. Pull requests, forks, other workflows, and manual runs from other branches cannot authenticate.

## 1. Configure GitHub's deployment gate before enabling anything

In repository Settings → Environments, create `firebase-production`. Under deployment branches/tags, select **Selected branches and tags** and allow only the branch `main` (no tags). Add the owner as a required reviewer if the repository plan supports this. An approval can be required for every future release; if that is undesirable, remove the recurring reviewer requirement only after initial cloud permission approval, retaining the branch restriction.

Keep the repository Actions variable `FIREBASE_DEPLOY_ENABLED` **unset** (or `false`) during review and merge. The job is skipped without this opt-in, including the push caused by merging this PR. The variable is a repository-admin-controlled rollout gate, not a replacement for environment protection or IAM restrictions.

Settings → Actions → General: allow the three pinned actions used by the workflow; use read-only default workflow token permissions and do not allow Actions to approve pull requests. The workflow grants only `contents: read` and job-scoped `id-token: write`. Protect `main` with PR review and restrict who can change workflows, environment settings, and Actions variables. No GitHub cloud credential secret is required.

## 2. Provision only after explicit owner approval

Use an authenticated administrator's Cloud Shell or workstation with `gcloud` and `gh`. Inspect the active account first. Never run `gcloud projects create`, `firebase init`, `gcloud iam service-accounts keys create`, or a DNS command.

Run this Bash block once. Use the exact repository ID returned from GitHub; do not substitute a repository name for the ID. If these dedicated resource names already exist, stop and inspect their configuration rather than overwriting or reusing an unrelated identity.

```bash
set -euo pipefail
PROJECT_ID=xbox-twitch-recorder
REPOSITORY=coltonhavens/xbox-twitch-recorder
POOL=github-hosting
PROVIDER=github
SA_NAME=github-hosting-deploy
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud projects describe "$PROJECT_ID" --format='table(projectId,projectNumber,name)'
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
REPOSITORY_ID="$(gh api "repos/$REPOSITORY" --jq '.id')"
OWNER_ID="$(gh api "repos/$REPOSITORY" --jq '.owner.id')"
test "$REPOSITORY_ID" = 1442216654
test "$OWNER_ID" = 230064597

gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  firebase.googleapis.com \
  firebasehosting.googleapis.com \
  --project="$PROJECT_ID"

gcloud iam service-accounts create "$SA_NAME" \
  --display-name="GitHub static Firebase Hosting deploy" \
  --project="$PROJECT_ID"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role=roles/firebasehosting.admin --condition=None
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role=roles/serviceusage.serviceUsageConsumer --condition=None

gcloud iam workload-identity-pools create "$POOL" \
  --location=global --display-name="GitHub Hosting deployment" \
  --project="$PROJECT_ID"

CONDITION="assertion.repository_id == '$REPOSITORY_ID' && assertion.repository_owner_id == '$OWNER_ID' && assertion.repository == '$REPOSITORY' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref == '$REPOSITORY/.github/workflows/deploy-firebase.yml@refs/heads/main' && assertion.sub == 'repo:$REPOSITORY:environment:firebase-production'"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --project="$PROJECT_ID" --location=global \
  --workload-identity-pool="$POOL" \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id" \
  --attribute-condition="$CONDITION"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository_id/$REPOSITORY_ID"

WIF_PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"
printf 'Provider: %s\nService account: %s\n' "$WIF_PROVIDER" "$SA_EMAIL"
```

Leave the provider's allowed audiences at the default: the auth action uses the full provider resource name as its audience. The project **number**, not project ID, belongs in the provider and principal-set paths. Do not add another provider to this dedicated pool without reviewing the impersonation binding.

Review the resulting provider and policies:

```bash
gcloud iam workload-identity-pools providers describe "$PROVIDER" \
  --project="$PROJECT_ID" --location=global --workload-identity-pool="$POOL"
gcloud iam service-accounts get-iam-policy "$SA_EMAIL" --project="$PROJECT_ID"
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten='bindings[].members' \
  --filter="bindings.members:serviceAccount:$SA_EMAIL" \
  --format='table(bindings.role,bindings.members)'
```

No user-managed service account key is created. The auth action generates a temporary external-account credential file on the ephemeral runner and cleans it up; that is not a long-lived JSON private key. It stays outside `public/`, is not committed, cached, or uploaded as an artifact. There is no `FIREBASE_TOKEN`, `credentials_json`, or interactive Firebase login in CI.

## 3. Configure identifiers and perform the first manual deployment

After the PR is reviewed and merged with the enable variable still unset, and after permission approval and provisioning:

```bash
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER \
  --repo "$REPOSITORY" --body "$WIF_PROVIDER"
gh variable set GCP_DEPLOY_SERVICE_ACCOUNT \
  --repo "$REPOSITORY" --body "$SA_EMAIL"
gh variable set FIREBASE_DEPLOY_ENABLED \
  --repo "$REPOSITORY" --body true
gh workflow run deploy-firebase.yml --repo "$REPOSITORY" --ref main
gh run list --repo "$REPOSITORY" --workflow deploy-firebase.yml --limit 5
```

These are **repository Actions variables**, not secrets; the identifiers are non-secret. Select the manual run's ID and monitor it with `gh run watch RUN_ID --repo "$REPOSITORY" --exit-status`, or use the Actions UI. Approve the `firebase-production` environment deployment when requested. Allow several minutes for new IAM policies to propagate; retry the manual run if propagation causes authentication failure.

The first deployment creates a new live Hosting release replacing the site's current files. Once enabled, every later push to `main` automatically queues deployment (subject to any configured environment reviewer). No deployment runs on PR events. Workflow runs manually selected on a feature branch are skipped and cannot authenticate with the provider.

The CLI version is fixed at `firebase-tools@15.14.0`, Node.js is 22, and all Actions use full commit SHAs. Review updates deliberately. Install the CLI before cloud authentication so installation scripts do not receive deployment credentials. Only `firebase deploy --only hosting --project xbox-twitch-recorder --non-interactive` is executed.

## 4. Verify before claiming success

The workflow's final step retries HTTPS GET requests up to twelve times per URL, requiring **HTTP 200 and a byte-for-byte match to the checked-out page**:

* https://xbox-twitch-recorder.web.app/
* https://xbox-twitch-recorder.web.app/privacy
* https://xbox.mrhype420.com/
* https://xbox.mrhype420.com/privacy

It does not follow redirects, so a redirect, generic fallback, old release, or missing policy cannot count as success. Firebase clean URLs serve `privacy.html` at `/privacy`. TLS verification remains enabled. There may be a short interval after release when the custom domain still serves cached content.

Only report success when the **deploy job actually ran** and both deployment and verification steps passed; a skipped workflow is not success. Record the Actions run URL, deployed commit SHA, and verification date. Inspect both pages in a browser as well as the stylesheet, response security headers, mobile layout, and a missing path's 404 response (see `docs/VERIFICATION.md`).

If deploy succeeds but verification fails, the release may already be live: inspect logs and Hosting release history; do not claim overall success. A pre-existing certificate/domain problem requires separate owner review; this workflow does not change DNS.

## Disable and recover

Set `FIREBASE_DEPLOY_ENABLED=false` to stop new deployment jobs. It does not revoke an already-issued token or cancel an active job. Cancel any active run separately. For an identity incident, disable the dedicated provider and remove its service-account impersonation binding; short-lived credentials may remain usable until expiry.

For a bad release, use Firebase Console → Hosting → release history to roll back with an authorized operator, then fix the source through a PR. Do not change DNS. Review the dedicated service account's project grants periodically and remove them if CI deployment is retired.

Reference: [Google GitHub auth action](https://github.com/google-github-actions/auth), [GitHub OIDC federation](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines#github-actions), [Firebase Hosting roles](https://firebase.google.com/docs/projects/iam/roles-predefined-product#hosting), [GitHub environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/managing-environments-for-deployment).
