# Chrome Setup Guide

How to install and configure Claude in Chrome for LinkedIn job searching.

## Prerequisites

- Google Chrome browser (latest version)
- Claude desktop app with Cowork mode
- LinkedIn account (free or Premium)

## Installation

### Step 1: Install Claude in Chrome Extension

1. Open Chrome and navigate to the Chrome Web Store
2. Search for "Claude in Chrome" or visit the direct link
3. Click "Add to Chrome" and confirm the installation
4. The Claude icon should appear in your Chrome toolbar

### Step 2: Connect the Extension

1. Click the Claude icon in the Chrome toolbar
2. Follow the OAuth flow to connect your Claude account
3. Once connected, the icon should show a green indicator

### Step 3: Verify Connection

In Cowork, Claude can test the connection by running:
```
tabs_context_mcp
```

If this returns information about your open Chrome tabs, the extension is connected and working.

## LinkedIn Login

1. Open Chrome and navigate to `https://www.linkedin.com`
2. Log in with your LinkedIn credentials
3. Stay logged in — don't log out between scout runs
4. If you use LinkedIn Premium, even better — it provides additional data on job listings

**Important:** The scout never enters credentials on your behalf. If you're not logged in when the scout runs, it will stop and ask you to log in manually.

## Troubleshooting

### Extension Not Connecting

**Symptom:** Claude says it can't access Chrome tools.

**Fixes:**
1. Check that the extension is enabled in `chrome://extensions`
2. Click the extension icon and re-authorize
3. Restart Chrome completely
4. If using a VPN or proxy, try disabling it temporarily
5. Clear the extension's data: `chrome://extensions` → Claude in Chrome → Remove → Reinstall

### OAuth Error

**Symptom:** Error mentioning "Redirect URI" or "chrome-extension://" not supported.

**Fixes:**
1. Remove the extension completely from `chrome://extensions`
2. Clear Chrome cache and cookies for the Claude domain
3. Reinstall the extension from the Chrome Web Store
4. Re-authorize through the OAuth flow
5. If the error persists, try in a new Chrome profile

### Timeout on First Call

**Symptom:** `tabs_context_mcp` hangs for 60+ seconds then times out.

**Fixes:**
1. Check if Chrome is actually running (not minimized/sleeping)
2. Disable other extensions that might interfere (ad blockers, privacy extensions)
3. Open a new tab to wake Chrome up
4. Try again — first connection sometimes takes longer

### LinkedIn Bot Detection

**Symptom:** LinkedIn shows a CAPTCHA or blocks automated browsing.

**Mitigation:**
1. Don't run searches too rapidly — the scout should pause between page loads
2. Limit to 2-3 search queries per run (configurable in config.json)
3. Avoid running the scout more than once per day
4. If blocked, wait 24 hours before trying again
5. Using LinkedIn Premium reduces the likelihood of rate limiting

## Fallback Mode

If Claude in Chrome is unavailable (extension broken, Chrome not running, etc.), the scout can still be useful. It will:

1. Generate the list of search queries you would run
2. List the target companies to check manually
3. Provide the search URLs you can open yourself
4. Still score and generate tailoring briefs if you paste JD text back into the conversation

This fallback mode produces about 70% of the value — you lose the automation but keep the analysis.

## Performance Tips

- Keep Chrome open with minimal tabs (the extension works better with less clutter)
- Close tabs from previous scout runs before starting a new one
- LinkedIn loads faster if you have a stable internet connection
- Premium LinkedIn accounts get more search results and fewer rate limits
- Run the scout during off-peak hours (early morning) for better LinkedIn performance
