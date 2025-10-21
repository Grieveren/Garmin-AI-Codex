/**
 * Data Prefetching Orchestrator
 * Intelligently prefetches data for faster page navigation
 */
class DataPrefetcher {
    constructor() {
        this.prefetchQueue = [];
        this.isPrefetching = false;
    }

    /**
     * Prefetch all data needed for site navigation
     */
    async prefetchAllPages() {
        if (this.isPrefetching) {
            if (window.DEBUG_MODE) console.log('Prefetch already in progress, skipping...');
            return;
        }

        this.isPrefetching = true;
        if (window.DEBUG_MODE) console.log('Starting data prefetch...');

        const prefetchTasks = [
            // Today's recommendation (if not already loaded)
            this._prefetch('/api/recommendations/today', { ttlMinutes: 60 }),

            // Analytics endpoints
            this._prefetch('/api/analytics/readiness-trend', {
                params: { days: 30 },
                ttlMinutes: 60
            }),
            this._prefetch('/api/analytics/training-load', {
                params: { days: 90 },
                ttlMinutes: 60
            }),
            this._prefetch('/api/analytics/sleep-performance', {
                params: { days: 30 },
                ttlMinutes: 60
            }),
            this._prefetch('/api/analytics/activity-breakdown', {
                params: { days: 30 },
                ttlMinutes: 60
            }),
            this._prefetch('/api/analytics/recovery-correlation', {
                params: { metric: 'hrv', days: 30 },
                ttlMinutes: 60
            }),

            // Training plan (if exists)
            this._prefetch('/api/training/plans/current', {
                ttlMinutes: 30,
                ignoreErrors: true // May not exist
            })
        ];

        // Execute all prefetch tasks in parallel
        const results = await Promise.allSettled(prefetchTasks);

        const successful = results.filter(r => r.status === 'fulfilled').length;
        const failed = results.filter(r => r.status === 'rejected').length;

        if (window.DEBUG_MODE) console.log(`Data prefetch complete! (${successful} successful, ${failed} failed)`);
        this.isPrefetching = false;
    }

    /**
     * Prefetch specific endpoint
     */
    async _prefetch(url, options = {}) {
        try {
            await window.cachedFetch(url, {
                ...options,
                forceRefresh: false // Use cache if available
            });
        } catch (error) {
            if (!options.ignoreErrors) {
                console.warn(`Prefetch failed for ${url}:`, error);
            }
        }
    }

    /**
     * Trigger prefetch after page load (low priority)
     */
    initPrefetch() {
        // Wait for page to fully load and be idle
        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => this.prefetchAllPages(), { timeout: 2000 });
        } else {
            // Fallback for browsers without requestIdleCallback
            setTimeout(() => this.prefetchAllPages(), 1000);
        }
    }

    /**
     * Prefetch specific page data on demand
     */
    async prefetchPage(page) {
        if (window.DEBUG_MODE) console.log(`Prefetching data for: ${page}`);

        switch (page) {
            case 'insights':
                await Promise.allSettled([
                    this._prefetch('/api/analytics/readiness-trend', {
                        params: { days: 30 },
                        ttlMinutes: 60
                    }),
                    this._prefetch('/api/analytics/training-load', {
                        params: { days: 90 },
                        ttlMinutes: 60
                    }),
                    this._prefetch('/api/analytics/sleep-performance', {
                        params: { days: 30 },
                        ttlMinutes: 60
                    }),
                    this._prefetch('/api/analytics/activity-breakdown', {
                        params: { days: 30 },
                        ttlMinutes: 60
                    })
                ]);
                break;

            case 'training_plan':
                await this._prefetch('/api/training/plans/current', {
                    ttlMinutes: 30,
                    ignoreErrors: true
                });
                break;

            case 'dashboard':
                await this._prefetch('/api/recommendations/today', {
                    ttlMinutes: 60
                });
                break;

            default:
                console.warn(`Unknown page: ${page}`);
        }
    }

    /**
     * Get prefetch statistics
     */
    getStats() {
        return {
            isPrefetching: this.isPrefetching,
            queueLength: this.prefetchQueue.length,
            cacheStats: window.dataCache.getStats()
        };
    }
}

// Global prefetcher instance
window.dataPrefetcher = new DataPrefetcher();
