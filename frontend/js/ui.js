/**
 * Quản Lý Thành Phần Giao Diện
 */

class UIManager {
  constructor() {
    this.currentImage = null;
    this.currentResults = null;
    this.currentPage = 1;
  }

  /**
   * Khởi tạo tất cả trình lắng nghe sự kiện giao diện
   */
  init() {
    this.setupNavigation();
    this.setupUploadWidget();
    this.setupSettingsForm();
    this.loadSettings();
  }

  /**
   * Thiết lập điều hướng giữa các trang
   */
  setupNavigation() {
    const navLinks = document.querySelectorAll('[data-nav]');
    navLinks.forEach((link) => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.dataset.nav;
        this.navigateToPage(page);
      });
    });
  }

  /**
   * Điều hướng tới một trang
   * @param {string} page - Tên trang (dashboard|upload|results|history|settings)
   */
  navigateToPage(page) {
    // Ẩn tất cả trang
    document.querySelectorAll('[data-page]').forEach((p) => {
      p.style.display = 'none';
    });

    // Hiện trang được chọn
    const pageEl = document.querySelector(`[data-page="${page}"]`);
    if (pageEl) {
      pageEl.style.display = 'block';

      // Cập nhật nav đang hoạt động
      document.querySelectorAll('[data-nav]').forEach((link) => {
        link.classList.toggle('active', link.dataset.nav === page);
      });

      // Tải dữ liệu riêng cho từng trang
      if (page === 'history') {
        this.loadHistory();
      } else if (page === 'dashboard') {
        this.loadDashboard();
      }
    }
  }

  /**
   * Thiết lập widget tải lên file
   */
  setupUploadWidget() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!dropZone || !fileInput) return;

    // Kéo và thả
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        fileInput.files = files;
        this.previewFile(files[0]);
      }
    });

    // Nhấp để tải lên
    dropZone.addEventListener('click', () => {
      fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        this.previewFile(e.target.files[0]);
      }
    });

    uploadBtn?.addEventListener('click', () => {
      this.uploadFile();
    });
  }

  /**
   * Xem trước file đã tải lên
   * @param {File} file - File đối tượng
   */
  async previewFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      this.currentImage = file;
      const preview = document.getElementById('imagePreview');
      if (preview) {
        preview.src = e.target.result;
        preview.style.display = 'block';
      }

      // Hiển thị thông tin file
      const fileInfo = document.getElementById('fileInfo');
      if (fileInfo) {
        fileInfo.innerHTML = `
          <div class="small">
            <p><strong>File:</strong> ${file.name}</p>
            <p><strong>Kích thước:</strong> ${formatBytes(file.size)}</p>
            <p><strong>Loại:</strong> ${file.type}</p>
          </div>
        `;
      }
    };
    reader.readAsDataURL(file);
  }

  /**
   * Tải lên và xử lý file
   */
  async uploadFile() {
    if (!this.currentImage) {
      showToast('Vui lòng chọn ảnh trước', 'warning');
      return;
    }

    const confidence =
      parseFloat(document.getElementById('confidenceSlider')?.value) || 0.25;
    const hideSpinner = showSpinner('Đang xử lý ảnh...');

    try {
      const results = await apiClient.inspectImage(this.currentImage, confidence);
      this.currentResults = results;

      // Hiển thị phần kết quả
      this.displayResults(results);
      this.navigateToPage('results');
      showToast('Kiểm tra hoàn tất!', 'success');
    } catch (error) {
      console.error('Lỗi tải lên:', error);
      showToast(`Lỗi: ${error.message}`, 'error');
    } finally {
      hideSpinner();
    }
  }

  /**
   * Hiển thị kết quả kiểm tra
   * @param {Object} results - Kết quả kiểm tra từ API
   */
  displayResults(results) {
    const resultsContainer = document.getElementById('resultsContainer');
    if (!resultsContainer) return;

    const { predictions, annotated_image_path, report, vqa_answers } = results;

    // Hiển thị ảnh đã chú thích
    const annotatedImg = document.getElementById('annotatedImage');
    if (annotatedImg && annotated_image_path) {
      annotatedImg.src = annotated_image_path;
    }

    // Hiển thị kết luận
    const verdictEl = document.getElementById('verdictDisplay');
    if (verdictEl && report?.verdict) {
      verdictEl.innerHTML = `
        <span class="badge ${getVerdictClass(report.verdict)} fs-5">
          ${report.verdict}
        </span>
      `;
    }

    // Hiển thị dự đoán
    const predictionsEl = document.getElementById('predictionsDisplay');
    if (predictionsEl && predictions?.length > 0) {
      const predictionsList = predictions
        .map(
          (pred) => `
        <div class="card prediction-card mb-3">
          <div class="card-body">
            <h6 class="card-title">${pred.defect_type || pred.class_name}</h6>
            <div class="row">
              <div class="col-6">
                <small><strong>Độ tin cậy:</strong> ${(pred.confidence * 100).toFixed(1)}%</small>
              </div>
              <div class="col-6">
                <small><strong>Diện tích:</strong> ${pred.area?.toFixed(2)}%</small>
              </div>
              <div class="col-6">
                <small><strong>Vị trí:</strong> ${pred.position}</small>
              </div>
              <div class="col-6">
                <small><strong>Mức độ:</strong> <span class="badge ${getSeverityClass(pred.severity)}">${pred.severity}</span></small>
              </div>
              <div class="col-12">
                <small><strong>Kích thước:</strong> ${pred.size_classification}</small>
              </div>
            </div>
          </div>
        </div>
      `
        )
        .join('');
      predictionsEl.innerHTML = predictionsList;
    }

    // Hiển thị báo cáo
    const reportEl = document.getElementById('reportDisplay');
    if (reportEl && report) {
      reportEl.innerHTML = `
        <div class="report-section">
          <h6>Tóm tắt kiểm tra</h6>
          <p>${report.summary || 'Không có tóm tắt'}</p>
          
          ${
            report.recommendations
              ? `
          <h6 class="mt-3">Khuyến cáo</h6>
          <ul>
            ${report.recommendations
              .map((rec) => `<li>${rec}</li>`)
              .join('')}
          </ul>
          `
              : ''
          }
        </div>
      `;
    }

    // Hiển thị câu trả lời VQA
    const vqaEl = document.getElementById('vqaAnswers');
    if (vqaEl && vqa_answers) {
      const answersList = Object.entries(vqa_answers)
        .map(
          ([question, answer]) => `
        <div class="card vqa-card mb-2">
          <div class="card-body p-2">
            <p class="mb-1"><strong>${question}</strong></p>
            <p class="text-muted mb-0">${answer}</p>
          </div>
        </div>
      `
        )
        .join('');
      vqaEl.innerHTML = answersList;
    }
  }

  /**
   * Tải thống kê tổng quan
   */
  async loadDashboard() {
    try {
      const logs = await apiClient.getInspectionLogs(1, 100);
      const data = logs.data || [];

      // Tính toán thống kê
      const total = data.length;
      const passed = data.filter((l) => l.verdict === 'PASS').length;
      const flagged = data.filter((l) => l.verdict === 'FLAG').length;
      const rejected = data.filter((l) => l.verdict === 'REJECT').length;

      // Hiển thị thống kê
      const dashboardStats = document.getElementById('dashboardStats');
      if (dashboardStats) {
        dashboardStats.innerHTML = `
          <div class="row">
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3>${total}</h3>
                  <p>Tổng kiểm tra</p>
                </div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3 class="text-success">${passed}</h3>
                  <p>Đạt</p>
                </div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3 class="text-warning">${flagged}</h3>
                  <p>Chờ xử lý</p>
                </div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3 class="text-danger">${rejected}</h3>
                  <p>Không đạt</p>
                </div>
              </div>
            </div>
          </div>
        `;
      }
    } catch (error) {
      console.error('Không thể tải tổng quan:', error);
    }
  }

  /**
   * Tải lịch sử kiểm tra
   * @param {number} page - Số trang
   */
  async loadHistory(page = 1) {
    try {
      const hideSpinner = showSpinner('Đang tải lịch sử...');
      const logs = await apiClient.getInspectionLogs(page, 10);
      hideSpinner();

      const historyTable = document.getElementById('historyTable');
      if (!historyTable) return;

      const rows = (logs.data || [])
        .map(
          (log) => `
        <tr>
          <td>${log.id}</td>
          <td>${log.video_name || 'N/A'}</td>
          <td>
            <span class="badge ${getVerdictClass(log.verdict)}">
              ${log.verdict}
            </span>
          </td>
          <td>${formatDate(log.created_at)}</td>
          <td>
            <button class="btn btn-sm btn-primary" onclick="uiManager.showInspectionDetail(${log.id})">
              Xem
            </button>
            <button class="btn btn-sm btn-danger" onclick="uiManager.deleteInspection(${log.id})">
              Xóa
            </button>
          </td>
        </tr>
      `
        )
        .join('');

      historyTable.innerHTML = rows || '<tr><td colspan="5" class="text-center">Không có bản ghi</td></tr>';

      // Cập nhật phân trang
      this.updatePagination(logs.page, logs.pages);
    } catch (error) {
      console.error('Không thể tải lịch sử:', error);
      showToast('Không thể tải lịch sử', 'error');
    }
  }

  /**
   * Hiển thị chi tiết kiểm tra
   * @param {number} id - ID kiểm tra
   */
  async showInspectionDetail(id) {
    try {
      const detail = await apiClient.getInspectionDetail(id);
      const modal = new bootstrap.Modal(document.getElementById('detailModal'));
      const modalBody = document.querySelector('#detailModal .modal-body');

      if (modalBody) {
        modalBody.innerHTML = `
          <pre><code>${JSON.stringify(detail, null, 2)}</code></pre>
        `;
      }

      modal.show();
    } catch (error) {
      showToast(`Lỗi: ${error.message}`, 'error');
    }
  }

  /**
   * Xóa bản ghi kiểm tra
   * @param {number} id - ID kiểm tra
   */
  async deleteInspection(id) {
    if (confirm('Bạn có chắc chắn muốn xóa?')) {
      try {
        await apiClient.deleteInspection(id);
        showToast('Xóa thành công', 'success');
        this.loadHistory();
      } catch (error) {
        showToast(`Lỗi: ${error.message}`, 'error');
      }
    }
  }

  /**
   * Thiết lập form cài đặt
   */
  setupSettingsForm() {
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    saveSettingsBtn?.addEventListener('click', () => {
      this.saveSettings();
    });
  }

  /**
   * Lưu cài đặt vào localStorage
   */
  saveSettings() {
    const confidence = parseFloat(document.getElementById('confidenceSlider')?.value) || 0.25;
    const skipRate = parseInt(document.getElementById('skipRateSlider')?.value) || 5;
    const showLabels = document.getElementById('showLabelsCheckbox')?.checked ?? true;
    const darkMode = document.getElementById('darkModeCheckbox')?.checked ?? false;

    Storage.set('settings', {
      confidence,
      skipRate,
      showLabels,
      darkMode,
    });

    showToast('Cài đặt đã được lưu', 'success');
  }

  /**
   * Tải cài đặt từ localStorage
   */
  loadSettings() {
    const settings = Storage.get('settings', {
      confidence: 0.25,
      skipRate: 5,
      showLabels: true,
      darkMode: false,
    });

    const confidenceSlider = document.getElementById('confidenceSlider');
    if (confidenceSlider) {
      confidenceSlider.value = settings.confidence;
      document.getElementById('confidenceValue').textContent = settings.confidence.toFixed(2);

      confidenceSlider.addEventListener('input', (e) => {
        document.getElementById('confidenceValue').textContent = parseFloat(e.target.value).toFixed(2);
      });
    }

    const skipRateSlider = document.getElementById('skipRateSlider');
    if (skipRateSlider) {
      skipRateSlider.value = settings.skipRate;
      document.getElementById('skipRateValue').textContent = settings.skipRate;

      skipRateSlider.addEventListener('input', (e) => {
        document.getElementById('skipRateValue').textContent = e.target.value;
      });
    }

    const showLabelsCheckbox = document.getElementById('showLabelsCheckbox');
    if (showLabelsCheckbox) {
      showLabelsCheckbox.checked = settings.showLabels;
    }

    const darkModeCheckbox = document.getElementById('darkModeCheckbox');
    if (darkModeCheckbox) {
      darkModeCheckbox.checked = settings.darkMode;
      darkModeCheckbox.addEventListener('change', (e) => {
        this.toggleDarkMode(e.target.checked);
      });
    }

    // Áp dụng chế độ tối nếu được bật
    if (settings.darkMode) {
      this.toggleDarkMode(true);
    }
  }

  /**
   * Chuyển đổi chế độ tối
   * @param {boolean} enabled - Bật chế độ tối
   */
  toggleDarkMode(enabled) {
    document.documentElement.setAttribute('data-bs-theme', enabled ? 'dark' : 'light');
  }

  /**
   * Cập nhật điều khiển phân trang
   * @param {number} currentPage - Trang hiện tại
   * @param {number} totalPages - Tổng số trang
   */
  updatePagination(currentPage, totalPages) {
    const paginationEl = document.getElementById('paginationControls');
    if (!paginationEl) return;

    const buttons = [];
    buttons.push(
      currentPage > 1
        ? `<button class="btn btn-sm btn-outline-primary" onclick="uiManager.loadHistory(${currentPage - 1})">Trước</button>`
        : `<button class="btn btn-sm btn-outline-primary" disabled>Trước</button>`
    );

    for (let i = 1; i <= totalPages && i <= 5; i++) {
      buttons.push(
        `<button class="btn btn-sm btn-outline-primary ${i === currentPage ? 'active' : ''}" onclick="uiManager.loadHistory(${i})">${i}</button>`
      );
    }

    buttons.push(
      currentPage < totalPages
        ? `<button class="btn btn-sm btn-outline-primary" onclick="uiManager.loadHistory(${currentPage + 1})">Sau</button>`
        : `<button class="btn btn-sm btn-outline-primary" disabled>Sau</button>`
    );

    paginationEl.innerHTML = buttons.join(' ');
  }
}

// Tạo instance quản lý giao diện toàn cục
const uiManager = new UIManager();