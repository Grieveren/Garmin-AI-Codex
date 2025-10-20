// Shared Navigation and Base JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const THEME_KEY = 'dashboard-theme';
    const LANGUAGE_KEY = 'dashboard-language';

    // Mobile menu toggle
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const navContent = document.getElementById('nav-content');

    if (mobileMenuToggle && navContent) {
        mobileMenuToggle.addEventListener('click', () => {
            const isOpen = navContent.classList.toggle('open');
            mobileMenuToggle.setAttribute('aria-expanded', isOpen.toString());
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', (event) => {
            if (!event.target.closest('.navbar-container')) {
                navContent.classList.remove('open');
                mobileMenuToggle.setAttribute('aria-expanded', 'false');
            }
        });

        // Close mobile menu when clicking a nav link
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                navContent.classList.remove('open');
                mobileMenuToggle.setAttribute('aria-expanded', 'false');
            });
        });

        // Close mobile menu on escape key
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && navContent.classList.contains('open')) {
                navContent.classList.remove('open');
                mobileMenuToggle.setAttribute('aria-expanded', 'false');
                mobileMenuToggle.focus();
            }
        });
    }

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        // Apply stored theme on page load
        applyStoredTheme();

        themeToggle.addEventListener('click', () => {
            toggleTheme();
        });
    }

    // Language toggle
    const languageToggle = document.getElementById('language-toggle');
    if (languageToggle) {
        // Set initial language button text
        const currentLanguage = localStorage.getItem(LANGUAGE_KEY) || 'en';
        updateLanguageButton(currentLanguage);

        languageToggle.addEventListener('click', () => {
            const currentLanguage = localStorage.getItem(LANGUAGE_KEY) || 'en';
            const newLanguage = currentLanguage === 'en' ? 'de' : 'en';
            localStorage.setItem(LANGUAGE_KEY, newLanguage);
            updateLanguageButton(newLanguage);

            // Reload page to apply language change
            window.location.reload();
        });
    }

    // Active link highlighting
    highlightActiveLink();

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

    function updateThemeToggleLabel(isDark) {
        if (!themeToggle) return;

        if (isDark) {
            themeToggle.textContent = '☀️ Light';
            themeToggle.setAttribute('aria-label', 'Switch to light mode');
        } else {
            themeToggle.textContent = '🌙 Dark';
            themeToggle.setAttribute('aria-label', 'Switch to dark mode');
        }
    }

    function updateLanguageButton(language) {
        if (!languageToggle) return;

        if (language === 'de') {
            languageToggle.textContent = '🇩🇪 DE';
            languageToggle.setAttribute('aria-label', 'Switch to English');
        } else {
            languageToggle.textContent = '🇬🇧 EN';
            languageToggle.setAttribute('aria-label', 'Switch to German');
        }
    }

    function highlightActiveLink() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.nav-link');

        navLinks.forEach(link => {
            const linkPath = new URL(link.href).pathname;

            // Remove active class from all links
            link.classList.remove('active');

            // Add active class to matching link
            if (linkPath === currentPath) {
                link.classList.add('active');
            } else if (currentPath === '/' && linkPath === '/') {
                link.classList.add('active');
            }
        });
    }
});
