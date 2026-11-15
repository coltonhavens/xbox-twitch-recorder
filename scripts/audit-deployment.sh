#!/usr/bin/env bash
# Read-only. Requires already authorized gh and gcloud. Never prints secret values.
set -euo pipefail
repo=coltonhavens/xbox-twitch-recorder
project=xbox-twitch-recorder
sa=github-hosting-deploy@xbox-twitch-recorder.iam.gserviceaccount.com
gh api "repos/$repo" --jq '{id,owner_id:.owner.id,default_branch,permissions}'
gh api "repos/$repo/environments/firebase-production" --jq '{name,deployment_branch_policy,protection_rules}'
gh api "repos/$repo/environments/firebase-production/deployment-branch-policies" --jq '.branch_policies'
gh variable list --repo "$repo" --json name,value --jq 'map(select(.name == "FIREBASE_DEPLOY_ENABLED" or .name == "GCP_WORKLOAD_IDENTITY_PROVIDER" or .name == "GCP_DEPLOY_SERVICE_ACCOUNT"))'
gh variable list --repo "$repo" --env firebase-production --json name,value --jq 'map(select(.name == "FIREBASE_DEPLOY_ENABLED" or .name == "GCP_WORKLOAD_IDENTITY_PROVIDER" or .name == "GCP_DEPLOY_SERVICE_ACCOUNT"))'
gh api "repos/$repo/actions/permissions"
gh api "repos/$repo/actions/permissions/workflow"
gh api "repos/$repo/branches/main/protection"
gh api "repos/$repo/rulesets"
gcloud projects describe "$project" --format='value(projectId,projectNumber)'
gcloud iam service-accounts describe "$sa" --project="$project"
gcloud iam service-accounts keys list --iam-account="$sa" --managed-by=user --project="$project" --format='table(name,validAfterTime,validBeforeTime)'
gcloud iam service-accounts get-iam-policy "$sa" --project="$project"
gcloud projects get-iam-policy "$project" --flatten='bindings[].members' --filter="bindings.members:serviceAccount:$sa" --format='table(bindings.role,bindings.members)'
gcloud iam workload-identity-pools providers describe github --workload-identity-pool=github-hosting --location=global --project="$project"
