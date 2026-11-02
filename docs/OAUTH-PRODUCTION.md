# Existing OAuth app: production readiness, not publication

Project `xbox-twitch-recorder`; existing Web OAuth client **Xbox Twitch Recorder**. Reuse that client and existing website. No duplicate client/project/site, paid hosting, IAM/billing enablement, publishing, merge or deployment is performed by this preparation.

## Known state and limits

Latest owner report: **External / In production**, drive.file configured, Drive/Picker APIs enabled, localhost origin/callback saved. The prior Testing status is historical; do not ask the owner to publish or reconfigure it again. These are owner-provided facts, not an independent Console inspection. No Google Cloud outbound identity is configured in this environment; actual Branding/Data Access fields, developer/support email, domain ownership, branding review state and live page availability remain unverified. Never infer the OAuth app name from its client name, or infer scope grants from the source request.

The source now provides the app description, a same-domain linked privacy policy, precise requested scope, owner Picker consent flow, Google-data use/storage/sharing/retention/revocation disclosures, and a Limited Use policy commitment. The website is still explicitly inactive. The existing URLs were attempted through the web tool but could not be accessed; this is not proof of an HTTP status, deployment or domain failure. Source preparation does not make a URL public. No new website or alternative paid hosting is proposed.

## Values prepared for the existing Branding page

Console: https://console.cloud.google.com/auth/branding?project=xbox-twitch-recorder

| Branding field | Prepared value / boundary |
| --- | --- |
| App name | Xbox Twitch Recorder (confirm actual app name; client name is separately known) |
| Application home page | https://xbox.mrhype420.com/ |
| Application privacy policy link | https://xbox.mrhype420.com/privacy |
| Authorized domain, if requested | mrhype420.com (registrable root; not the subdomain or a URL) |
| User support email | Owner-selected reachable address; not supplied/guessed in this repository |
| Developer contact email | Owner-selected reachable address; do not publish/guess it in source |
| Logo | Preserve existing choice; do not add the website icon as a consent logo automatically |
| Terms of service | Optional; do not create a duplicate page solely to fill an optional field |
| Existing JavaScript origin | http://localhost:8765 — preserve owner-saved setting |
| Existing redirect URI | http://localhost:8765/callback — preserve owner-saved setting |

No field is claimed missing without seeing the Console. Save edits only as an owner-reviewed draft where supported; do not click Publish app or Publish branding. Do not add localhost as a registrable authorized domain. If domain ownership verification is requested, use the same project-associated owner and existing domain; DNS/Search Console changes require separate approval. No domain verification or approval is assumed.

## What verification drive.file actually requires

Google's [Drive scope classification](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) places `https://www.googleapis.com/auth/drive.file` under **non-sensitive** scopes. It does not require sensitive/restricted scope verification or a restricted-scope security assessment. The current guide describes basic OAuth app verification for non-sensitive access; do not simplify that to a blanket claim that Google never requires any review.

**Branding is separate.** Google's [brand verification guidance](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification) discusses verifying identity/links and display branding. It explicitly documents an exception for an app used only by its owner or a few personally known users. This repository describes an owner-only personal recorder, so that exception is relevant; actual Console requirements must still be inspected, and no review/approval is claimed. Public GitHub source does not by itself make the OAuth app a public multi-user service. Wider distribution or extra scopes requires a fresh review.

The requested scope remains exactly drive.file in the owner helper and runtime. No broad drive, drive.readonly, metadata-wide, Gmail, contacts, or unnecessary sign-in scopes are added. The existing Console's configured scope set has not been read. Do not change permission grants or request additional scopes to make verification easier.

## Why Testing must be addressed before unattended consent

Google's [OAuth refresh-token guidance](https://developers.google.com/identity/protocols/oauth2#expiration) says an External app in Testing receives seven-day refresh tokens unless only basic identity scopes are requested. drive.file is outside that exception. Being a test user does not remove that refresh-token restriction.

Moving the app to In production requires **separate owner approval** and does not itself authorize Drive or activate Actions. After approved publication, obtain a fresh offline grant with the existing helper; do not assume an old Testing-issued token becomes long-lived. Production tokens can still be revoked, expire through inactivity or account policy, or be replaced; never promise permanent authorization.

Production readiness is not a request to create a parallel project/client, remove the saved callback, submit a review, bypass warnings, or change DNS. Follow any actual Console prompt in the context of this owner-only app and ask before an approval boundary, rather than copying generic public-app checklists blindly.

## Current owner interaction

Production is now owner-confirmed. Do not repeat the completed origin, callback, scope or publishing setup. Obtain a fresh owner Drive grant using the [browser-only connection plan](DRIVE-AUTHORIZATION.md). No Google Cloud setting is changed by the prepared broker, and no recording workflow is activated. Branding field values above remain reference values, not a claim that the actual Console was independently inspected or that live website URLs were verified.
