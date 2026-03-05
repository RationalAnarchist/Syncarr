with open("static/index.html", "r") as f:
    content = f.read()

import re

# Remove the top bar inputs
content = re.sub(
    r'<input type="text" id="overseerrApiKey" placeholder="Overseerr API Key".*?>\s*<button onclick="linkOverseerr\(\)" id="linkOverseerrBtn" class="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-md font-medium transition text-sm flex items-center">\s*Link Overseerr\s*</button>',
    '',
    content,
    flags=re.DOTALL
)

# RenderCard Updates
new_render_card = """
        let selectedApps = new Set();
        let overseerrLinkedKeys = [];
        let allDiscoveredApps = [];

        function toggleAppSelection(apiKey) {
            if (!apiKey) return;
            if (selectedApps.has(apiKey)) {
                selectedApps.delete(apiKey);
            } else {
                selectedApps.add(apiKey);
            }
            renderAllCards();
        }

        const renderCard = (appData) => {
            const accentColor = getAppColor(appData.app);
            const urlBaseDisplay = appData.urlBase ? appData.urlBase : '/';

            const isSelectable = ['sonarr', 'radarr'].includes(appData.app.toLowerCase());
            const isSelected = selectedApps.has(appData.apiKey);

            let cardClasses = `bg-servarrCard rounded-lg shadow-lg border border-servarrBorder overflow-hidden flex flex-col transition hover:border-gray-600`;
            if (isSelectable && isSelected) {
                cardClasses = `bg-servarrCard rounded-lg shadow-lg border-2 border-servarrCyan overflow-hidden flex flex-col transition scale-[1.02]`;
            }

            let selectionIndicator = '';
            if (isSelectable) {
                selectionIndicator = `
                    <div class="absolute top-2 right-2 z-10">
                        <input type="checkbox" class="w-5 h-5 rounded bg-gray-900 border-gray-700 text-servarrCyan focus:ring-servarrCyan cursor-pointer pointer-events-none" ${isSelected ? 'checked' : ''} />
                    </div>
                `;
            }

            let linkButton = '';
            if (appData.app.toLowerCase() === 'overseerr') {
                linkButton = `
                    <div class="mt-4 pt-4 border-t border-gray-700">
                        <button onclick="linkOverseerr('${appData.apiKey}')" id="linkOverseerrBtn" class="w-full bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-md font-medium transition text-sm flex items-center justify-center">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                            Link Selected Instances
                        </button>
                    </div>
                `;
            }

            let linkedBadge = '';
            if (isSelectable && overseerrLinkedKeys.includes(appData.apiKey)) {
                linkedBadge = `
                    <span class="ml-2 px-2 py-0.5 bg-green-900/50 text-green-400 text-xs font-medium rounded border border-green-700 flex items-center" title="Linked to Overseerr">
                        <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        Linked
                    </span>
                `;
            }

            return `
                <div class="${cardClasses} relative ${isSelectable ? 'cursor-pointer' : ''}" ${isSelectable ? `onclick="toggleAppSelection('${appData.apiKey}')"` : ''}>
                    ${selectionIndicator}
                    <div class="h-1 ${accentColor} w-full"></div>
                    <div class="p-5 flex-1 flex flex-col relative">
                        <div class="flex items-center mb-4 pr-6">
                            <h3 class="text-xl font-bold text-white">${appData.app}</h3>
                            ${linkedBadge}
                            <span class="ml-auto px-2.5 py-1 bg-gray-800 text-xs font-medium rounded text-gray-300 border border-gray-700">Port ${appData.port}</span>
                        </div>

                        <div class="space-y-3 flex-1">
                            <div>
                                <label class="text-xs text-gray-500 uppercase font-semibold tracking-wider">API Key</label>
                                <div class="mt-1 flex items-center bg-gray-900 rounded border border-gray-700 p-2">
                                    <code class="text-sm text-gray-300 font-mono truncate flex-1">${appData.apiKey || 'Not found'}</code>
                                </div>
                            </div>

                            <div class="flex items-center justify-between">
                                <div>
                                    <label class="text-xs text-gray-500 uppercase font-semibold tracking-wider">URL Base</label>
                                    <p class="text-sm text-gray-300 mt-0.5 font-mono">${urlBaseDisplay}</p>
                                </div>
                                <div>
                                    <label class="text-xs text-gray-500 uppercase font-semibold tracking-wider">Config Path</label>
                                    <p class="text-xs text-gray-400 mt-0.5 truncate max-w-[120px]" title="${appData.path}">.../${appData.path.split('/').pop()}</p>
                                </div>
                            </div>
                        </div>
                        ${linkButton}
                    </div>
                </div>
            `;
        };

        function renderAllCards() {
            const resultsGrid = document.getElementById('resultsGrid');
            if (allDiscoveredApps && allDiscoveredApps.length > 0) {
                const overseerrApp = allDiscoveredApps.find(a => a.app.toLowerCase() === 'overseerr');
                overseerrLinkedKeys = overseerrApp && overseerrApp.linkedApiKeys ? overseerrApp.linkedApiKeys : [];

                const cardsHtml = allDiscoveredApps.map(app => renderCard(app)).join('');
                resultsGrid.innerHTML = cardsHtml;
            }
        }

        async function discoverApps() {
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');
            const resultsGrid = document.getElementById('resultsGrid');
            const emptyState = document.getElementById('emptyState');

            loading.classList.remove('hidden');
            error.classList.add('hidden');
            resultsGrid.innerHTML = '';
            emptyState.classList.add('hidden');

            selectedApps.clear();

            try {
                const response = await fetch('/api/discover');
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to scan configurations.');
                }

                if (data.data && data.data.length > 0) {
                    allDiscoveredApps = data.data;
                    renderAllCards();
                } else {
                    allDiscoveredApps = [];
                    emptyState.classList.remove('hidden');
                    emptyState.innerHTML = '<p class="text-lg text-gray-400">Scan completed. No config files found.</p>';
                }
            } catch (err) {
                error.textContent = err.message;
                error.classList.remove('hidden');
                emptyState.classList.remove('hidden');
            } finally {
                loading.classList.add('hidden');
            }
        }
"""

content = re.sub(
    r'        const renderCard = \(appData\) => \{.*?(?=        async function fetchSettings)',
    new_render_card,
    content,
    flags=re.DOTALL
)

with open("static/index.html", "w") as f:
    f.write(content)
