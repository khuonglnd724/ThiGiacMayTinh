/**
 * Main Application Entry Point
 */

// Application state
const appState = {
  isProcessing: false,
  currentInspection: null,
  theme: Storage.get('theme', 'light'),
};

/**
 * Initialize application
 */
async function initApp() {
  console.log('Initializing application...');

  // Check backend connectivity
  try {
    await apiClient.healthCheck();
    console.log('✓ Backend connected');
  } catch (error) {
    console.error('✗ Backend connection failed:', error);
    showToast('Warning: Cannot connect to backend. Please start the backend server.', 'warning');
  }

  // Initialize UI manager
  uiManager.init();

  // Load initial page (dashboard)
  uiManager.navigateToPage('dashboard');

  // Setup theme
  const savedTheme = Storage.get('theme', 'light');
  applyTheme(savedTheme);

  console.log('✓ Application initialized');
}

/**
 * Apply theme
 * @param {string} theme - Theme name (light|dark)
 */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-bs-theme', theme);
  appState.theme = theme;
  Storage.set('theme', theme);
}

/**
 * Toggle theme
 */
function toggleTheme() {
  const newTheme = appState.theme === 'light' ? 'dark' : 'light';
  applyTheme(newTheme);
}

/**
 * Handle async operations with loading state
 * @param {Function} fn - Async function to execute
 * @param {string} message - Loading message
 */
async function withLoading(fn, message = 'Processing...') {
  if (appState.isProcessing) {
    showToast('Another operation is in progress', 'warning');
    return;
  }

  appState.isProcessing = true;
  const hideSpinner = showSpinner(message);

  try {
    return await fn();
  } catch (error) {
    console.error('Error:', error);
    showToast(`Error: ${error.message}`, 'error');
  } finally {
    appState.isProcessing = false;
    hideSpinner();
  }
}

/**
 * Global keyboard shortcuts
 */
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl+U: Go to upload
    if (e.ctrlKey && e.key === 'u') {
      e.preventDefault();
      uiManager.navigateToPage('upload');
    }

    // Ctrl+H: Go to history
    if (e.ctrlKey && e.key === 'h') {
      e.preventDefault();
      uiManager.navigateToPage('history');
    }

    // Ctrl+D: Go to dashboard
    if (e.ctrlKey && e.key === 'd') {
      e.preventDefault();
      uiManager.navigateToPage('dashboard');
    }

    // Ctrl+T: Toggle theme
    if (e.ctrlKey && e.key === 't') {
      e.preventDefault();
      toggleTheme();
    }
  });
}

/**
 * Export global functions
 */
window.appState = appState;
window.appInit = initApp;
window.applyTheme = applyTheme;
window.toggleTheme = toggleTheme;
window.withLoading = withLoading;

/**
 * DOMContentLoaded: Start app
 */
document.addEventListener('DOMContentLoaded', () => {
  initApp();
  setupKeyboardShortcuts();
});
