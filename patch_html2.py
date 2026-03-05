import re

with open("static/index.html", "r") as f:
    content = f.read()

new_link_function = """        async function linkOverseerr(apiKey) {
            if (!apiKey) {
                showToast('Error', 'Overseerr API Key missing.', true);
                return;
            }

            if (selectedApps.size === 0) {
                showToast('Info', 'Please select at least one Sonarr or Radarr instance to link.', false);
                return;
            }

            const appsToLink = Array.from(selectedApps);

            const btn = document.getElementById('linkOverseerrBtn');
            const originalContent = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `
                <svg class="animate-spin h-4 w-4 mr-2 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Linking...
            `;

            try {
                const response = await fetch('/api/link/overseerr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_key: apiKey, port: 5055, apps_to_link: appsToLink })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to link Overseerr.');
                }

                if (data.status === 'success') {
                    showToast('Linked Successfully', 'Overseerr has been linked with selected apps.');
                    // Rescan to update the linked status badges
                    discoverApps();
                } else if (data.status === 'partial_success') {
                    showToast('Partial Success', 'Some apps failed to link. Check logs.', true);
                    discoverApps();
                } else {
                    showToast('Link Failed', 'Failed to link any apps to Overseerr.', true);
                }

            } catch (err) {
                showToast('Link Failed', err.message, true);
            } finally {
                if(btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalContent;
                }
            }
        }"""

content = re.sub(
    r'        async function linkOverseerr\(\) \{.*?(?=        async function triggerBackup)',
    new_link_function + "\n\n",
    content,
    flags=re.DOTALL
)

with open("static/index.html", "w") as f:
    f.write(content)
