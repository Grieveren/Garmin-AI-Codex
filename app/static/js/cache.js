/**
 * Data Cache Manager with TTL Support
 * Provides intelligent caching with memory + localStorage backup
 */
class DataCache {
    constructor() {
        this.cache = new Map();
        this.TTL_MINUTES = 5; // 5 minute default TTL
    }

    set(key, data, ttlMinutes = this.TTL_MINUTES) {
        const expiry = Date.now() + (ttlMinutes * 60 * 1000);
        this.cache.set(key, {
            data: data,
            expiry: expiry,
            timestamp: Date.now()
        });

        // Also save to localStorage for persistence across sessions
        this._saveToLocalStorage(key, data, expiry);
    }

    get(key) {
        // Check memory cache first
        let cached = this.cache.get(key);

        // Fallback to localStorage
        if (!cached) {
            cached = this._loadFromLocalStorage(key);
            if (cached) {
                this.cache.set(key, cached);
            }
        }

        if (!cached) return null;

        // Check if expired
        if (Date.now() > cached.expiry) {
            this.delete(key);
            return null;
        }

        return cached.data;
    }

    delete(key) {
        this.cache.delete(key);
        localStorage.removeItem(`cache_${key}`);
    }

    clear() {
        this.cache.clear();
        // Clear all cache_ prefixed items
        Object.keys(localStorage)
            .filter(k => k.startsWith('cache_'))
            .forEach(k => localStorage.removeItem(k));
    }

    // Helper to generate cache keys with URL encoding to prevent collisions
    static generateKey(endpoint, params = {}, headers = {}) {
        // Security: URL encode both keys and values to prevent cache poisoning
        const paramString = Object.keys(params)
            .sort()
            .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
            .join('&');

        // Include language header in cache key to prevent language-specific cache collisions
        // IMPORTANT: Only Accept-Language affects API responses in this application
        // If adding authentication (Authorization header) or other request-varying headers,
        // update this cache key generation to include those headers
        const langHeader = headers['Accept-Language'] || '';
        const langPart = langHeader ? `&lang=${encodeURIComponent(langHeader)}` : '';

        return `${endpoint}${paramString ? '?' + paramString : ''}${langPart}`;
    }

    _saveToLocalStorage(key, data, expiry) {
        try {
            localStorage.setItem(`cache_${key}`, JSON.stringify({
                data: data,
                expiry: expiry,
                timestamp: Date.now()
            }));
        } catch (e) {
            console.warn('localStorage quota exceeded, clearing old cache');
            this._clearOldestCache();
            // Retry save after clearing cache
            try {
                localStorage.setItem(`cache_${key}`, JSON.stringify({
                    data: data,
                    expiry: expiry,
                    timestamp: Date.now()
                }));
            } catch (retryError) {
                console.error('Failed to save to localStorage even after clearing cache', retryError);
            }
        }
    }

    _loadFromLocalStorage(key) {
        try {
            const item = localStorage.getItem(`cache_${key}`);
            if (!item) return null;
            return JSON.parse(item);
        } catch (e) {
            console.error('Failed to load from localStorage', e);
            return null;
        }
    }

    _clearOldestCache() {
        // Clear oldest 50% of cache entries for better quota recovery
        const cacheKeys = Object.keys(localStorage)
            .filter(k => k.startsWith('cache_'))
            .map(k => {
                try {
                    const data = JSON.parse(localStorage.getItem(k));
                    return { key: k, timestamp: data.timestamp };
                } catch (e) {
                    return { key: k, timestamp: 0 };
                }
            })
            .sort((a, b) => a.timestamp - b.timestamp);

        const toClear = Math.max(1, Math.floor(cacheKeys.length * 0.5));
        cacheKeys.slice(0, toClear).forEach(item => {
            localStorage.removeItem(item.key);
        });
    }

    // Get cache statistics
    getStats() {
        const memoryKeys = Array.from(this.cache.keys());
        const storageKeys = Object.keys(localStorage)
            .filter(k => k.startsWith('cache_'));

        return {
            memoryEntries: memoryKeys.length,
            storageEntries: storageKeys.length,
            totalSize: storageKeys.reduce((sum, key) => {
                return sum + (localStorage.getItem(key)?.length || 0);
            }, 0)
        };
    }
}

/**
 * Fetch wrapper with automatic caching
 */
async function cachedFetch(url, options = {}) {
    // Security: Include headers in cache key to prevent language-specific collisions
    const cacheKey = DataCache.generateKey(url, options.params || {}, options.headers || {});

    // Check cache first (unless force refresh)
    if (!options.forceRefresh) {
        const cached = window.dataCache.get(cacheKey);
        if (cached) {
            return cached;
        }
    }

    // Add query params to URL
    const fullUrl = new URL(url, window.location.origin);
    if (options.params) {
        Object.keys(options.params).forEach(key => {
            fullUrl.searchParams.append(key, options.params[key]);
        });
    }

    // Fetch from API
    const response = await fetch(fullUrl, {
        method: options.method || 'GET',
        headers: options.headers || {},
        body: options.body
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Cache the response (with custom TTL if provided)
    window.dataCache.set(cacheKey, data, options.ttlMinutes);

    return data;
}

/**
 * UI State Manager
 * Persists UI state across page navigation
 */
class UIState {
    static save(page, state) {
        localStorage.setItem(`ui_state_${page}`, JSON.stringify(state));
    }

    static load(page) {
        try {
            const state = localStorage.getItem(`ui_state_${page}`);
            return state ? JSON.parse(state) : null;
        } catch (e) {
            console.error('Failed to load UI state', e);
            return null;
        }
    }

    static clear(page) {
        if (page) {
            localStorage.removeItem(`ui_state_${page}`);
        } else {
            // Clear all UI state
            Object.keys(localStorage)
                .filter(k => k.startsWith('ui_state_'))
                .forEach(k => localStorage.removeItem(k));
        }
    }
}

// Global instances
window.dataCache = new DataCache();
window.cachedFetch = cachedFetch;
window.UIState = UIState;
