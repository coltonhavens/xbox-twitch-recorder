'use strict';
let settings = null;
const status = document.getElementById('status');
async function post(path, body) {
  const response = await fetch(path, {method: 'POST', credentials: 'same-origin', headers: {
    'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest',
    ...(settings ? {'X-XTR-CSRF': settings.csrf} : {})}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Connection failed');
  return result;
}
async function initialize() {
  try {
    status.textContent = 'Preparing a secure connection…';
    settings = await post('/start', {});
    document.getElementById('google').disabled = false;
    status.textContent = 'Use your owner Google account, then select the existing archive folder.';
  } catch (error) { status.textContent = error.message; }
}
initialize();
document.getElementById('google').addEventListener('click', () => {
  if (!settings || !window.google?.accounts?.oauth2 || !window.gapi?.load) {
    status.textContent = 'Google sign-in is still loading. Try again shortly.'; return;
  }
  google.accounts.oauth2.initCodeClient({client_id: settings.clientId,
    scope: 'https://www.googleapis.com/auth/drive.file', ux_mode: 'popup',
    include_granted_scopes: false, select_account: true,
    callback: async response => {
      if (!response.code || response.error) { status.textContent = 'Google access was not approved.'; return; }
      try {
        const token = await post('/code', {code: response.code});
        // Access token stays in memory for Picker; refresh/client/GitHub secrets never reach this page.
        gapi.load('picker', () => {
          const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS).setIncludeFolders(true).setSelectFolderEnabled(true);
          new google.picker.PickerBuilder().addView(view).setOAuthToken(token.accessToken)
            .setDeveloperKey(settings.pickerKey).setAppId(settings.projectNumber).setOrigin(window.location.origin)
            .setCallback(async selected => {
              if (selected.action !== google.picker.Action.PICKED) return;
              try {
                await post('/finish', {folderId: selected.docs[0].id});
                token.accessToken = '';
                settings = null;
                document.getElementById('google').hidden = true;
                status.textContent = 'Google Drive connected securely. Recording is still off. You can close this page.';
              } catch (error) { status.textContent = error.message; }
            }).build().setVisible(true);
        });
      } catch (error) { status.textContent = error.message; }
    }}).requestCode();
});
