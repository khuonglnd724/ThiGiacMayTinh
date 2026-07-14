/**
 * Lớp Tích Hợp API
 * Xử lý mọi giao tiếp với backend FastAPI
 */

const API_BASE = 'http://localhost:8000';

class APIClient {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
    this.timeout = 300000; // 5 phút timeout cho xử lý video
  }

  /**
   * Wrapper fetch chung với xử lý lỗi
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
        throw new Error('Yêu cầu đã hết thời gian chờ');
      }
      throw error;
    }
  }

  /**
   * Tải lên ảnh và chạy quy trình kiểm tra đầy đủ
   * @param {File} file - File ảnh
   * @param {number} confidence - Ngưỡng độ tin cậy (0-1)
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
   * Phân vùng ảnh (phát hiện + mặt nạ)
   * @param {File} file - File ảnh
   * @param {number} confidence - Ngưỡng độ tin cậy
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
   * Phát hiện đối tượng trong ảnh (chỉ bounding box)
   * @param {File} file - File ảnh
   * @param {number} confidence - Ngưỡng độ tin cậy
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
   * Lấy chú thích ảnh
   * @param {File} file - File ảnh
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
   * Hỏi câu hỏi về ảnh (VQA)
   * @param {File} file - File ảnh
   * @param {string} question - Nội dung câu hỏi
   * @param {Object} context - Ngữ cảnh kiểm tra tùy chọn
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
   * Tải lên và xử lý video (với phát hiện thay đổi cảnh)
   * @param {File} file - File video
   * @param {number} confidence - Ngưỡng độ tin cậy
   * @param {number} maxFrames - Số lượng frame tối đa cần xử lý
   * @param {number} sceneThreshold - Ngưỡng phát hiện thay đổi cảnh (thấp hơn = nhạy hơn)
   * @returns {Object} {status, message, total_frames, unique_images_detected, defect_frames}
   */
  async processVideo(file, confidence = 0.25, maxFrames = 40, sceneThreshold = 30.0) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conf', confidence);
    formData.append('max_frames', maxFrames);
    formData.append('scene_threshold', sceneThreshold);

    return this.request('/process_video', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Lấy ảnh từ URL, sau đó hỏi câu hỏi VQA về ảnh đó.
   * Dùng cho các frame video khi có saved_image_url thay vì file tải lên.
   * @param {string} imageUrl - URL của ảnh cần hỏi
   * @param {string} question - Nội dung câu hỏi
   * @param {Object} context - Ngữ cảnh kiểm tra tùy chọn (ví dụ: dự đoán của một lỗi cụ thể)
   * @returns {Object} {answer}
   */
  async askVQAFromUrl(imageUrl, question, context = null) {
    // Lấy ảnh từ URL dưới dạng blob
    const response = await fetch(imageUrl);
    if (!response.ok) {
      throw new Error(`Không thể lấy ảnh từ ${imageUrl}: HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const fileName = imageUrl.split('/').pop() || 'frame.jpg';
    const file = new File([blob], fileName, { type: blob.type || 'image/jpeg' });

    // Sau đó dùng phương thức askVQA có sẵn
    return this.askVQA(file, question, context);
  }

  /**
   * Mô phỏng luồng kiểm tra băng chuyền trực tiếp từ backend.
   * @param {number} frames - Số lượng frame mô phỏng cần trả về
   * @param {number} intervalMs - Độ trễ giữa các frame tính bằng mili giây
   * @param {number} confidence - Ngưỡng độ tin cậy dùng cho mô phỏng
   * @returns {Object} {status, frames, interval_ms}
   */
  async simulateConveyor(frames = 8, intervalMs = 800, confidence = 0.25) {
    const params = new URLSearchParams({
      frames,
      interval_ms: intervalMs,
      confidence,
    });

    return this.request(`/conveyor/simulate?${params}`, {
      method: 'GET',
    });
  }

  /**
   * Lấy nhật ký/lịch sử kiểm tra
   * @param {number} page - Số trang (đánh số từ 1)
   * @param {number} limit - Số mục mỗi trang
   * @param {string} verdict - Lọc theo kết luận (PASS|FLAG|REJECT)
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
   * Lấy chi tiết kiểm tra theo ID
   * @param {number} id - ID kiểm tra
   * @returns {Object} Chi tiết kiểm tra đầy đủ
   */
  async getInspectionDetail(id) {
    return this.request(`/logs/${id}`, {
      method: 'GET',
    });
  }

  /**
   * Kiểm tra sức khỏe
   * @returns {Object} {status}
   */
  async healthCheck() {
    return this.request('/', {
      method: 'GET',
    });
  }

  /**
   * Xóa bản ghi kiểm tra
   * @param {number} id - ID kiểm tra
   * @returns {Object} {message}
   */
  async deleteInspection(id) {
    return this.request(`/logs/${id}`, {
      method: 'DELETE',
    });
  }
}

// Xuất singleton instance
const apiClient = new APIClient();