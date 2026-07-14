/**
 * Điểm Vào Chính của Ứng Dụng
 */

// Trạng thái ứng dụng
const appState = {
  isProcessing: false,
  currentInspection: null,
  theme: Storage.get('theme', 'light'),
};

/**
 * Khởi tạo ứng dụng
 */
async function initApp() {
  console.log('Đang khởi tạo ứng dụng...');

  // Kiểm tra kết nối backend
  try {
    await apiClient.healthCheck();
    console.log('✓ Đã kết nối backend');
  } catch (error) {
    console.error('✗ Kết nối backend thất bại:', error);
    showToast('Cảnh báo: Không thể kết nối backend. Vui lòng khởi động máy chủ backend.', 'warning');
  }

  // Khởi tạo quản lý giao diện
  uiManager.init();

  // Tải trang ban đầu (dashboard)
  uiManager.navigateToPage('dashboard');

  // Thiết lập chủ đề
  const savedTheme = Storage.get('theme', 'light');
  applyTheme(savedTheme);

  console.log('✓ Ứng dụng đã khởi tạo');
}

/**
 * Áp dụng chủ đề
 * @param {string} theme - Tên chủ đề (light|dark)
 */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-bs-theme', theme);
  appState.theme = theme;
  Storage.set('theme', theme);
}

/**
 * Chuyển đổi chủ đề
 */
function toggleTheme() {
  const newTheme = appState.theme === 'light' ? 'dark' : 'light';
  applyTheme(newTheme);
}

/**
 * Xử lý tác vụ bất đồng bộ với trạng thái tải
 * @param {Function} fn - Hàm bất đồng bộ cần thực thi
 * @param {string} message - Thông báo đang tải
 */
async function withLoading(fn, message = 'Đang xử lý...') {
  if (appState.isProcessing) {
    showToast('Một tác vụ khác đang được xử lý', 'warning');
    return;
  }

  appState.isProcessing = true;
  const hideSpinner = showSpinner(message);

  try {
    return await fn();
  } catch (error) {
    console.error('Lỗi:', error);
    showToast(`Lỗi: ${error.message}`, 'error');
  } finally {
    appState.isProcessing = false;
    hideSpinner();
  }
}

/**
 * Phím tắt toàn cục
 */
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl+U: Tới trang tải lên
    if (e.ctrlKey && e.key === 'u') {
      e.preventDefault();
      uiManager.navigateToPage('upload');
    }

    // Ctrl+H: Tới trang lịch sử
    if (e.ctrlKey && e.key === 'h') {
      e.preventDefault();
      uiManager.navigateToPage('history');
    }

    // Ctrl+D: Tới trang tổng quan
    if (e.ctrlKey && e.key === 'd') {
      e.preventDefault();
      uiManager.navigateToPage('dashboard');
    }

    // Ctrl+T: Chuyển đổi chủ đề
    if (e.ctrlKey && e.key === 't') {
      e.preventDefault();
      toggleTheme();
    }
  });
}

/**
 * Xuất các hàm toàn cục
 */
window.appState = appState;
window.appInit = initApp;
window.applyTheme = applyTheme;
window.toggleTheme = toggleTheme;
window.withLoading = withLoading;

/**
 * DOMContentLoaded: Khởi động ứng dụng
 */
document.addEventListener('DOMContentLoaded', () => {
  initApp();
  setupKeyboardShortcuts();
});