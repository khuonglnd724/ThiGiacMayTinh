/**
 * UI Components Manager
 */

class UIManager {
  constructor() {
    this.currentImage = null;
    this.currentResults = null;
    this.currentPage = 1;
  }

  /**
   * Initialize all UI event listeners
   */
  init() {
    this.setupNavigation();
    this.setupUploadWidget();
    this.setupSettingsForm();
    this.loadSettings();
  }

  /**
   * Setup navigation between pages
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
   * Navigate to a page
   * @param {string} page - Page name (dashboard|upload|results|history|settings)
   */
  navigateToPage(page) {
    // Hide all pages
    document.querySelectorAll('[data-page]').forEach((p) => {
      p.style.display = 'none';
    });

    // Show selected page
    const pageEl = document.querySelector(`[data-page="${page}"]`);
    if (pageEl) {
      pageEl.style.display = 'block';

      // Update active nav
      document.querySelectorAll('[data-nav]').forEach((link) => {
        link.classList.toggle('active', link.dataset.nav === page);
      });

      // Load page-specific data
      if (page === 'history') {
        this.loadHistory();
      } else if (page === 'dashboard') {
        this.loadDashboard();
      }
    }
  }

  /**
   * Setup file upload widget
   */
  setupUploadWidget() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!dropZone || !fileInput) return;

    // Drag and drop
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

    // Click to upload
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
   * Preview uploaded file
   * @param {File} file - File object
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

      // Show file info
      const fileInfo = document.getElementById('fileInfo');
      if (fileInfo) {
        fileInfo.innerHTML = `
          <div class="small">
            <p><strong>File:</strong> ${file.name}</p>
            <p><strong>Size:</strong> ${formatBytes(file.size)}</p>
            <p><strong>Type:</strong> ${file.type}</p>
          </div>
        `;
      }
    };
    reader.readAsDataURL(file);
  }

  /**
   * Upload and process file
   */
  async uploadFile() {
    if (!this.currentImage) {
      showToast('Please select an image first', 'warning');
      return;
    }

    const confidence =
      parseFloat(document.getElementById('confidenceSlider')?.value) || 0.25;
    const hideSpinner = showSpinner('Processing image...');

    try {
      const results = await apiClient.inspectImage(this.currentImage, confidence);
      this.currentResults = results;

      // Show results section
      this.displayResults(results);
      this.navigateToPage('results');
      showToast('Inspection completed successfully!', 'success');
    } catch (error) {
      console.error('Upload error:', error);
      showToast(`Error: ${error.message}`, 'error');
    } finally {
      hideSpinner();
    }
  }

  /**
   * Display inspection results
   * @param {Object} results - Inspection results from API
   */
  displayResults(results) {
    const resultsContainer = document.getElementById('resultsContainer');
    if (!resultsContainer) return;

    const { predictions, annotated_image_path, report, vqa_answers } = results;

    // Display annotated image
    const annotatedImg = document.getElementById('annotatedImage');
    if (annotatedImg && annotated_image_path) {
      annotatedImg.src = annotated_image_path;
    }

    // Display verdict
    const verdictEl = document.getElementById('verdictDisplay');
    if (verdictEl && report?.verdict) {
      verdictEl.innerHTML = `
        <span class="badge ${getVerdictClass(report.verdict)} fs-5">
          ${report.verdict}
        </span>
      `;
    }

    // Display predictions
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
                <small><strong>Confidence:</strong> ${(pred.confidence * 100).toFixed(1)}%</small>
              </div>
              <div class="col-6">
                <small><strong>Area:</strong> ${pred.area?.toFixed(2)}%</small>
              </div>
              <div class="col-6">
                <small><strong>Position:</strong> ${pred.position}</small>
              </div>
              <div class="col-6">
                <small><strong>Severity:</strong> <span class="badge ${getSeverityClass(pred.severity)}">${pred.severity}</span></small>
              </div>
              <div class="col-12">
                <small><strong>Size:</strong> ${pred.size_classification}</small>
              </div>
            </div>
          </div>
        </div>
      `
        )
        .join('');
      predictionsEl.innerHTML = predictionsList;
    }

    // Display report
    const reportEl = document.getElementById('reportDisplay');
    if (reportEl && report) {
      reportEl.innerHTML = `
        <div class="report-section">
          <h6>Inspection Summary</h6>
          <p>${report.summary || 'No summary available'}</p>
          
          ${
            report.recommendations
              ? `
          <h6 class="mt-3">Recommendations</h6>
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

    // Display VQA answers
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
   * Load dashboard statistics
   */
  async loadDashboard() {
    try {
      const logs = await apiClient.getInspectionLogs(1, 100);
      const data = logs.data || [];

      // Calculate statistics
      const total = data.length;
      const passed = data.filter((l) => l.verdict === 'PASS').length;
      const flagged = data.filter((l) => l.verdict === 'FLAG').length;
      const rejected = data.filter((l) => l.verdict === 'REJECT').length;

      // Display stats
      const dashboardStats = document.getElementById('dashboardStats');
      if (dashboardStats) {
        dashboardStats.innerHTML = `
          <div class="row">
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3>${total}</h3>
                  <p>Total Inspections</p>
                </div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3 class="text-success">${passed}</h3>
                  <p>Passed</p>
                </div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3 class="text-warning">${flagged}</h3>
                  <p>Flagged</p>
                </div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="stat-card card">
                <div class="card-body text-center">
                  <h3 class="text-danger">${rejected}</h3>
                  <p>Rejected</p>
                </div>
              </div>
            </div>
          </div>
        `;
      }
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    }
  }

  /**
   * Load inspection history
   * @param {number} page - Page number
   */
  async loadHistory(page = 1) {
    try {
      const hideSpinner = showSpinner('Loading history...');
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
              View
            </button>
            <button class="btn btn-sm btn-danger" onclick="uiManager.deleteInspection(${log.id})">
              Delete
            </button>
          </td>
        </tr>
      `
        )
        .join('');

      historyTable.innerHTML = rows || '<tr><td colspan="5" class="text-center">No records</td></tr>';

      // Update pagination
      this.updatePagination(logs.page, logs.pages);
    } catch (error) {
      console.error('Failed to load history:', error);
      showToast('Failed to load history', 'error');
    }
  }

  /**
   * Show inspection detail
   * @param {number} id - Inspection ID
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
      showToast(`Error: ${error.message}`, 'error');
    }
  }

  /**
   * Delete inspection record
   * @param {number} id - Inspection ID
   */
  async deleteInspection(id) {
    if (confirm('Are you sure?')) {
      try {
        await apiClient.deleteInspection(id);
        showToast('Deleted successfully', 'success');
        this.loadHistory();
      } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
      }
    }
  }

  /**
   * Setup settings form
   */
  setupSettingsForm() {
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    saveSettingsBtn?.addEventListener('click', () => {
      this.saveSettings();
    });
  }

  /**
   * Save settings to localStorage
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

    showToast('Settings saved successfully', 'success');
  }

  /**
   * Load settings from localStorage
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

    // Apply dark mode if enabled
    if (settings.darkMode) {
      this.toggleDarkMode(true);
    }
  }

  /**
   * Toggle dark mode
   * @param {boolean} enabled - Enable dark mode
   */
  toggleDarkMode(enabled) {
    document.documentElement.setAttribute('data-bs-theme', enabled ? 'dark' : 'light');
  }

  /**
   * Update pagination controls
   * @param {number} currentPage - Current page
   * @param {number} totalPages - Total pages
   */
  updatePagination(currentPage, totalPages) {
    const paginationEl = document.getElementById('paginationControls');
    if (!paginationEl) return;

    const buttons = [];
    buttons.push(
      currentPage > 1
        ? `<button class="btn btn-sm btn-outline-primary" onclick="uiManager.loadHistory(${currentPage - 1})">Previous</button>`
        : `<button class="btn btn-sm btn-outline-primary" disabled>Previous</button>`
    );

    for (let i = 1; i <= totalPages && i <= 5; i++) {
      buttons.push(
        `<button class="btn btn-sm btn-outline-primary ${i === currentPage ? 'active' : ''}" onclick="uiManager.loadHistory(${i})">${i}</button>`
      );
    }

    buttons.push(
      currentPage < totalPages
        ? `<button class="btn btn-sm btn-outline-primary" onclick="uiManager.loadHistory(${currentPage + 1})">Next</button>`
        : `<button class="btn btn-sm btn-outline-primary" disabled>Next</button>`
    );

    paginationEl.innerHTML = buttons.join(' ');
  }
}

// Create global UI manager instance
const uiManager = new UIManager();
