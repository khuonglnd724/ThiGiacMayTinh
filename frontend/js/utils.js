/**
 * Utility Functions
 */

/**
 * Format bytes to readable size
 * @param {number} bytes - Bytes
 * @param {number} decimals - Decimal places
 * @returns {string} Formatted size (e.g., "2.5 MB")
 */
function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Format date to readable string
 * @param {string|Date} date - Date object or ISO string
 * @returns {string} Formatted date (e.g., "Jan 15, 2024 10:30 AM")
 */
function formatDate(date) {
  const d = new Date(date);
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Get verdict badge class
 * @param {string} verdict - PASS|FLAG|REJECT
 * @returns {string} CSS class name
 */
function getVerdictClass(verdict) {
  const verdictMap = {
    PASS: 'badge-success',
    FLAG: 'badge-warning',
    REJECT: 'badge-danger',
  };
  return verdictMap[verdict] || 'badge-secondary';
}

/**
 * Get severity badge class
 * @param {string} severity - Low|Medium|High|Critical
 * @returns {string} CSS class name
 */
function getSeverityClass(severity) {
  const severityMap = {
    Low: 'badge-info',
    Medium: 'badge-warning',
    High: 'badge-danger',
    Critical: 'badge-danger',
  };
  return severityMap[severity] || 'badge-secondary';
}

/**
 * Calculate percentage
 * @param {number} value - Value
 * @param {number} total - Total
 * @returns {number} Percentage (0-100)
 */
function percentage(value, total) {
  return total === 0 ? 0 : Math.round((value / total) * 100);
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
}

/**
 * Throttle function
 * @param {Function} func - Function to throttle
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(func, delay) {
  let lastCall = 0;
  return function (...args) {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      func(...args);
    }
  };
}

/**
 * Deep clone object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * LocalStorage wrapper
 */
const Storage = {
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
    }
  },

  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      console.error('Failed to read from localStorage:', error);
      return defaultValue;
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error('Failed to remove from localStorage:', error);
    }
  },

  clear() {
    try {
      localStorage.clear();
    } catch (error) {
      console.error('Failed to clear localStorage:', error);
    }
  },
};

/**
 * Show toast notification
 * @param {string} message - Message text
 * @param {string} type - Type (success|error|warning|info)
 * @param {number} duration - Duration in milliseconds
 */
function showToast(message, type = 'info', duration = 3000) {
  const toastContainer = document.getElementById('toast-container') || createToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast alert alert-${type === 'error' ? 'danger' : type}`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <div class="toast-body">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
  `;

  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, duration);
}

/**
 * Create toast container if not exists
 */
function createToastContainer() {
  const container = document.createElement('div');
  container.id = 'toast-container';
  container.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
  `;
  document.body.appendChild(container);
  return container;
}

/**
 * Show loading spinner
 * @param {string} message - Message text
 * @returns {Function} Function to hide spinner
 */
function showSpinner(message = 'Loading...') {
  const overlay = document.createElement('div');
  overlay.id = 'loading-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9998;
  `;

  overlay.innerHTML = `
    <div class="spinner-container text-center">
      <div class="spinner-border text-primary mb-3" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-white">${message}</p>
    </div>
  `;

  document.body.appendChild(overlay);

  return () => overlay.remove();
}

/**
 * Validate file type
 * @param {File} file - File object
 * @param {string[]} allowedTypes - Allowed MIME types
 * @returns {boolean} Is file valid
 */
function isValidFileType(file, allowedTypes) {
  return allowedTypes.includes(file.type);
}

/**
 * Validate file size
 * @param {File} file - File object
 * @param {number} maxSize - Max size in bytes
 * @returns {boolean} Is file valid
 */
function isValidFileSize(file, maxSize) {
  return file.size <= maxSize;
}

/**
 * Convert file to base64
 * @param {File} file - File object
 * @returns {Promise<string>} Base64 string
 */
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Download file
 * @param {string} url - File URL
 * @param {string} filename - Filename
 */
function downloadFile(url, filename = 'download') {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
}
