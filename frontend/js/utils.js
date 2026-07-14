/**
 * Các Hàm Tiện Ích
 */

/**
 * Định dạng byte sang kích thước có thể đọc được
 * @param {number} bytes - Byte
 * @param {number} decimals - Số chữ số thập phân
 * @returns {string} Kích thước đã định dạng (ví dụ: "2.5 MB")
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
 * Định dạng ngày thành chuỗi có thể đọc được
 * @param {string|Date} date - Đối tượng ngày hoặc chuỗi ISO
 * @returns {string} Ngày đã định dạng
 */
function formatDate(date) {
  const d = new Date(date);
  return d.toLocaleString('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Lấy lớp CSS cho huy hiệu kết luận
 * @param {string} verdict - PASS|FLAG|REJECT
 * @returns {string} Tên lớp CSS
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
 * Lấy lớp CSS cho huy hiệu mức độ nghiêm trọng
 * @param {string} severity - Low|Medium|High|Critical
 * @returns {string} Tên lớp CSS
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
 * Tính phần trăm
 * @param {number} value - Giá trị
 * @param {number} total - Tổng
 * @returns {number} Phần trăm (0-100)
 */
function percentage(value, total) {
  return total === 0 ? 0 : Math.round((value / total) * 100);
}

/**
 * Hàm debounce
 * @param {Function} func - Hàm cần debounce
 * @param {number} delay - Độ trễ tính bằng mili giây
 * @returns {Function} Hàm đã debounce
 */
function debounce(func, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
}

/**
 * Hàm throttle
 * @param {Function} func - Hàm cần throttle
 * @param {number} delay - Độ trễ tính bằng mili giây
 * @returns {Function} Hàm đã throttle
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
 * Sao chép sâu đối tượng
 * @param {Object} obj - Đối tượng cần sao chép
 * @returns {Object} Đối tượng đã sao chép
 */
function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Bọc LocalStorage
 */
const Storage = {
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('Không thể lưu vào localStorage:', error);
    }
  },

  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      console.error('Không thể đọc từ localStorage:', error);
      return defaultValue;
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error('Không thể xóa khỏi localStorage:', error);
    }
  },

  clear() {
    try {
      localStorage.clear();
    } catch (error) {
      console.error('Không thể xóa localStorage:', error);
    }
  },
};

/**
 * Hiển thị thông báo toast
 * @param {string} message - Nội dung thông báo
 * @param {string} type - Loại (success|error|warning|info)
 * @param {number} duration - Thời gian hiển thị tính bằng mili giây
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
 * Tạo container toast nếu chưa tồn tại
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
 * Hiển thị spinner tải
 * @param {string} message - Nội dung thông báo
 * @returns {Function} Hàm để ẩn spinner
 */
function showSpinner(message = 'Đang tải...') {
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
        <span class="visually-hidden">Đang tải...</span>
      </div>
      <p class="text-white">${message}</p>
    </div>
  `;

  document.body.appendChild(overlay);

  return () => overlay.remove();
}

/**
 * Kiểm tra loại file hợp lệ
 * @param {File} file - Đối tượng file
 * @param {string[]} allowedTypes - Các loại MIME được phép
 * @returns {boolean} File có hợp lệ không
 */
function isValidFileType(file, allowedTypes) {
  return allowedTypes.includes(file.type);
}

/**
 * Kiểm tra kích thước file hợp lệ
 * @param {File} file - Đối tượng file
 * @param {number} maxSize - Kích thước tối đa tính bằng byte
 * @returns {boolean} File có hợp lệ không
 */
function isValidFileSize(file, maxSize) {
  return file.size <= maxSize;
}

/**
 * Chuyển đổi file sang base64
 * @param {File} file - Đối tượng file
 * @returns {Promise<string>} Chuỗi base64
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
 * Tải file xuống
 * @param {string} url - URL file
 * @param {string} filename - Tên file
 */
function downloadFile(url, filename = 'download') {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
}