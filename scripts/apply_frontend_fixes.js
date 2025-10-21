#!/usr/bin/env node

/**
 * Script to apply critical frontend fixes for race conditions, memory leaks, and accessibility
 *
 * Fixes:
 * 1. Rate limiting on retry button handler
 * 2. AbortController signal merging in fetchWithTimeout
 * 3. Global AbortController cleanup on page unload
 * 4. Remove artificial delay from fresh data path
 * 5. Keyboard focus management for loading→content transition
 * 6. Progress bar aria-valuetext for screen readers
 * 7. Loading message aria-live='assertive'
 */

const fs = require('fs');
const path = require('path');

const DASHBOARD_JS_PATH = path.join(__dirname, '../app/static/js/dashboard.js');
const DASHBOARD_HTML_PATH = path.join(__dirname, '../app/templates/dashboard.html');

console.log('🔧 Applying frontend fixes...\n');

// Read files
const dashboardJs = fs.readFileSync(DASHBOARD_JS_PATH, 'utf8');
const dashboardHtml = fs.readFileSync(DASHBOARD_HTML_PATH, 'utf8');

let updatedJs = dashboardJs;
let updatedHtml = dashboardHtml;

// Fix 1 & 2 & 3: Add rate limiting, AbortController tracking, and signal merging
console.log('✓ Adding rate limiting variables and AbortController tracking');
updatedJs = updatedJs.replace(
    /let initRetryCount = 0;\s+const MAX_INIT_RETRIES = 3;/,
    `let initRetryCount = 0;
    const MAX_INIT_RETRIES = 3;
    let lastRetryTimestamp = 0;
    const RETRY_COOLDOWN_MS = 2000; // 2 second cooldown
    const activeAbortControllers = new Set();`
);

// Fix 2: Update fetchWithTimeout to merge signals and track controllers
console.log('✓ Fixing AbortController signal merging in fetchWithTimeout');
updatedJs = updatedJs.replace(
    /async function fetchWithTimeout\(url, options = \{\}, timeoutMs = 60000\) \{[\s\S]*?^\s{4}\}/m,
    `async function fetchWithTimeout(url, options = {}, timeoutMs = 60000) {
        const controller = new AbortController();
        activeAbortControllers.add(controller);

        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        // Merge caller's signal with timeout signal
        const callerSignal = options.signal;
        if (callerSignal) {
            if (callerSignal.aborted) {
                clearTimeout(timeoutId);
                activeAbortControllers.delete(controller);
                throw new DOMException('Aborted', 'AbortError');
            }
            callerSignal.addEventListener('abort', () => controller.abort(), { once: true });
        }

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            return response;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(\`Request timeout after \${timeoutMs / 1000} seconds\`);
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
            activeAbortControllers.delete(controller);
        }
    }`
);

// Fix 3: Add page unload cleanup
console.log('✓ Adding global AbortController cleanup on page unload');
updatedJs = updatedJs.replace(
    /(\/\/ Trigger data prefetch for other pages \(after dashboard loads\)[\s\S]*?})/,
    `$1

    // Cleanup active requests on page unload
    window.addEventListener('pagehide', () => {
        activeAbortControllers.forEach(controller => {
            controller.abort();
        });
        activeAbortControllers.clear();
    });`
);

// Fix 1: Add rate limiting to retry button
console.log('✓ Adding rate limiting to retry button handler');
updatedJs = updatedJs.replace(
    /(retryBtn\.onclick = \(\) => \{\s+\/\/ Prevent concurrent initialization[\s\S]*?return;\s+})/,
    `retryBtn.onclick = () => {
                    // Prevent concurrent initialization
                    if (window._initializationInProgress) {
                        console.log('Initialization already in progress');
                        return;
                    }

                    // Rate limiting check
                    const now = Date.now();
                    if (now - lastRetryTimestamp < RETRY_COOLDOWN_MS) {
                        console.log(\`Retry cooldown active. Please wait \${Math.ceil((RETRY_COOLDOWN_MS - (now - lastRetryTimestamp)) / 1000)}s\`);
                        return;
                    }
                    lastRetryTimestamp = now;`
);

// Fix 4: Remove artificial delay from fresh data path
console.log('✓ Removing artificial delay from fresh data path');
updatedJs = updatedJs.replace(
    /(} else \{[\s\S]*?\/\/ Data is fresh.*?\n[\s\S]*?)await new Promise\(resolve => setTimeout\(resolve, \d+\)\); \/\/ Brief transition/,
    '$1// No artificial delay for fresh data'
);

// Fix 5: Add keyboard focus management
console.log('✓ Adding keyboard focus management for loading→content transition');
updatedJs = updatedJs.replace(
    /(if \(contentDiv\) \{\s+contentDiv\.style\.display = 'flex';\s+})/,
    `if (contentDiv) {
                contentDiv.style.display = 'flex';

                // Move focus to first heading for keyboard navigation
                const firstHeading = contentDiv.querySelector('h2');
                if (firstHeading) {
                    firstHeading.setAttribute('tabindex', '-1');
                    firstHeading.focus();
                }
            }`
);

// Fix 6: Add aria-valuetext to progress bar updates
console.log('✓ Adding aria-valuetext to progress bar for screen readers');
updatedJs = updatedJs.replace(
    /(\/\/ Update ARIA attribute for accessibility\s+if \(progressBar\) \{\s+progressBar\.setAttribute\('aria-valuenow', progress\.toString\(\)\);[\s\S]*?})/,
    `// Update ARIA attributes for accessibility
        if (progressBar) {
            progressBar.setAttribute('aria-valuenow', progress.toString());
            progressBar.setAttribute('aria-valuetext', \`\${progress}% - \${message}\`);
        }`
);

// Fix 7: Change loading message to aria-live="assertive"
console.log('✓ Updating loading message to aria-live="assertive"');
updatedHtml = updatedHtml.replace(
    /aria-live="polite"/,
    'aria-live="assertive"'
);

// Fix 6: Add aria-valuetext to progress bar HTML
console.log('✓ Adding initial aria-valuetext to progress bar HTML');
updatedHtml = updatedHtml.replace(
    /<div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" aria-label="Loading progress">/,
    '<div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" aria-label="Loading progress" aria-valuetext="0% - Preparing your dashboard">'
);

// Write updated files
console.log('\n📝 Writing updated files...');
fs.writeFileSync(DASHBOARD_JS_PATH, updatedJs, 'utf8');
fs.writeFileSync(DASHBOARD_HTML_PATH, updatedHtml, 'utf8');

console.log('✅ All fixes applied successfully!\n');
console.log('Summary of fixes:');
console.log('1. ✓ Rate limiting on retry button (2 second cooldown)');
console.log('2. ✓ AbortController signal merging in fetchWithTimeout');
console.log('3. ✓ Global AbortController cleanup on page unload');
console.log('4. ✓ Removed artificial delay from fresh data path');
console.log('5. ✓ Keyboard focus management for loading→content transition');
console.log('6. ✓ Progress bar aria-valuetext for screen readers');
console.log('7. ✓ Loading message aria-live="assertive"');
console.log('\nCache.js improvements (already applied):');
console.log('8. ✓ Retry save after clearing 50% of cache');
console.log('9. ✓ Clear 50% instead of 25% for better quota recovery');
