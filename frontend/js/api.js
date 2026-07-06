/**
 * API Integration Layer
 * Handles all communication with backend FastAPI
 */

const API_BASE = 'http://localhost:8000';

class APIClient {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
    this.timeout = 30000; // 30s timeout
  }

  /**
   * Generic fetch wrapper with error handling
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      throw error;
    }
  }

  /**
   * Upload image and run full inspection pipeline
   * @param {File} file - Image file
   * @param {number} confidence - Confidence threshold (0-1)
   * @returns {Object} {predictions, image_path, report, vqa_answers}
   */
  async inspectImage(file, confidence = 0.25) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conf', confidence);

    return this.request('/inspect', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Segment image (detect + mask)
   * @param {File} file - Image file
   * @param {number} confidence - Confidence threshold
   * @returns {Object} {predictions, annotated_image_path}
   */
  async segmentImage(file, confidence = 0.25) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conf', confidence);

    return this.request('/segment', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Detect objects in image (bounding box only)
   * @param {File} file - Image file
   * @param {number} confidence - Confidence threshold
   * @returns {Object} {predictions, annotated_image_path}
   */
  async detectImage(file, confidence = 0.25) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conf', confidence);

    return this.request('/detect', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Get image caption
   * @param {File} file - Image file
   * @returns {Object} {caption}
   */
  async captionImage(file) {
    const formData = new FormData();
    formData.append('file', file);

    return this.request('/caption', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Ask question about image (VQA)
   * @param {File} file - Image file
   * @param {string} question - Question text
   * @param {Object} context - Optional inspection context
   * @returns {Object} {answer}
   */
  async askVQA(file, question, context = null) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('question', question);
    if (context) {
      formData.append('context', JSON.stringify(context));
    }

    return this.request('/vqa', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Upload and process video
   * @param {File} file - Video file
   * @param {number} confidence - Confidence threshold
   * @param {number} skipRate - Process every N frames
   * @returns {Object} {status, message, total_frames, defect_frames}
   */
  async processVideo(file, confidence = 0.25, skipRate = 5) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conf', confidence);
    formData.append('skip_rate', skipRate);

    return this.request('/process_video', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Get inspection logs/history
   * @param {number} page - Page number (1-indexed)
   * @param {number} limit - Items per page
   * @param {string} verdict - Filter by verdict (PASS|FLAG|REJECT)
   * @returns {Object} {data: Array, total, page, pages}
   */
  async getInspectionLogs(page = 1, limit = 10, verdict = null) {
    const params = new URLSearchParams({
      page,
      limit,
    });
    if (verdict) {
      params.append('verdict', verdict);
    }

    return this.request(`/logs?${params}`, {
      method: 'GET',
    });
  }

  /**
   * Get inspection detail by ID
   * @param {number} id - Inspection ID
   * @returns {Object} Full inspection details
   */
  async getInspectionDetail(id) {
    return this.request(`/logs/${id}`, {
      method: 'GET',
    });
  }

  /**
   * Health check
   * @returns {Object} {status}
   */
  async healthCheck() {
    return this.request('/', {
      method: 'GET',
    });
  }

  /**
   * Delete inspection record
   * @param {number} id - Inspection ID
   * @returns {Object} {message}
   */
  async deleteInspection(id) {
    return this.request(`/logs/${id}`, {
      method: 'DELETE',
    });
  }
}

// Export singleton instance
const apiClient = new APIClient();
