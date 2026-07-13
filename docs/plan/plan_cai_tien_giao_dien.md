# Kế hoạch Cải thiện Giao diện Dashboard (UI Modernization Plan)

## Goal
Cải thiện giao diện hiển thị của dashboard chất lượng sản phẩm (QC) trở nên hiện đại, cao cấp, chuyên nghiệp và có chiều sâu, loại bỏ cảm giác thô sơ của mã nguồn tự động tạo (AI-generated look). 
**Cam kết:** Giữ nguyên 100% cấu trúc HTML, bố cục lưới, vị trí các nút, thanh trượt và các luồng chức năng hiện tại. Chỉ nâng cấp các thuộc tính CSS.

## Input
- File giao diện chính: [index.html](file:///c:/Users/LENOVO/Downloads/ThiGiacMayTinh/ThiGiacMayTinh/frontend/index.html)
- Tệp định hình quy tắc: [rule.md](file:///c:/Users/LENOVO/Downloads/ThiGiacMayTinh/ThiGiacMayTinh/docs/rule.md)

## Output
- File [index.html](file:///c:/Users/LENOVO/Downloads/ThiGiacMayTinh/ThiGiacMayTinh/frontend/index.html) được nâng cấp vùng `<style>` với thiết kế chuyên nghiệp.
- Ghi nhận chi tiết lịch sử sửa đổi trong log.

## How to do
1. **Font & Typography**:
   - Nhúng font chữ hiện đại **Inter** từ Google Fonts.
   - Điều chỉnh tỉ lệ font-size, line-height và letter-spacing.
2. **Bảng màu & Glassmorphism**:
   - Chuyển đổi màu sắc sang hệ màu Slate & Indigo hiện đại (SaaS/Enterprise style).
   - Header: Thay đổi gradient phẳng thành gradient chiều sâu kim loại tối (`#0f172a` sang `#1e1b4b`) kèm hiệu ứng phản quang nhẹ.
   - sidebar & main panel: Tăng góc bo tròn thành `16px`, sử dụng đường viền mảnh `1px solid #e2e8f0` và đổ bóng cực mềm (soft-shadow).
3. **Chi tiết hóa các thành phần (Component Styling)**:
   - **Upload Box**: Định hình lại viền đứt nét mảnh, tăng khoảng cách padding và tạo hiệu ứng nhấc nhẹ khi di chuột qua (hover translateY).
   - **Range Slider**: Tùy biến hoàn toàn track và thumb của thanh trượt, tạo hiệu ứng phát sáng nhẹ khi hover/focus.
   - **Buttons**: Thiết kế nút bấm với độ chuyển màu mượt mà, phản hồi chuyển động (scale) cực nhạy.
   - **Defect Cards**: Thiết kế lại header thẻ lỗi với gradient mềm, phần thông tin chi tiết dùng viền phân chia thanh mảnh.
   - **VQA Section**: Bo góc mềm các thẻ chat, sử dụng màu xanh dịu mắt và xám mềm để phân biệt câu hỏi/trả lời.
   - **Live Panel**: Nâng cấp giao diện giả lập băng chuyền tối màu với màu xanh neon nổi bật của viền trạng thái.
4. **Hiệu ứng Micro-animations**:
   - Cài đặt thuộc tính `transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1)` cho mọi tương tác hover của nút, thẻ lỗi và thẻ lịch sử để tạo cảm giác mượt mà.

## Lưu ý
- Không thay đổi tên class hay id nào trong CSS/HTML để tránh phá vỡ code JS hiện tại.
- Giữ lại đầy đủ các thuộc tính responsive cho di động.
- File plan không vượt quá 200 dòng theo đúng rule.md.
