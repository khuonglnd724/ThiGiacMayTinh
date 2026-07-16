import sys
import subprocess
import os

# Try importing pptx, fallback to pip install without accent printing
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
except ImportError:
    print("Library python-pptx not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-pptx"])
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE

def create_presentation():
    # Khởi tạo bản trình bày
    prs = Presentation()
    
    # Thiết lập kích thước slide rộng 16:9 tiêu chuẩn
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    
    # Layout trống để dễ dàng vẽ tự do
    blank_layout = prs.slide_layouts[6]
    
    # Bảng màu chủ đạo (Indigo & Slate)
    c_dark_slate = RGBColor(15, 23, 42)
    c_indigo = RGBColor(79, 70, 229)
    c_cyan = RGBColor(6, 182, 212)
    c_text_main = RGBColor(51, 65, 85)
    c_text_white = RGBColor(255, 255, 255)
    c_bg_light = RGBColor(248, 250, 252)
    
    def set_slide_background(slide, color):
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_slide_header(slide, title_text):
        # Tạo shape tiêu đề
        title_box = slide.shapes.add_textbox(Inches(0.75), Inches(0.4), Inches(11.83), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.name = 'Inter'
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = c_dark_slate
        
        # Đường kẻ trang trí bên dưới tiêu đề
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.75), Inches(1.2), Inches(11.83), Inches(0.04))
        line.fill.solid()
        line.fill.fore_color.rgb = c_indigo
        line.line.color.rgb = c_indigo

    # -------------------------------------------------------------
    # SLIDE 1: Title Slide (Dark Theme)
    # -------------------------------------------------------------
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1, c_dark_slate)
    
    # Vẽ khối trang trí bên trái
    left_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.4), Inches(7.5))
    left_bar.fill.solid()
    left_bar.fill.fore_color.rgb = c_indigo
    left_bar.line.fill.background()
    
    # Text box tiêu đề chính
    title_box = s1.shapes.add_textbox(Inches(1.2), Inches(1.8), Inches(11.0), Inches(2.2))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "HỆ THỐNG TỰ ĐỘNG KIỂM TRA CHẤT LƯỢNG\nSẢN PHẨM BẰNG THỊ GIÁC MÁY TÌNH"
    p.font.name = 'Inter'
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = c_text_white
    p.alignment = PP_ALIGN.LEFT
    
    # Text box tiêu đề phụ
    sub_box = s1.shapes.add_textbox(Inches(1.2), Inches(4.2), Inches(11.0), Inches(1.0))
    tf_sub = sub_box.text_frame
    tf_sub.word_wrap = True
    p_sub = tf_sub.paragraphs[0]
    p_sub.text = "Ứng dụng YOLO11-seg, ResNet18 Classifier & Động cơ Hỏi đáp VQA đa ngôn ngữ"
    p_sub.font.name = 'Inter'
    p_sub.font.size = Pt(20)
    p_sub.font.italic = True
    p_sub.font.color.rgb = c_cyan
    
    # Thông tin nhóm
    info_box = s1.shapes.add_textbox(Inches(1.2), Inches(5.8), Inches(11.0), Inches(0.8))
    p_info = info_box.text_frame.paragraphs[0]
    p_info.text = "Báo cáo Đồ án tốt nghiệp / Nghiên cứu khoa học chuyên ngành Thị giác Máy tính"
    p_info.font.name = 'Inter'
    p_info.font.size = Pt(14)
    p_info.font.color.rgb = RGBColor(148, 163, 184)

    # -------------------------------------------------------------
    # SLIDE 2: Đặt vấn đề & Mục tiêu
    # -------------------------------------------------------------
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2, c_bg_light)
    add_slide_header(s2, "1. Đặt Vấn Đề & Mục Tiêu Dự Án")
    
    # Cột bên trái: Thực trạng & Thách thức
    col1 = s2.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(5.5), Inches(4.8))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "THỰC TRẠNG & THÁCH THỨC"
    p1.font.name = 'Inter'
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = c_indigo
    
    bullets1 = [
        "Kiểm tra chất lượng (QC) thủ công bằng mắt dễ gây sai sót do sự mệt mỏi của người vận hành.",
        "Thiếu báo cáo định lượng về kích thước lỗi, diện tích phủ của lỗi và vị trí lỗi cụ thể trên sản phẩm.",
        "Tốc độ kiểm định chậm, gây tắc nghẽn dây chuyền sản xuất hàng loạt.",
        "Khó lưu trữ lịch sử để cải tiến quy trình QC."
    ]
    for b in bullets1:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(14)

    # Cột bên phải: Giải pháp & Mục tiêu
    col2 = s2.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.8))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "MỤC TIÊU CỦA GIẢI PHÁP AI"
    p2.font.name = 'Inter'
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = c_cyan
    
    bullets2 = [
        "Tự động hóa hoàn toàn quy trình phát hiện và khoanh vùng lỗi bề mặt thời gian thực (Real-time).",
        "Trích xuất số liệu hình học chính xác diện tích, phân vùng lưới 9 khu vực và tính điểm nghiêm trọng.",
        "Xây dựng Dashboard trực quan hóa và bộ giả lập Conveyor Live cho sản xuất thực tế.",
        "Tích hợp công nghệ Chatbot VQA hỗ trợ cả tiếng Anh lẫn tiếng Việt giúp tương tác dễ dàng với hệ thống."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(14)

    # -------------------------------------------------------------
    # SLIDE 3: Kiến trúc hệ thống
    # -------------------------------------------------------------
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3, c_bg_light)
    add_slide_header(s3, "2. Kiến Trúc Hệ Thống Tổng Thể")
    
    # Vẽ các khối đại diện cho 3 lớp kiến trúc chính
    x_positions = [Inches(0.75), Inches(4.8), Inches(8.85)]
    widths = [Inches(3.6), Inches(3.6), Inches(3.7)]
    titles = [
        "💻 CLIENT (GIAO DIỆN)", 
        "⚡ FASTAPI BACKEND", 
        "🔮 PIPELINE AI & LOGIC"
    ]
    descs = [
        [
            "Giao diện HTML/CSS/JS thuần hiện đại",
            "Công cụ Upload ảnh phân tích QC trực quan",
            "Màn hình mô phỏng băng chuyền động Live",
            "Khung chat VQA trò chuyện trực tiếp với AI"
        ],
        [
            "API Server xây dựng trên FastAPI siêu tốc",
            "Xử lý kết nối, định tuyến yêu cầu HTTP",
            "Lịch sử kiểm định lưu vào cơ sở dữ liệu SQLite",
            "Giao diện RESTful tích hợp thuận tiện"
        ],
        [
            "YOLO11-seg: Phát hiện và phủ mặt nạ lỗi",
            "ResNet18: Phân loại loại lỗi chi tiết (ROI)",
            "Trích xuất đặc trưng diện tích, lưới vị trí",
            "Hệ quyết định QC ĐẠT/CẢNH BÁO/KHÔNG ĐẠT"
        ]
    ]
    
    for i in range(3):
        card = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x_positions[i], Inches(2.0), widths[i], Inches(4.5))
        card.fill.solid()
        card.fill.fore_color.rgb = c_dark_slate if i != 2 else c_indigo
        card.line.color.rgb = c_indigo
        
        tf = card.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        p.text = titles[i]
        p.font.name = 'Inter'
        p.font.size = Pt(18)
        p.font.bold = True
        p.font.color.rgb = c_text_white
        p.alignment = PP_ALIGN.CENTER
        p.space_after = Pt(20)
        
        for item in descs[i]:
            p2 = tf.add_paragraph()
            p2.text = "- " + item
            p2.font.name = 'Inter'
            p2.font.size = Pt(13)
            p2.font.color.rgb = RGBColor(226, 232, 240)
            p2.space_before = Pt(8)
            p2.alignment = PP_ALIGN.LEFT

    # -------------------------------------------------------------
    # SLIDE 4: Bộ dữ liệu MVTec-AD & Tiền xử lý
    # -------------------------------------------------------------
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4, c_bg_light)
    add_slide_header(s4, "3. Tập Dữ Liệu MVTec-AD & Tiền Xử Lý")
    
    col1 = s4.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(5.5), Inches(4.8))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "TẬP DỮ LIỆU HUẤN LUYỆN"
    p1.font.name = 'Inter'
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = c_indigo
    
    bullets = [
        "Sử dụng bộ dữ liệu chuẩn công nghiệp MVTec-AD.",
        "Mô phỏng các bề mặt sản phẩm kim loại, vỏ chai, dây cáp, gỗ...",
        "Phân tách rõ hai nhóm: Normal (Bình thường) và Anomaly (Có khuyết tật).",
        "Gán nhãn đa dạng loại lỗi: Trầy xước (Scratch), nứt (Crack), móp (Dent), thiếu linh kiện (Missing part)."
    ]
    for b in bullets:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)
        
    col2 = s4.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.8))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "TIỀN XỬ LÝ HÌNH ẢNH (PREPROCESSING)"
    p2.font.name = 'Inter'
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = c_cyan
    
    bullets2 = [
        "Thay đổi độ phân giải ảnh về kích thước chuẩn 640x640 pixel phục vụ model.",
        "Chuẩn hóa giá trị pixel về khoảng [0-1] để tăng tốc hội tụ.",
        "Làm sạch dữ liệu, loại bỏ các khung hình mờ, nhiễu kỹ thuật lớn.",
        "Chuyển đổi mặt nạ Segmentation Mask sang định dạng nhãn chuẩn YOLO."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)

    # -------------------------------------------------------------
    # SLIDE 5: Tăng cường dữ liệu (Augmentation)
    # -------------------------------------------------------------
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5, c_bg_light)
    add_slide_header(s5, "4. Tăng Cường Dữ Liệu (Augmentation)")
    
    # Thiết kế 4 khối biểu diễn 4 phương pháp Augment
    x_positions = [Inches(0.75), Inches(3.75), Inches(6.75), Inches(9.75)]
    titles = ["🔄 XOAY & LẬT", "☀️ ĐỘ SÁNG", "🔊 NHIỄU GAUSS", "🔎 THU PHÓNG"]
    descs = [
        "Lật ảnh ngẫu nhiên theo chiều dọc/ngang (Horizontal & Vertical Flip) và xoay tự do.\n\nGiúp mô hình nhận diện khuyết tật không phụ thuộc vào góc quay của sản phẩm trên băng tải.",
        "Thay đổi ngẫu nhiên độ sáng, độ tương phản (Brightness/Contrast).\n\nGiúp mô hình ổn định ngay cả khi ánh sáng nhà xưởng thay đổi đột ngột giữa ca ngày và đêm.",
        "Thêm nhiễu Gaussian ngẫu nhiên ở các cấp độ hạt mịn khác nhau.\n\nMô phỏng nhiễu phần cứng từ camera công nghiệp trong môi trường rung động của nhà máy.",
        "Cắt ngẫu nhiên và thu phóng (Random Crop & Scale).\n\nTập trung huấn luyện mô hình nhận diện lỗi ở nhiều tỷ lệ khoảng cách camera xa gần khác nhau."
    ]
    
    for i in range(4):
        card = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x_positions[i], Inches(2.0), Inches(2.83), Inches(4.5))
        card.fill.solid()
        card.fill.fore_color.rgb = c_dark_slate
        card.line.color.rgb = c_cyan
        
        tf = card.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        p.text = titles[i]
        p.font.name = 'Inter'
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = c_cyan
        p.alignment = PP_ALIGN.CENTER
        p.space_after = Pt(14)
        
        p2 = tf.add_paragraph()
        p2.text = descs[i]
        p2.font.name = 'Inter'
        p2.font.size = Pt(13)
        p2.font.color.rgb = RGBColor(226, 232, 240)
        p2.alignment = PP_ALIGN.LEFT

    # -------------------------------------------------------------
    # SLIDE 6: Phát hiện & Phân vùng lỗi (Model 1: YOLO11-seg)
    # -------------------------------------------------------------
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6, c_bg_light)
    add_slide_header(s6, "5. Phát Hiện & Phân Vùng Vùng Lỗi (YOLO11-seg)")
    
    col1 = s6.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(5.5), Inches(4.8))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "KIẾN TRÚC MÔ HÌNH HỌC SÂU 1"
    p1.font.name = 'Inter'
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = c_indigo
    
    bullets = [
        "Sử dụng YOLO11-seg làm mô hình học sâu chính cho tác vụ đầu chuỗi.",
        "Thực hiện đồng thời hai tác vụ: Phát hiện vật thể chứa lỗi và Phân vùng lỗi (Instance Segmentation).",
        "Đầu ra (Output) cung cấp Bounding Box (khung bao lỗi) và đường đa giác Segmentation Mask bao lỗi chi tiết.",
        "Trọng số tối ưu hóa được xuất ra file best.pt để tích hợp chạy thực tế."
    ]
    for b in bullets:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)
        
    col2 = s6.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.8))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "CHỈ SỐ THEO DÕI VÀ ĐÁNH GIÁ"
    p2.font.name = 'Inter'
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = c_cyan
    
    bullets2 = [
        "mAP (Mean Average Precision): Đo lường độ chính xác phát hiện trung bình.",
        "IoU (Intersection over Union) & Dice Score: Đo lường chất lượng và sự tương đồng của phân vùng mặt nạ lỗi so với nhãn gốc.",
        "Kiểm soát nghiêm ngặt tỷ lệ bỏ sót lỗi nghiêm trọng (False Negative) bắt buộc dưới 1-2%.",
        "Hỗ trợ chế độ chạy dự phòng yolo11n-seg.pt (Fallback) để đảm bảo hệ thống không bao giờ dừng hoạt động."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)

    # -------------------------------------------------------------
    # SLIDE 7: Phân loại loại lỗi chi tiết (Model 2: ResNet18)
    # -------------------------------------------------------------
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7, c_bg_light)
    add_slide_header(s7, "6. Phân Loại Loại Lỗi Chi Tiết (ResNet18 Classifier)")
    
    col1 = s7.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(5.5), Inches(4.8))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "MÔ HÌNH PHÂN LOẠI TUẦN TỰ"
    p1.font.name = 'Inter'
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = c_indigo
    
    bullets = [
        "Sử dụng mô hình ResNet18 Classifier chạy song hành tuần tự sau YOLO11-seg.",
        "Nhận diện chính xác tên loại lỗi (Scratch, Dent, Crack...) thay vì chỉ gom nhóm chung là 'lỗi'.",
        "Trích xuất vùng ảnh lỗi (ROI) từ bounding box của YOLO, mở rộng thêm 15% biên để thu thập ngữ cảnh xung quanh.",
        "Học sâu phân loại trên tập phân loại lỗi công nghiệp lên tới ~41 lớp lỗi."
    ]
    for b in bullets:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)
        
    col2 = s7.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.8))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "CƠ CHẾ RÀNG BUỘC PHÂN LOẠI"
    p2.font.name = 'Inter'
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = c_cyan
    
    bullets2 = [
        "Tích hợp tệp cấu hình JSON định hình mối quan hệ giữa nhóm sản phẩm và các loại lỗi được phép tồn tại.",
        "Lọc kết quả dự đoán của ResNet18, loại bỏ các lỗi vô lý không thể xảy ra đối với cấu trúc vật lý sản phẩm đó.",
        "Cung cấp danh sách dự đoán Top-3 kèm độ tin cậy tương ứng.",
        "Thiết lập cơ chế Fallback Heuristic tự động chuyển sang phân loại dựa trên luật mềm nếu không thể khởi tạo mô hình."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)

    # -------------------------------------------------------------
    # SLIDE 8: Trích xuất đặc trưng & Luật QC
    # -------------------------------------------------------------
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8, c_bg_light)
    add_slide_header(s8, "7. Trích Xuất Đặc Trưng Hình Học & Quyết Định QC")
    
    col1 = s8.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(5.5), Inches(4.8))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "TRÍCH XUẤT ĐẶC TRƯNG HÌNH HỌC"
    p1.font.name = 'Inter'
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = c_indigo
    
    bullets = [
        "Diện tích (Area): Tính toán diện tích vùng lỗi bằng công thức đa giác Shoelace trên tọa độ polygon của mask.",
        "Vị trí (Position): Chia bề mặt sản phẩm thành lưới 9 khu vực (9-zone grid), xác định lỗi nằm ở vị trí nào.",
        "Độ nghiêm trọng (Severity Score): Thang điểm 0-100 tính dựa trên tỉ lệ diện tích (40%) + vị trí lỗi tâm hay biên (30%) + độ tin cậy AI (30%)."
    ]
    for b in bullets:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)
        
    col2 = s8.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.8))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "LUẬT RA QUYẾT ĐỊNH QC"
    p2.font.name = 'Inter'
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = c_cyan
    
    bullets2 = [
        "ĐẠT (PASS): Sản phẩm sạch hoàn toàn hoặc các lỗi phát hiện chỉ có độ nghiêm trọng ở mức thấp (Low Severity < 25).",
        "CẢNH BÁO (FLAG): Phát hiện có từ 1 đến 2 lỗi ở mức độ trung bình (Medium Severity: 25-50) ➔ Chuyển qua luồng kiểm tra lại thủ công.",
        "KHÔNG ĐẠT (REJECT): Có nhiều hơn 2 lỗi Medium hoặc tồn tại bất kỳ lỗi nào ở mức độ cao (High / Critical Severity > 50) ➔ Hủy bỏ sản phẩm."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)

    # -------------------------------------------------------------
    # SLIDE 9: Động cơ Hỏi Đáp VQA
    # -------------------------------------------------------------
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9, c_bg_light)
    add_slide_header(s9, "8. Động Cơ Hỏi Đáp Ngữ Cảnh Đa Ngôn Ngữ (VQA)")
    
    col1 = s9.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(5.5), Inches(4.8))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "CƠ CHẾ PHÂN CẤP ƯU TIÊN 3 TẦNG"
    p1.font.name = 'Inter'
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = c_indigo
    
    bullets = [
        "Tầng 1 (Context-aware): Trích xuất thông tin trực tiếp từ báo cáo QC (tổng lỗi, mức độ nghiêm trọng, vị trí lỗi). Ưu tiên tốc độ xử lý nhanh nhất.",
        "Tầng 2 (Deep Learning): Sử dụng mô hình Transformer ViLT trực tuyến để xử lý các câu hỏi trực quan tổng quát hơn ngoài phạm vi báo cáo QC.",
        "Tầng 3 (Keyword Fallback): Bộ so khớp từ khóa dự phòng có sẵn tiếng Việt và tiếng Anh để đưa ra phản hồi logic, mượt mà."
    ]
    for b in bullets:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)
        
    col2 = s9.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.8))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "BẢN ĐỊA HÓA TIẾNG VIỆT ĐỘNG"
    p2.font.name = 'Inter'
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = c_cyan
    
    bullets2 = [
        "Tự động quét và phát hiện ngôn ngữ câu hỏi dựa trên các từ khóa tiếng Việt.",
        "Phản hồi trực quan bằng tiếng Việt cho 8 chủ đề chính: Có lỗi không, độ nghiêm trọng, vị trí, kết quả QC, số lượng lỗi, loại lỗi, khuyến cáo và báo cáo tóm tắt.",
        "Hỗ trợ ghi nhớ context: Sử dụng biến toàn cục ở frontend để tự động chuyển tiếp dữ liệu phân tích sang VQA chat."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = c_text_main
        p.space_before = Pt(12)

    # -------------------------------------------------------------
    # SLIDE 10: Kết luận & Hướng phát triển
    # -------------------------------------------------------------
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10, c_dark_slate)
    
    # Khối bên trái trang trí
    left_bar = s10.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.4), Inches(7.5))
    left_bar.fill.solid()
    left_bar.fill.fore_color.rgb = c_cyan
    left_bar.line.fill.background()
    
    col1 = s10.shapes.add_textbox(Inches(1.0), Inches(1.5), Inches(5.2), Inches(5.0))
    tf1 = col1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "KẾT QUẢ ĐẠT ĐƯỢC"
    p1.font.name = 'Inter'
    p1.font.size = Pt(24)
    p1.font.bold = True
    p1.font.color.rgb = c_cyan
    
    bullets = [
        "Xây dựng thành công hệ thống tích hợp mượt mà giữa AI Vision và Dashboard quản lý.",
        "Tỉ lệ bỏ sót lỗi nghiêm trọng rất thấp (< 1-2%), đáp ứng yêu cầu chất lượng công nghiệp.",
        "Dashboard trực quan hóa cao cấp, thao tác đơn giản và hỗ trợ VQA phản hồi cực nhạy."
    ]
    for b in bullets:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = RGBColor(226, 232, 240)
        p.space_before = Pt(16)
        
    col2 = s10.shapes.add_textbox(Inches(6.8), Inches(1.5), Inches(5.8), Inches(5.0))
    tf2 = col2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "HƯỚNG PHÁT TRIỂN TIẾP THEO"
    p2.font.name = 'Inter'
    p2.font.size = Pt(24)
    p2.font.bold = True
    p2.font.color.rgb = c_text_white
    
    bullets2 = [
        "Tối ưu hóa tốc độ suy luận (Inference Speed) bằng TensorRT để chạy ổn định trên thiết bị nhúng (Nvidia Jetson) ở rìa băng chuyền.",
        "Tích hợp kết nối trực tiếp với các thiết bị vật lý công nghiệp PLC, cánh tay robot để tự động gạt sản phẩm lỗi.",
        "Huấn luyện mở rộng thêm các nhóm sản phẩm và khuyết tật bề mặt mới."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.name = 'Inter'
        p.font.size = Pt(15)
        p.font.color.rgb = RGBColor(226, 232, 240)
        p.space_before = Pt(16)

    # Lưu tệp PowerPoint
    output_filename = "presentation_ai_qc.pptx"
    prs.save(output_filename)
    print("Presentation saved successfully: " + os.path.abspath(output_filename))

if __name__ == "__main__":
    create_presentation()
