/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text safe for HTML insertion
 */
function escapeHtml(text) {
    if (typeof text !== 'string') {
        return '';
    }

    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    const syncBtn = document.getElementById('sync-btn');
    const languageToggle = document.getElementById('language-toggle');
    const themeToggle = document.getElementById('theme-toggle');
    const toastContainer = document.getElementById('toast-container');
    const dateElement = document.getElementById('current-date');

    const THEME_KEY = 'dashboard-theme';
    const LANGUAGE_KEY = 'dashboard-language';
    const FALLBACK_LANGUAGE = 'en';
    const TRANSITION_DELAY_MS = 200;
    const COMPLETION_DISPLAY_MS = 500;

    const translations = {
        en: {
            'meta.title': 'AI Training Optimizer - Dashboard',
            'header.title': '🏃 AI Training Optimizer',
            'button.language': '🇬🇧 English',
            'button.sync': '⬇️ Sync Data',
            'button.refresh': '🔄 Refresh',
            'loading.message': 'Analyzing your Garmin data with Claude AI...',
            'readiness.heading': "Overall Readiness (AI)",
            'confidence.label': 'Confidence: {value}',
            'trend.title': '7-day trend',
            'trend.need_more': 'Need more history',
            'recommendation.high_intensity': 'HIGH INTENSITY',
            'recommendation.moderate': 'MODERATE',
            'recommendation.easy': 'EASY',
            'recommendation.rest': 'REST',
            'workout.heading': '💪 Suggested Workout',
            'workout.duration': 'Duration',
            'workout.intensity': 'Intensity',
            'workout.rationale_heading': 'Why this workout?',
            'workout.duration_value': '{minutes} min',
            'workout.intensity_value': '{intensity} / 10',
            'enhanced.heading': '🔬 Enhanced Recovery Metrics',
            'enhanced.training_readiness': 'Garmin Training Readiness',
            'enhanced.vo2_max': 'VO₂ Max',
            'enhanced.training_status': 'Training Status',
            'enhanced.spo2': 'Blood Oxygen',
            'enhanced.respiration': 'Respiration',
            'enhanced.not_available': 'Not available',
            'enhanced.respiration_value': '{value} breaths/min',
            'enhanced.spo2_value': '{value}%{min_part}',
            'enhanced.spo2_min_part': ' (min: {value}%)',
            'factors.heading': '✅ Key Factors',
            'tips.heading': '💡 Recovery Tips',
            'red_flags.heading': '⚠️ Things to Watch',
            'analysis.heading': '🤖 AI Analysis',
            'extended.heading': '🧭 Additional Signals',
            'extended.recovery_time': 'Recovery Time',
            'extended.recovery_time_value': '{hours} h remaining',
            'extended.recovery_time_ready': 'Ready for high intensity',
            'extended.hydration': 'Hydration',
            'extended.hydration_value': '{intake} L of {goal} L goal',
            'extended.hydration_value_no_goal': '{intake} L consumed',
            'extended.hydration_note': 'Estimated sweat loss {sweat} L',
            'extended.load_focus': 'Load Focus',
            'extended.load_focus_entry': '{label}: {load}',
            'extended.load_focus_entry_with_range': '{label}: {load} (optimal {low}-{high})',
            'extended.load_focus_status': 'Status: {status}',
            'extended.acclimation': 'Heat & Altitude',
            'extended.acclimation_value': 'Heat {heat}% · Altitude {altitude}%',
            'extended.acclimation_heat_only': 'Heat {heat}%',
            'extended.acclimation_alt_only': 'Altitude {altitude}%',
            'extended.acclimation_status': '{status}',
            'extended.not_available': 'Not available',
            'load_focus.low_aerobic': 'Low Aerobic',
            'load_focus.high_aerobic': 'High Aerobic',
            'load_focus.anaerobic': 'Anaerobic',
            'load_focus.balance': 'Balanced',
            'load_focus_status.within': 'Optimal',
            'load_focus_status.over': 'High',
            'load_focus_status.under': 'Low',
            'list.empty': 'No data available.',
            'toast.sync_success': 'Sync successful! Refreshing with latest data...',
            'toast.sync_failure': 'Sync failed: {error}',
            'toast.load_failure': 'Failed to load recommendation: {error}',
            'error.loading_title': 'Error loading recommendation:',
            'status.acwr': 'ACWR · {ratio} ({status})',
            'status.last_sync': 'Last sync · {label}',
            'status.last_sync_unknown': 'Last sync · unknown',
            'status.just_now': 'just now',
            'status.minutes_ago': '{minutes} min ago',
            'status.hours_ago': '{hours} hr{plural} ago',
            'status.days_ago': '{days} day{plural} ago',
            'status.sync_in_progress': '⏳ Syncing...',
            'summary.activities': 'Activities · {count}',
            'summary.distance': 'Distance · {distance} km',
            'summary.duration': 'Time · {duration} min',
            'language.aria': 'Toggle language',
            'language.label.en': '🇬🇧 English',
            'language.label.de': '🇩🇪 Deutsch',
            'theme.dark': '🌙 Dark',
            'theme.light': '☀️ Light',
            'acwr.status.high': 'High',
            'acwr.status.moderate': 'Moderate',
            'acwr.status.low': 'Low',
            'acwr.status.optimal': 'Optimal',
            'acwr.status.elevated': 'Elevated',
            'acwr.status.warning': 'Warning',
            'acwr.status.unknown': 'Unknown',
            'loading.checking': 'Checking data freshness...',
            'loading.syncing': 'Syncing data with Garmin...',
            'loading.analyzing': 'Analyzing with Claude AI...',
            'loading.complete': 'Complete!',
            'loading.preparing': 'Preparing your dashboard...',
            'error.retry': 'Retry',
            'error.refresh_page': 'Refresh Page',
            'error.init_failed': 'Dashboard initialization failed: {error}',
            'error.retry_attempt': 'Retry attempt {current}/{max}',
            'error.max_retries': 'Maximum retries exceeded. Please refresh the page.',
            'error.unknown': 'Unknown error',
            'error.network': 'Network error. Check your internet connection.',
            'error.timeout': 'Request timed out. Please try again.',
            'error.sync_failed': 'Data sync failed. Please check Garmin connection.',
            'error.api_validation': 'Invalid data received from server.',
        },
        de: {
            'meta.title': 'KI Trainings-Optimierer - Dashboard',
            'header.title': '🏃 KI Trainings-Optimierer',
            'button.language': '🇩🇪 Deutsch',
            'button.sync': '⬇️ Daten synchronisieren',
            'button.refresh': '🔄 Aktualisieren',
            'loading.message': 'Analysiere deine Garmin-Daten mit Claude AI ...',
            'readiness.heading': 'Gesamtbereitschaft (KI)',
            'confidence.label': 'Vertrauen: {value}',
            'trend.title': '7-Tage-Trend',
            'trend.need_more': 'Mehr Verlauf nötig',
            'recommendation.high_intensity': 'HOHE INTENSITÄT',
            'recommendation.moderate': 'MODERAT',
            'recommendation.easy': 'LOCKER',
            'recommendation.rest': 'RUHETAG',
            'workout.heading': '💪 Vorgeschlagenes Workout',
            'workout.duration': 'Dauer',
            'workout.intensity': 'Intensität',
            'workout.rationale_heading': 'Warum dieses Workout?',
            'workout.duration_value': '{minutes} Min.',
            'workout.intensity_value': '{intensity} / 10',
            'enhanced.heading': '🔬 Erweiterte Erholungsmetriken',
            'enhanced.training_readiness': 'Garmin Trainingsbereitschaft',
            'enhanced.vo2_max': 'VO₂max',
            'enhanced.training_status': 'Trainingsstatus',
            'enhanced.spo2': 'Sauerstoffsättigung',
            'enhanced.respiration': 'Atmung',
            'enhanced.not_available': 'Nicht verfügbar',
            'enhanced.respiration_value': '{value} Atemzüge/Min.',
            'enhanced.spo2_value': '{value}%{min_part}',
            'enhanced.spo2_min_part': ' (Min.: {value}%)',
            'factors.heading': '✅ Wichtige Faktoren',
            'tips.heading': '💡 Erholungstipps',
            'red_flags.heading': '⚠️ Dinge zum Beobachten',
            'analysis.heading': '🤖 KI-Analyse',
            'extended.heading': '🧭 Zusätzliche Signale',
            'extended.recovery_time': 'Erholungszeit',
            'extended.recovery_time_value': '{hours} Std. verbleibend',
            'extended.recovery_time_ready': 'Bereit für intensive Einheiten',
            'extended.hydration': 'Hydration',
            'extended.hydration_value': '{intake} L von {goal} L Ziel',
            'extended.hydration_value_no_goal': '{intake} L getrunken',
            'extended.hydration_note': 'Geschätzter Schweißverlust {sweat} L',
            'extended.load_focus': 'Belastungsfokus',
            'extended.load_focus_entry': '{label}: {load}',
            'extended.load_focus_entry_with_range': '{label}: {load} (optimal {low}-{high})',
            'extended.load_focus_status': 'Status: {status}',
            'extended.acclimation': 'Hitze & Höhe',
            'extended.acclimation_value': 'Hitze {heat}% · Höhe {altitude}%',
            'extended.acclimation_heat_only': 'Hitze {heat}%',
            'extended.acclimation_alt_only': 'Höhe {altitude}%',
            'extended.acclimation_status': '{status}',
            'extended.not_available': 'Nicht verfügbar',
            'load_focus.low_aerobic': 'Niedrig aerobe Belastung',
            'load_focus.high_aerobic': 'Hoch aerobe Belastung',
            'load_focus.anaerobic': 'Anaerobe Belastung',
            'load_focus.balance': 'Ausgeglichen',
            'load_focus_status.within': 'Optimal',
            'load_focus_status.over': 'Zu hoch',
            'load_focus_status.under': 'Zu niedrig',
            'list.empty': 'Keine Daten verfügbar.',
            'toast.sync_success': 'Synchronisierung erfolgreich! Lade aktuelle Daten ...',
            'toast.sync_failure': 'Synchronisierung fehlgeschlagen: {error}',
            'toast.load_failure': 'Empfehlung konnte nicht geladen werden: {error}',
            'error.loading_title': 'Fehler beim Laden der Empfehlung:',
            'status.acwr': 'ACWR · {ratio} ({status})',
            'status.last_sync': 'Letzte Synchronisierung · {label}',
            'status.last_sync_unknown': 'Letzte Synchronisierung · unbekannt',
            'status.just_now': 'soeben',
            'status.minutes_ago': 'vor {minutes} Min.',
            'status.hours_ago': 'vor {hours} Std.',
            'status.days_ago': 'vor {days} Tag{plural}',
            'status.sync_in_progress': '⏳ Synchronisiere ...',
            'summary.activities': 'Aktivitäten · {count}',
            'summary.distance': 'Distanz · {distance} km',
            'summary.duration': 'Zeit · {duration} Min.',
            'language.aria': 'Sprache umschalten',
            'language.label.en': '🇬🇧 Englisch',
            'language.label.de': '🇩🇪 Deutsch',
            'theme.dark': '🌙 Dunkel',
            'theme.light': '☀️ Hell',
            'acwr.status.high': 'Hoch',
            'acwr.status.moderate': 'Mittel',
            'acwr.status.low': 'Niedrig',
            'acwr.status.optimal': 'Optimal',
            'acwr.status.elevated': 'Erhöht',
            'acwr.status.warning': 'Warnung',
            'acwr.status.unknown': 'Unbekannt',
            'loading.checking': 'Prüfe Datenaktualität...',
            'loading.syncing': 'Synchronisiere Daten mit Garmin...',
            'loading.analyzing': 'Analysiere mit Claude AI...',
            'loading.complete': 'Fertig!',
            'loading.preparing': 'Bereite dein Dashboard vor...',
            'error.retry': 'Erneut versuchen',
            'error.refresh_page': 'Seite aktualisieren',
            'error.init_failed': 'Dashboard-Initialisierung fehlgeschlagen: {error}',
            'error.retry_attempt': 'Versuch {current}/{max}',
            'error.max_retries': 'Maximale Versuche überschritten. Bitte Seite aktualisieren.',
            'error.unknown': 'Unbekannter Fehler',
            'error.network': 'Netzwerkfehler. Bitte Internetverbindung prüfen.',
            'error.timeout': 'Zeitüberschreitung. Bitte erneut versuchen.',
            'error.sync_failed': 'Datensynchronisierung fehlgeschlagen. Bitte Garmin-Verbindung prüfen.',
            'error.api_validation': 'Ungültige Daten vom Server erhalten.',
        },
    };

    const ACCEPT_LANGUAGE_HEADERS = {
        en: 'en-US,en;q=0.9',
        de: 'de-DE,de;q=0.9,en;q=0.5',
    };

    // Logger utility for production-safe logging
    const logger = {
        debug: (msg, ...args) => {
            if (window.DEBUG_MODE) {
                console.log(msg, ...args);
            }
        },
        warn: (msg, ...args) => console.warn(msg, ...args),
        error: (msg, ...args) => console.error(msg, ...args)
    };

    const dateLocales = {
        en: 'en-US',
        de: 'de-DE',
    };

    let currentLanguage = localStorage.getItem(LANGUAGE_KEY) ?? FALLBACK_LANGUAGE;
    if (!translations[currentLanguage]) {
        currentLanguage = FALLBACK_LANGUAGE;
    }

    let latestRecommendation = null;
    let lastSyncIso = null;
    let latestLoadSummary = null;
    let latestExtendedSignals = null;
    let syncInProgress = false;
    let initRetryCount = 0;
    const MAX_INIT_RETRIES = 3;
    let lastRetryTimestamp = 0;
    const RETRY_COOLDOWN_MS = 2000; // 2 second cooldown
    const activeAbortControllers = new Set();

    function getAcceptLanguageHeader(lang = currentLanguage) {
        return ACCEPT_LANGUAGE_HEADERS[lang] ?? lang;
    }

    function normalizeLanguageCode(lang) {
        if (!lang) {
            return null;
        }
        const trimmed = lang.trim().toLowerCase();
        if (!trimmed) {
            return null;
        }
        if (trimmed.includes('-')) {
            return trimmed.split('-')[0];
        }
        return trimmed;
    }

    // Ensure cache system is available with fallback
    if (typeof window.cachedFetch !== 'function') {
        logger.warn('Cache system not loaded, using direct fetch fallback');
        window.cachedFetch = async function(url, options = {}) {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        };
    }

    /**
     * Fetch with timeout protection.
     * @param {string} url - URL to fetch
     * @param {object} options - Fetch options
     * @param {number} timeoutMs - Timeout in milliseconds (default 60000ms = 60s)
     * @returns {Promise<Response>}
     */
    async function fetchWithTimeout(url, options = {}, timeoutMs = 60000) {
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
                throw new Error(`Request timeout after ${timeoutMs / 1000} seconds`);
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
            activeAbortControllers.delete(controller);
        }
    }

    /**
     * Validate and sanitize API response data to prevent XSS and injection attacks.
     * @param {object} data - Raw API response data
     * @returns {object} Validated data
     * @throws {Error} If validation fails
     */
    function validateApiResponse(data) {
        if (!data || typeof data !== 'object') {
            throw new Error('Invalid API response: expected object');
        }

        // Validate readiness_score (must be number 0-100)
        if (typeof data.readiness_score !== 'number' ||
            !Number.isFinite(data.readiness_score) ||
            data.readiness_score < 0 ||
            data.readiness_score > 100) {
            throw new Error('Invalid readiness_score: must be a number between 0-100');
        }

        // Validate workout_recommendation object
        if (data.workout_recommendation && typeof data.workout_recommendation !== 'object') {
            throw new Error('Invalid workout_recommendation: must be an object');
        }

        // Validate recent_training_load object
        if (data.recent_training_load && typeof data.recent_training_load !== 'object') {
            throw new Error('Invalid recent_training_load: must be an object');
        }

        // Validate readiness_history array
        if (data.readiness_history) {
            if (!Array.isArray(data.readiness_history)) {
                throw new Error('Invalid readiness_history: must be an array');
            }
            data.readiness_history.forEach((item, index) => {
                if (!item || typeof item !== 'object') {
                    throw new Error(`Invalid readiness_history[${index}]: must be an object`);
                }
                if (typeof item.score !== 'number' || !Number.isFinite(item.score)) {
                    throw new Error(`Invalid readiness_history[${index}].score: must be a finite number`);
                }
            });
        }

        // Validate string fields that will be displayed
        const stringFields = [
            'recommendation',
            'confidence',
            'language',
            'ai_reasoning'
        ];
        stringFields.forEach(field => {
            if (data[field] !== undefined && data[field] !== null && typeof data[field] !== 'string') {
                throw new Error(`Invalid ${field}: must be a string`);
            }
        });

        // Validate array fields
        const arrayFields = ['key_factors', 'red_flags', 'recovery_tips'];
        arrayFields.forEach(field => {
            if (data[field] !== undefined && data[field] !== null) {
                if (!Array.isArray(data[field])) {
                    throw new Error(`Invalid ${field}: must be an array`);
                }
                data[field].forEach((item, index) => {
                    if (typeof item !== 'string') {
                        throw new Error(`Invalid ${field}[${index}]: must be a string`);
                    }
                });
            }
        });

        // Validate enhanced_metrics if present
        if (data.enhanced_metrics && typeof data.enhanced_metrics !== 'object') {
            throw new Error('Invalid enhanced_metrics: must be an object');
        }

        // Validate extended_signals if present
        if (data.extended_signals && typeof data.extended_signals !== 'object') {
            throw new Error('Invalid extended_signals: must be an object');
        }

        return data;
    }

    applyStoredTheme();
    setLanguage(currentLanguage, { save: false, revalidate: false });

    themeToggle?.addEventListener('click', toggleTheme);
    languageToggle?.addEventListener('click', () => {
        const next = currentLanguage === 'en' ? 'de' : 'en';
        setLanguage(next, { revalidate: true });
    });
    refreshBtn?.addEventListener('click', () => {
        void handleRefresh();
    });
    syncBtn?.addEventListener('click', () => {
        void handleManualSync();
    });

    void initializeApp();
    // triggerAutoSync disabled - handled by initializeApp

    // Trigger data prefetch for other pages (after dashboard loads)
    if (window.dataPrefetcher) {
        window.dataPrefetcher.initPrefetch();
    }

    // Load alerts on page initialization
    void loadAlerts();

    // Cleanup active requests on page unload
    window.addEventListener('pagehide', () => {
        activeAbortControllers.forEach(controller => {
            controller.abort();
        });
        activeAbortControllers.clear();
    });

    /**
     * Initialize the app by checking data staleness and orchestrating sync/load flow.
     */
    async function initializeApp() {
        // Prevent concurrent initialization
        if (window._initializationInProgress) {
            logger.debug('Initialization already in progress, skipping');
            return;
        }

        // Check retry limit
        if (initRetryCount >= MAX_INIT_RETRIES) {
            logger.error('Maximum initialization retries exceeded');
            showLoadingError(
                t('error.max_retries'),
                true, // Disable retry button
                true  // Show refresh page button
            );
            return;
        }

        window._initializationInProgress = true;

        const loadingDiv = document.getElementById('loading');
        const contentDiv = document.getElementById('content');
        const errorDiv = document.getElementById('error');

        try {
            // Show loading screen
            if (loadingDiv) loadingDiv.style.display = 'block';
            if (contentDiv) contentDiv.style.display = 'none';
            if (errorDiv) errorDiv.style.display = 'none';

            // Check if data needs syncing
            updateLoadingStage('checking', 5, t('loading.checking'));
            const syncStatus = await checkSyncStatus();

            if (syncStatus.needs_sync) {
                // Data is stale - sync first
                await performSyncWithProgress();
            } else {
                // Data is fresh - skip to analyzing stage smoothly
                updateLoadingStage('syncing', 50, t('loading.preparing'));
                await new Promise(resolve => setTimeout(resolve, TRANSITION_DELAY_MS));
            }

            // Load the recommendation (includes analyzing stage)
            await loadRecommendation();

            // Success - reset retry count
            initRetryCount = 0;

        } catch (error) {
            logger.error('Initialization error:', error);
            initRetryCount++;

            const errorMessage = error instanceof Error ? error.message : t('error.unknown');
            const fullMessage = t('error.init_failed', { error: errorMessage });

            showLoadingError(
                fullMessage,
                initRetryCount >= MAX_INIT_RETRIES, // Disable retry if max reached
                initRetryCount >= MAX_INIT_RETRIES  // Show refresh button if max reached
            );
        } finally {
            window._initializationInProgress = false;
        }
    }

    /**
     * Check the sync status of data.
     */
    async function checkSyncStatus() {
        try {
            const response = await fetchWithTimeout('/api/health/sync-status', {}, 10000); // 10 second timeout
            if (!response.ok) {
                throw new Error(`Failed to check sync status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            logger.error('Error checking sync status:', error);
            // If status check fails, assume we need to sync to be safe
            return { needs_sync: true, is_stale: true };
        }
    }

    /**
     * Perform actual Garmin data sync.
     */
    async function performSyncWithProgress() {
        // Show syncing stage and perform actual sync (no fake delays)
        updateLoadingStage('syncing', 20, t('loading.syncing'));

        try {
            const response = await fetchWithTimeout('/manual/sync/now', {
                method: 'POST',
                headers: {
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            }, 60000); // 60 second timeout for sync

            if (!response.ok) {
                throw new Error(`Sync failed: ${response.status} ${response.statusText}`);
            }

            await response.json();
            lastSyncIso = new Date().toISOString();

        } catch (error) {
            logger.error('Sync error:', error);
            const errorMsg = error instanceof Error ? error.message : t('error.unknown');
            throw new Error(`Failed to sync data: ${errorMsg}`);
        }
    }

    /**
     * Update the loading stage UI.
     */
    function updateLoadingStage(stageName, progress, message) {
        // Update progress bar
        const progressFill = document.getElementById('progress-fill');
        const progressBar = progressFill?.parentElement;
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        // Update ARIA attributes for accessibility
        if (progressBar) {
            progressBar.setAttribute('aria-valuenow', progress.toString());
            progressBar.setAttribute('aria-valuetext', `${progress}% - ${message}`);
        }

        // Update message
        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) {
            loadingMessage.textContent = message;

            // CRITICAL FIX: Announce stage change to screen readers
            // Create temporary live region for assertive announcement
            const liveRegion = document.createElement('div');
            liveRegion.setAttribute('role', 'status');
            liveRegion.setAttribute('aria-live', 'assertive');
            liveRegion.setAttribute('aria-atomic', 'true');
            liveRegion.classList.add('sr-only');
            liveRegion.textContent = message;
            document.body.appendChild(liveRegion);

            // Remove after announcement (1 second)
            setTimeout(() => liveRegion.remove(), 1000);
        }

        // Update stage indicators
        const stages = document.querySelectorAll('.stage');
        stages.forEach(stageEl => {
            const stageData = stageEl.getAttribute('data-stage');
            if (stageData === stageName) {
                stageEl.classList.remove('stage-pending', 'stage-complete');
                stageEl.classList.add('stage-active');
            } else if (shouldMarkComplete(stageData, stageName)) {
                stageEl.classList.remove('stage-pending', 'stage-active');
                stageEl.classList.add('stage-complete');
            }
        });
    }

    /**
     * Determine if a stage should be marked as complete.
     */
    function shouldMarkComplete(stageData, currentStage) {
        const stageOrder = ['checking', 'syncing', 'analyzing'];
        const currentIndex = stageOrder.indexOf(currentStage);
        const stageIndex = stageOrder.indexOf(stageData);
        return stageIndex < currentIndex && stageIndex >= 0;
    }

    /**
     * Show loading error with retry button.
     * @param {string} message - Error message to display
     * @param {boolean} disableRetry - Whether to disable the retry button
     * @param {boolean} showRefreshButton - Whether to show a refresh page button
     */
    function showLoadingError(message, disableRetry = false, showRefreshButton = false) {
        const loadingDiv = document.getElementById('loading');
        const errorContainer = document.getElementById('loading-error');
        const errorText = document.getElementById('error-text');
        const retryBtn = document.getElementById('retry-btn');

        if (errorText) {
            errorText.textContent = message;
        }

        if (errorContainer) {
            errorContainer.style.display = 'block';
        }

        // Handle refresh button creation/removal
        let refreshPageBtn = errorContainer?.querySelector('.refresh-page-btn');
        if (showRefreshButton) {
            if (!refreshPageBtn) {
                refreshPageBtn = document.createElement('button');
                refreshPageBtn.className = 'refresh-page-btn';
                refreshPageBtn.textContent = t('error.refresh_page');
                // FIX: Use addEventListener instead of onclick to prevent memory leaks
                refreshPageBtn.addEventListener('click', handleRefreshPage);
                // Insert after retry button if it exists
                if (retryBtn && retryBtn.parentNode) {
                    retryBtn.parentNode.insertBefore(refreshPageBtn, retryBtn.nextSibling);
                } else if (errorContainer) {
                    errorContainer.appendChild(refreshPageBtn);
                }
            }
        } else if (refreshPageBtn) {
            refreshPageBtn.removeEventListener('click', handleRefreshPage);
            refreshPageBtn.remove();
        }

        // Handle retry button setup
        if (retryBtn) {
            // Disable retry button if max retries reached
            if (disableRetry) {
                retryBtn.disabled = true;
                retryBtn.style.opacity = '0.5';
                retryBtn.style.cursor = 'not-allowed';
            } else {
                retryBtn.disabled = false;
                retryBtn.style.opacity = '1';
                retryBtn.style.cursor = 'pointer';

                // FIX: Use addEventListener with named function to prevent memory leak
                retryBtn.removeEventListener('click', handleRetryInit);
                retryBtn.addEventListener('click', handleRetryInit);
            }
        }

        // Hide other loading elements
        const progressBar = loadingDiv?.querySelector('.progress-bar');
        const loadingStages = loadingDiv?.querySelector('.loading-stages');
        const loadingMessage = document.getElementById('loading-message');

        if (progressBar) progressBar.style.display = 'none';
        if (loadingStages) loadingStages.style.display = 'none';
        if (loadingMessage) loadingMessage.style.display = 'none';
    }

    /**
     * Named function for refresh page button handler
     * Prevents closure memory leaks
     */
    function handleRefreshPage() {
        window.location.reload();
    }

    /**
     * Named function for retry button handler
     * Prevents closure memory leaks
     */
    function handleRetryInit() {
        // Prevent concurrent initialization
        if (window._initializationInProgress) {
            logger.debug('Initialization already in progress');
            return;
        }

        // Rate limiting check
        const now = Date.now();
        if (now - lastRetryTimestamp < RETRY_COOLDOWN_MS) {
            logger.debug(`Retry cooldown active. Please wait ${Math.ceil((RETRY_COOLDOWN_MS - (now - lastRetryTimestamp)) / 1000)}s`);
            return;
        }
        lastRetryTimestamp = now;

        // Reset UI elements
        const loadingDiv = document.getElementById('loading');
        const errorContainer = document.getElementById('loading-error');

        if (errorContainer) errorContainer.style.display = 'none';
        const progressBar = loadingDiv?.querySelector('.progress-bar');
        const loadingStages = loadingDiv?.querySelector('.loading-stages');
        const loadingMessage = document.getElementById('loading-message');

        if (progressBar) progressBar.style.display = 'block';
        if (loadingStages) loadingStages.style.display = 'flex';
        if (loadingMessage) loadingMessage.style.display = 'block';

        // Reset all stages to pending
        const stages = document.querySelectorAll('.stage');
        stages.forEach(stage => {
            stage.classList.remove('stage-active', 'stage-complete');
            stage.classList.add('stage-pending');
        });

        // Reset progress bar
        const progressFill = document.getElementById('progress-fill');
        if (progressFill) progressFill.style.width = '0%';

        void initializeApp();
    }

    async function loadRecommendation() {
        const loadingDiv = document.getElementById('loading');
        const contentDiv = document.getElementById('content');

        if (refreshBtn) {
            refreshBtn.disabled = true;
        }

        try {
            // Show analyzing stage before actual Claude AI API call
            updateLoadingStage('analyzing', 80, t('loading.analyzing'));

            const data = await window.cachedFetch('/api/recommendations/today', {
                ttlMinutes: 60,
                headers: {
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            });

            // Complete!
            updateLoadingStage('complete', 100, t('loading.complete'));
            await new Promise(resolve => setTimeout(resolve, COMPLETION_DISPLAY_MS));

            handleRecommendationData(data);

            if (loadingDiv) {
                loadingDiv.style.display = 'none';
            }
            if (contentDiv) {
                contentDiv.style.display = 'flex';

                // Move focus to first heading for keyboard navigation
                const firstHeading = contentDiv.querySelector('h2');
                if (firstHeading) {
                    firstHeading.setAttribute('tabindex', '-1');
                    firstHeading.focus();
                }
            }
        } catch (error) {
            logger.error('Error:', error);
            const message = error instanceof Error ? error.message : t('error.unknown');
            showToast('toast.load_failure', 'error', { error: message });
            throw error; // Re-throw so initializeApp can handle it
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    }

    function handleRecommendationData(data) {
        // Security: Validate all API response data before processing
        const validatedData = validateApiResponse(data);

        latestRecommendation = validatedData;
        latestLoadSummary = validatedData.recent_training_load || {};
        lastSyncIso = validatedData.latest_data_sync || validatedData.generated_at || null;
        latestExtendedSignals = validatedData.extended_signals || null;

        const responseLanguage = normalizeLanguageCode(validatedData.language);
        if (responseLanguage && responseLanguage !== currentLanguage) {
            setLanguage(responseLanguage, { save: true, revalidate: false });
        }

        renderRecommendation();
        updateLoadSummary(latestLoadSummary);
        updateAcwrBadge(latestRecommendation.historical_baselines?.acwr);
        renderReadinessTrend(validatedData.readiness_history);
        updateLastSyncChip(lastSyncIso);
        renderExtendedSignals(latestExtendedSignals);
    }

    function renderRecommendation() {
        if (!latestRecommendation) {
            return;
        }

        const scoreElement = document.getElementById('readiness-score');
        if (scoreElement) {
            scoreElement.textContent = latestRecommendation.readiness_score;

            if (latestRecommendation.readiness_score >= 80) {
                scoreElement.className = 'readiness-score score-green';
            } else if (latestRecommendation.readiness_score >= 60) {
                scoreElement.className = 'readiness-score score-yellow';
            } else if (latestRecommendation.readiness_score >= 40) {
                scoreElement.className = 'readiness-score score-orange';
            } else {
                scoreElement.className = 'readiness-score score-red';
            }
        }

        const confidenceBadge = document.getElementById('confidence-badge');
        if (confidenceBadge) {
            confidenceBadge.textContent = t('confidence.label', {
                value: latestRecommendation.confidence ?? '--',
            });
        }

        const recBadge = document.getElementById('recommendation-badge');
        if (recBadge) {
            const key = `recommendation.${latestRecommendation.recommendation}`;
            const fallback = latestRecommendation.recommendation
                ? latestRecommendation.recommendation.replace(/_/g, ' ').toUpperCase()
                : '--';
            recBadge.textContent = t(key, { _fallback: fallback });

            if (latestRecommendation.recommendation === 'high_intensity') {
                recBadge.className = 'recommendation-badge badge-high';
            } else if (latestRecommendation.recommendation === 'moderate') {
                recBadge.className = 'recommendation-badge badge-moderate';
            } else if (latestRecommendation.recommendation === 'easy') {
                recBadge.className = 'recommendation-badge badge-easy';
            } else {
                recBadge.className = 'recommendation-badge badge-rest';
            }
        }

        const workout = latestRecommendation.suggested_workout || {};
        const workoutType = document.getElementById('workout-type');
        if (workoutType) {
            workoutType.textContent = workout.type ? workout.type.replace(/_/g, ' ').toUpperCase() : '--';
        }
        const workoutDescription = document.getElementById('workout-description');
        if (workoutDescription) {
            workoutDescription.textContent = workout.description ?? '--';
        }
        const workoutDuration = document.getElementById('workout-duration');
        if (workoutDuration) {
            const minutes = workout.target_duration_minutes ?? '--';
            workoutDuration.textContent = t('workout.duration_value', { minutes });
        }
        const workoutIntensity = document.getElementById('workout-intensity');
        if (workoutIntensity) {
            const intensity = workout.intensity ?? '--';
            workoutIntensity.textContent = t('workout.intensity_value', { intensity });
        }
        const workoutRationale = document.getElementById('workout-rationale');
        if (workoutRationale) {
            workoutRationale.textContent = workout.rationale ?? '--';
        }

        renderList('key-factors', latestRecommendation.key_factors, 'factor-item');

        const redFlagsSection = document.getElementById('red-flags-section');
        if (latestRecommendation.red_flags && latestRecommendation.red_flags.length > 0) {
            redFlagsSection?.setAttribute('style', 'display: block;');
            renderList('red-flags', latestRecommendation.red_flags, 'red-flag-item');
        } else {
            if (redFlagsSection) {
                redFlagsSection.style.display = 'none';
            }
        }

        renderList('recovery-tips', latestRecommendation.recovery_tips, 'tip-item');

        const aiReasoning = document.getElementById('ai-reasoning');
        if (aiReasoning) {
            aiReasoning.textContent = latestRecommendation.ai_reasoning ?? '--';
        }

        renderEnhancedMetrics(latestRecommendation.enhanced_metrics);
    }

    function renderList(containerId, items, itemClass) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }

        container.textContent = '';

        if (!items || items.length === 0) {
            const empty = document.createElement('div');
            empty.className = itemClass;
            empty.textContent = t('list.empty');
            container.appendChild(empty);
            return;
        }

        items.forEach((item) => {
            const div = document.createElement('div');
            div.className = itemClass;
            div.textContent = item;
            container.appendChild(div);
        });
    }

    function renderEnhancedMetrics(metrics) {
        const card = document.getElementById('enhanced-metrics-card');
        if (!card) {
            return;
        }

        if (!metrics) {
            card.style.display = 'none';
            return;
        }

        let hasAnyMetric = false;

        const readinessEl = document.getElementById('garmin-readiness');
        if (readinessEl) {
            if (metrics.training_readiness_score !== null && metrics.training_readiness_score !== undefined) {
                readinessEl.textContent = `${metrics.training_readiness_score}/100`;
                hasAnyMetric = true;
            } else {
                readinessEl.textContent = t('enhanced.not_available');
            }
        }

        const vo2El = document.getElementById('vo2-max');
        if (vo2El) {
            if (metrics.vo2_max) {
                vo2El.textContent = `${metrics.vo2_max} ml/kg/min`;
                hasAnyMetric = true;
            } else {
                vo2El.textContent = t('enhanced.not_available');
            }
        }

        const statusEl = document.getElementById('training-status');
        if (statusEl) {
            if (metrics.training_status) {
                statusEl.textContent = metrics.training_status.replace(/_/g, ' ').toUpperCase();
                hasAnyMetric = true;
            } else {
                statusEl.textContent = t('enhanced.not_available');
            }
        }

        const spo2El = document.getElementById('spo2');
        if (spo2El) {
            if (metrics.spo2_avg) {
                const avg = metrics.spo2_avg.toFixed(1);
                const minPart =
                    metrics.spo2_min !== null && metrics.spo2_min !== undefined
                        ? t('enhanced.spo2_min_part', { value: metrics.spo2_min.toFixed(1) })
                        : '';
                spo2El.textContent = t('enhanced.spo2_value', { value: avg, min_part: minPart });
                hasAnyMetric = true;
            } else {
                spo2El.textContent = t('enhanced.not_available');
            }
        }

        const respirationEl = document.getElementById('respiration');
        if (respirationEl) {
            if (metrics.respiration_avg) {
                respirationEl.textContent = t('enhanced.respiration_value', {
                    value: metrics.respiration_avg.toFixed(1),
                });
                hasAnyMetric = true;
            } else {
                respirationEl.textContent = t('enhanced.not_available');
            }
        }

        card.style.display = hasAnyMetric ? 'block' : 'none';
    }

    function renderExtendedSignals(signals) {
        const card = document.getElementById('extended-signals-card');
        if (!card) {
            return;
        }

        if (!signals || Object.keys(signals).length === 0) {
            card.style.display = 'none';
            return;
        }

        let hasData = false;

        const badgesContainer = document.getElementById('extended-signal-badges');
        const loadFocusContainer = document.getElementById('load-focus');
        if (badgesContainer) {
            badgesContainer.textContent = '';
        }
        if (loadFocusContainer) {
            loadFocusContainer.textContent = '';
        }

        const badgeFragments = [];

        const recovery = signals.recovery_time || {};
        if (typeof recovery.hours === 'number') {
            const hoursRaw = Math.max(recovery.hours, 0);
            const formatted = hoursRaw >= 10 ? Math.round(hoursRaw).toString() : (Math.round(hoursRaw * 10) / 10).toString();
            const label = hoursRaw <= 0.5
                ? t('extended.recovery_time_ready')
                : t('extended.recovery_time_value', { hours: formatted });
            badgeFragments.push({ label: t('extended.recovery_time'), value: label });
        }

        const hydration = signals.hydration || {};
        if (typeof hydration.intake_ml === 'number') {
            const intakeLitres = Math.round((hydration.intake_ml / 1000) * 10) / 10;
            const intakeText = intakeLitres.toFixed(intakeLitres % 1 === 0 ? 0 : 1);
            let value;
            if (typeof hydration.goal_ml === 'number' && hydration.goal_ml > 0) {
                const goalLitres = Math.round((hydration.goal_ml / 1000) * 10) / 10;
                const goalText = goalLitres.toFixed(goalLitres % 1 === 0 ? 0 : 1);
                value = t('extended.hydration_value', { intake: intakeText, goal: goalText });
            } else {
                value = t('extended.hydration_value_no_goal', { intake: intakeText });
            }
            badgeFragments.push({ label: t('extended.hydration'), value });
        }
        if (typeof hydration.sweat_loss_ml === 'number' && hydration.sweat_loss_ml > 0) {
            const sweatLitres = Math.round((hydration.sweat_loss_ml / 1000) * 10) / 10;
            const sweatText = sweatLitres.toFixed(sweatLitres % 1 === 0 ? 0 : 1);
            badgeFragments.push({ label: t('extended.hydration'), value: t('extended.hydration_note', { sweat: sweatText }) });
        }

        const focusEntries = Array.isArray(signals.load_focus) ? signals.load_focus : [];
        if (loadFocusContainer) {
            loadFocusContainer.textContent = '';
            if (focusEntries.length > 0) {
                focusEntries.slice(0, 3).forEach((entry) => {
                    const item = document.createElement('div');
                    const focusKey = typeof entry.focus === 'string' ? entry.focus.toLowerCase() : '';
                    const focusLabel = focusKey ? t(`load_focus.${focusKey}`, { _fallback: humanizeLabel(entry.focus) }) : humanizeLabel(entry.focus || t('extended.not_available'));
                    const loadValue = typeof entry.load === 'number' ? Math.round(entry.load) : null;
                    const rangeLow = typeof entry.optimal_low === 'number' ? Math.round(entry.optimal_low) : null;
                    const rangeHigh = typeof entry.optimal_high === 'number' ? Math.round(entry.optimal_high) : null;
                    const statusKey = entry.status ? entry.status.toLowerCase() : null;
                    const statusText = statusKey ? t(`load_focus_status.${statusKey}`, { _fallback: humanizeLabel(entry.status) }) : null;

                    let text = focusLabel;
                    if (loadValue !== null) {
                        text += ` · ${loadValue}`;
                    }
                    if (rangeLow !== null && rangeHigh !== null) {
                        text += ` (opt ${rangeLow}-${rangeHigh})`;
                    }
                    if (statusText) {
                        text += ` · ${statusText}`;
                    }

                    item.textContent = text;
                    loadFocusContainer.appendChild(item);
                });
                hasData = true;
            }
        }

        const acclimation = signals.acclimation || {};
        if (typeof acclimation.heat === 'number' || typeof acclimation.altitude === 'number' || acclimation.status) {
            const heat = typeof acclimation.heat === 'number' ? Math.round(acclimation.heat) : null;
            const altitude = typeof acclimation.altitude === 'number' ? Math.round(acclimation.altitude) : null;

            let value;
            if (heat !== null && altitude !== null) {
                value = t('extended.acclimation_value', { heat, altitude });
            } else if (heat !== null) {
                value = t('extended.acclimation_heat_only', { heat });
            } else if (altitude !== null) {
                value = t('extended.acclimation_alt_only', { altitude });
            }

            if (value) {
                badgeFragments.push({ label: t('extended.acclimation'), value });
            }

            if (acclimation.status) {
                badgeFragments.push({ label: t('extended.acclimation'), value: t('extended.acclimation_status', { status: acclimation.status }) });
            }
        }

        if (badgeFragments.length > 0 && badgesContainer) {
            badgeFragments.forEach((fragment) => {
                const badge = document.createElement('div');
                badge.className = 'extended-badge';
                const labelSpan = document.createElement('strong');
                labelSpan.textContent = fragment.label;
                const valueSpan = document.createElement('span');
                valueSpan.textContent = fragment.value;
                badge.appendChild(labelSpan);
                badge.appendChild(valueSpan);
                badgesContainer.appendChild(badge);
            });
            hasData = true;
        }

        card.style.display = hasData ? 'block' : 'none';
    }

    async function handleManualSync() {
        try {
            await performSync({ triggeredByUser: true });
            await loadRecommendation();
        } catch (error) {
            logger.error('Manual sync failed:', error);
            const message = error instanceof Error ? error.message : t('error.unknown');
            showToast('toast.sync_failure', 'error', { error: message });
        }
    }

    async function handleRefresh() {
        try {
            await loadRecommendation();
            triggerAutoSync(true);
        } catch (error) {
            logger.error('Refresh failed:', error);
            const message = error instanceof Error ? error.message : t('error.unknown');
            showToast('toast.load_failure', 'error', { error: message });
        }
    }

    function triggerAutoSync(triggeredByUser = false) {
        if (syncInProgress) {
            if (triggeredByUser) {
                showToast('status.sync_in_progress', 'info');
            }
            return;
        }

        void (async () => {
            try {
                const success = await performSync({ triggeredByUser });
                if (success) {
                    await loadRecommendation();
                }
            } catch (error) {
                logger.error('Auto sync failed:', error);
                if (triggeredByUser) {
                    const message = error instanceof Error ? error.message : t('error.unknown');
                    showToast('toast.sync_failure', 'error', { error: message });
                }
            }
        })();
    }

    async function performSync({ triggeredByUser = false } = {}) {
        if (syncInProgress) {
            if (triggeredByUser) {
                showToast('status.sync_in_progress', 'info');
            }
            return false;
        }

        syncInProgress = true;

        if (syncBtn) {
            syncBtn.disabled = true;
            syncBtn.textContent = t('status.sync_in_progress');
        }

        const chip = document.getElementById('last-sync-chip');
        const previousChipState =
            chip != null
                ? {
                      text: chip.textContent,
                      className: chip.className,
                  }
                : null;
        if (chip) {
            chip.textContent = t('status.sync_in_progress');
            chip.className = 'status-chip';
        }

        try {
            const response = await fetchWithTimeout('/manual/sync/now', {
                method: 'POST',
                headers: {
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            }, 60000); // 60 second timeout
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            await response.json();

            const nowIso = new Date().toISOString();
            lastSyncIso = nowIso;
            updateLastSyncChip(nowIso);

            if (triggeredByUser) {
                showToast('toast.sync_success', 'success');
            }

            return true;
        } catch (error) {
            logger.error('Sync error:', error);
            const message = error instanceof Error ? error.message : t('error.unknown');
            showToast('toast.sync_failure', 'error', { error: message });
            if (chip) {
                if (previousChipState) {
                    chip.textContent = previousChipState.text;
                    chip.className = previousChipState.className;
                } else {
                    chip.textContent = t('status.last_sync_unknown');
                    chip.className = 'status-chip status-chip--old';
                }
            }
            return false;
        } finally {
            syncInProgress = false;
            if (syncBtn) {
                syncBtn.disabled = false;
                syncBtn.textContent = t('button.sync');
            }
        }
    }

    function renderError(message) {
        const errorDiv = document.getElementById('error');
        if (!errorDiv) {
            return;
        }

        errorDiv.textContent = '';

        const wrapper = document.createElement('div');
        wrapper.className = 'error-card';

        const title = document.createElement('strong');
        title.textContent = t('error.loading_title');
        wrapper.appendChild(title);
        wrapper.appendChild(document.createElement('br'));
        wrapper.appendChild(document.createTextNode(message));

        errorDiv.appendChild(wrapper);
        errorDiv.style.display = 'block';
    }

    function showToast(messageKey, variant = 'info', vars = {}) {
        if (!toastContainer) {
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast toast--${variant}`;
        toast.textContent = t(messageKey, vars);
        toastContainer.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.add('toast--visible');
        });

        setTimeout(() => {
            toast.classList.remove('toast--visible');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    function updateLoadSummary(summary) {
        const activityCount =
            summary && Number.isFinite(summary.activity_count) ? summary.activity_count : '--';
        const distanceValue =
            summary &&
            typeof summary.total_distance_km === 'number' &&
            Number.isFinite(summary.total_distance_km)
                ? summary.total_distance_km
                : '--';
        const durationValue =
            summary &&
            typeof summary.total_duration_min === 'number' &&
            Number.isFinite(summary.total_duration_min)
                ? Math.round(summary.total_duration_min)
                : '--';

        const countEl = document.getElementById('load-summary-count');
        if (countEl) {
            countEl.textContent = t('summary.activities', { count: activityCount });
        }
        const distanceEl = document.getElementById('load-summary-distance');
        if (distanceEl) {
            distanceEl.textContent = t('summary.distance', { distance: distanceValue });
        }
        const durationEl = document.getElementById('load-summary-duration');
        if (durationEl) {
            durationEl.textContent = t('summary.duration', { duration: durationValue });
        }
    }

    function updateAcwrBadge(acwrData) {
        const badge = document.getElementById('acwr-badge');
        if (!badge) {
            return;
        }

        if (!acwrData || acwrData.acwr == null) {
            badge.style.display = 'none';
            badge.textContent = '';
            badge.className = 'metric-chip';
            return;
        }

        const ratio = typeof acwrData.acwr === 'number' ? acwrData.acwr.toFixed(2) : acwrData.acwr;
        const statusKey = (acwrData.status || 'unknown').toLowerCase();
        const translatedStatus = t(`acwr.status.${statusKey}`, {
            _fallback: (acwrData.status || 'unknown').replace(/_/g, ' '),
        });
        const risk = (acwrData.injury_risk || 'unknown').toLowerCase();

        badge.style.display = 'inline-flex';
        badge.textContent = t('status.acwr', { ratio, status: translatedStatus });
        badge.className = 'metric-chip';

        if (risk === 'high') {
            badge.classList.add('metric-chip--danger');
        } else if (risk === 'moderate') {
            badge.classList.add('metric-chip--caution');
        } else {
            badge.classList.add('metric-chip--good');
        }
    }

    function renderReadinessTrend(history) {
        const container = document.getElementById('readiness-trend');
        if (!container) {
            return;
        }

        container.replaceChildren(); // Modern, safe alternative to innerHTML = ''

        if (!history || history.length < 2) {
            const empty = document.createElement('span');
            empty.className = 'trend-empty';
            empty.textContent = t('trend.need_more');
            container.appendChild(empty);
            return;
        }

        const width = 160;
        const height = 50;
        const scores = history.map((item) => item.score);
        const max = Math.max(...scores);
        const min = Math.min(...scores);
        const range = max - min || 1;
        const step = width / (scores.length - 1 || 1);

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        svg.setAttribute('preserveAspectRatio', 'none');
        svg.classList.add('trend-sparkline');

        const points = scores
            .map((score, index) => {
                const x = index * step;
                const normalized = (score - min) / range;
                const y = height - normalized * (height - 10) - 5;
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(' ');

        const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        polyline.setAttribute('points', points);
        polyline.setAttribute('fill', 'none');
        polyline.setAttribute('stroke', 'var(--accent-primary)');
        polyline.setAttribute('stroke-width', '3');
        polyline.setAttribute('stroke-linecap', 'round');
        polyline.setAttribute('stroke-linejoin', 'round');

        const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        gradient.setAttribute('id', 'trendGradient');
        gradient.setAttribute('x1', '0');
        gradient.setAttribute('x2', '0');
        gradient.setAttribute('y1', '0');
        gradient.setAttribute('y2', '1');

        const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop1.setAttribute('offset', '0%');
        stop1.setAttribute('stop-color', 'var(--accent-primary)');
        stop1.setAttribute('stop-opacity', '0.35');

        const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop2.setAttribute('offset', '100%');
        stop2.setAttribute('stop-color', 'var(--accent-primary)');
        stop2.setAttribute('stop-opacity', '0');

        gradient.appendChild(stop1);
        gradient.appendChild(stop2);

        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.appendChild(gradient);

        const area = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        area.setAttribute('points', `0,${height} ${points} ${width},${height}`);
        area.setAttribute('fill', 'url(#trendGradient)');
        area.setAttribute('stroke', 'none');

        svg.appendChild(defs);
        svg.appendChild(area);
        svg.appendChild(polyline);

        container.appendChild(svg);

        const labels = document.createElement('div');
        labels.className = 'trend-labels';

        // Security: Use textContent instead of innerHTML to prevent XSS
        const firstScoreSpan = document.createElement('span');
        firstScoreSpan.textContent = String(history[0].score);
        const lastScoreSpan = document.createElement('span');
        lastScoreSpan.textContent = String(history[history.length - 1].score);

        labels.appendChild(firstScoreSpan);
        labels.appendChild(lastScoreSpan);
        container.appendChild(labels);
    }

    function updateLastSyncChip(isoString) {
        const chip = document.getElementById('last-sync-chip');
        if (!chip) {
            return;
        }

        if (!isoString) {
            chip.textContent = t('status.last_sync_unknown');
            chip.className = 'status-chip status-chip--old';
            return;
        }

        const parsed = new Date(isoString);
        if (Number.isNaN(parsed.getTime())) {
            chip.textContent = t('status.last_sync_unknown');
            chip.className = 'status-chip status-chip--old';
            return;
        }

        const now = new Date();
        const diffMinutes = Math.floor((now.getTime() - parsed.getTime()) / 60000);

        let label;
        if (diffMinutes < 1) {
            label = t('status.just_now');
        } else if (diffMinutes < 60) {
            label = t('status.minutes_ago', { minutes: diffMinutes });
        } else if (diffMinutes < 1440) {
            const hours = Math.floor(diffMinutes / 60);
            label = t('status.hours_ago', {
                hours,
                plural: hours > 1 ? 's' : '',
            });
        } else {
            const days = Math.floor(diffMinutes / 1440);
            label = t('status.days_ago', {
                days,
                plural: currentLanguage === 'de' ? (days > 1 ? 'en' : '') : days > 1 ? 's' : '',
            });
        }

        chip.textContent = t('status.last_sync', { label });
        chip.className = 'status-chip';

        if (diffMinutes <= 90) {
            chip.classList.add('status-chip--fresh');
        } else if (diffMinutes <= 240) {
            chip.classList.add('status-chip--stale');
        } else {
            chip.classList.add('status-chip--old');
        }
    }

    function applyStoredTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        const isDark = stored === 'dark';
        document.body.classList.toggle('dark-theme', isDark);
        updateThemeToggleLabel(isDark);
    }

    function toggleTheme() {
        const isDark = document.body.classList.toggle('dark-theme');
        localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
        updateThemeToggleLabel(isDark);
    }

    function setLanguage(lang, { save = true, revalidate = false } = {}) {
        if (!translations[lang]) {
            lang = FALLBACK_LANGUAGE;
        }
        currentLanguage = lang;

        if (save) {
            localStorage.setItem(LANGUAGE_KEY, currentLanguage);
        }

        document.documentElement.lang = currentLanguage;

        applyStaticTranslations();
        updateDateDisplay();
        updateThemeToggleLabel(document.body.classList.contains('dark-theme'));
        updateLoadSummary(latestLoadSummary);
        updateAcwrBadge(latestRecommendation?.historical_baselines?.acwr);
        renderReadinessTrend(latestRecommendation?.readiness_history);
        updateLastSyncChip(lastSyncIso);
        if (latestRecommendation) {
            renderRecommendation();
        }
        renderExtendedSignals(latestExtendedSignals);

        if (revalidate) {
            void loadRecommendation();
        }
    }

    function applyStaticTranslations() {
        document.title = t('meta.title');

        document.querySelectorAll('[data-i18n]').forEach((el) => {
            const key = el.dataset.i18n;
            if (!key) {
                return;
            }
            if (el.id === 'language-toggle') {
                return;
            }
            el.textContent = t(key);
        });

        updateActionButtons();
    }

    function updateActionButtons() {
        if (languageToggle) {
            const labelKey = `language.label.${currentLanguage}`;
            languageToggle.textContent = t(labelKey);
            languageToggle.setAttribute('aria-label', t('language.aria'));
        }
        if (syncBtn) {
            syncBtn.textContent = t('button.sync');
        }
        if (refreshBtn) {
            refreshBtn.textContent = t('button.refresh');
        }
    }

    function updateThemeToggleLabel(isDark) {
        if (!themeToggle) {
            return;
        }
        themeToggle.textContent = isDark ? t('theme.light') : t('theme.dark');
    }

    function updateDateDisplay() {
        if (!dateElement) {
            return;
        }
        const locale = dateLocales[currentLanguage] ?? dateLocales[FALLBACK_LANGUAGE];
        const today = new Date();
        dateElement.textContent = today.toLocaleDateString(locale, {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        });
    }

    function humanizeLabel(value) {
        if (value == null) {
            return '';
        }
        return value
            .toString()
            .toLowerCase()
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    function t(key, vars = {}) {
        const langDict = translations[currentLanguage] ?? {};
        const fallbackDict = translations[FALLBACK_LANGUAGE] ?? {};
        let template = langDict[key];
        if (template === undefined) {
            template = fallbackDict[key];
        }
        if (template === undefined) {
            template = vars._fallback ?? key;
        }

        return template.replace(/\{(\w+)\}/g, (match, varName) => {
            if (vars[varName] === undefined) {
                return '';
            }
            return String(vars[varName]);
        });
    }

    /**
     * Load and display training alerts
     */
    async function loadAlerts() {
        const alertsSection = document.getElementById('alerts-section');
        const alertsList = document.getElementById('alerts-list');

        if (!alertsSection || !alertsList) {
            logger.debug('Alerts container not found');
            return;
        }

        try {
            const response = await fetchWithTimeout('/api/alerts/active?days=7', {
                headers: {
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            }, 10000); // 10 second timeout

            if (!response.ok) {
                throw new Error(`Failed to fetch alerts: ${response.status}`);
            }

            const data = await response.json();
            const alerts = data.alerts || [];

            if (alerts.length === 0) {
                alertsSection.style.display = 'none';
            } else {
                displayAlerts(alerts);
                alertsSection.style.display = 'block';
            }
        } catch (error) {
            logger.error('Error loading alerts:', error);
            // Hide alerts section on error (graceful degradation)
            alertsSection.style.display = 'none';
        }
    }

    /**
     * Display alerts in the UI
     * @param {Array} alerts - Array of alert objects
     */
    function displayAlerts(alerts) {
        const alertsList = document.getElementById('alerts-list');
        if (!alertsList) {
            return;
        }

        // Clear existing content
        alertsList.textContent = '';

        // Create alert cards
        alerts.forEach(alert => {
            const cardHtml = createAlertCard(alert);
            alertsList.insertAdjacentHTML('beforeend', cardHtml);
        });
    }

    /**
     * Create HTML for a single alert card
     * @param {Object} alert - Alert object
     * @returns {string} HTML string
     */
    function createAlertCard(alert) {
        const severityIcon = alert.severity === 'critical' ? '⚠️' : '⚡';
        const severityClass = alert.severity === 'critical' ? 'alert-critical' : 'alert-warning';

        // Format date
        const alertDate = new Date(alert.detected_at);
        const formattedDate = alertDate.toLocaleDateString(dateLocales[currentLanguage] || dateLocales[FALLBACK_LANGUAGE], {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        // Format trigger metrics as readable text
        let metricsHtml = '';
        if (alert.trigger_metrics && typeof alert.trigger_metrics === 'object') {
            const metricsEntries = Object.entries(alert.trigger_metrics)
                .map(([key, value]) => {
                    const readableKey = humanizeLabel(key);
                    const formattedValue = typeof value === 'number' ? value.toFixed(2) : String(value);
                    return `${readableKey}: ${formattedValue}`;
                })
                .join(' | ');
            metricsHtml = `<div class="alert-metrics">${metricsEntries}</div>`;
        }

        // Use global escapeHtml function for XSS protection
        const title = escapeHtml(alert.title || 'Alert');
        const message = escapeHtml(alert.message || '');
        const recommendation = alert.recommendation ? `<p class="alert-recommendation"><strong>Recommendation:</strong> ${escapeHtml(alert.recommendation)}</p>` : '';

        return `
            <div class="alert-card ${severityClass}" data-alert-id="${alert.id}">
                <div class="alert-header">
                    <span class="alert-badge">${severityIcon}</span>
                    <h3 class="alert-title">${title}</h3>
                    <span class="alert-date">${formattedDate}</span>
                </div>
                <div class="alert-body">
                    <p class="alert-message">${message}</p>
                    ${metricsHtml}
                    ${recommendation}
                </div>
                <div class="alert-actions">
                    <button class="alert-acknowledge-btn" onclick="acknowledgeAlert(${alert.id})">
                        Acknowledge
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Acknowledge an alert
     * @param {number} alertId - Alert ID
     */
    window.acknowledgeAlert = async function(alertId) {
        try {
            const response = await fetchWithTimeout(`/api/alerts/${alertId}/acknowledge`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            }, 10000);

            if (!response.ok) {
                throw new Error(`Failed to acknowledge alert: ${response.status}`);
            }

            // Show success toast
            showToast('Alert acknowledged', 'success');

            // Reload alerts to update UI
            await loadAlerts();
        } catch (error) {
            logger.error('Error acknowledging alert:', error);
            const message = error instanceof Error ? error.message : 'Unknown error';
            showToast(`Failed to acknowledge alert: ${message}`, 'error');
        }
    };
});
