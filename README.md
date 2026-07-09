# 🏥 Hệ Thống Tự Động Hóa Content Y Khoa: TikTok -> Benhviencantho.com

Dự án tự động cào video TikTok chính thức từ **Bệnh viện Đa khoa Quốc tế S.I.S Cần Thơ (`@bvquoctesis`)**, sử dụng **AI Google Gemini Pro** để viết bài tư vấn y khoa Chuẩn SEO E-E-A-T tích hợp **Ma trận 4 Nhóm Từ Khóa Ngách Chuyên Sâu** và tự động đăng tải trực tiếp lên cổng thông tin **Benhviencantho.com**.

---

## 🌟 Tính Năng Nổi Bật & Tối Ưu SEO Ngách Chuyên Sâu

- **Tự động kết nối RSS Feed:** Đọc video TikTok thời gian thực từ Google Apps Script Web App (`AKfycbw...`).
- **Ma Trận Từ Khóa Ngách Y Khoa (Niche Keyword Matrix):** Tự động nhận diện chủ đề bệnh lý của video để lồng ghép 4 nhóm từ khóa ngách hữu cơ vào nội dung:
  1. **Nhóm Dịch vụ/Chuyên khoa + Địa phương:** `[Tên bệnh/phương pháp] + [tại/ở đâu] + [Cần Thơ/Miền Tây]` *(Ví dụ: tầm soát đột quỵ ở đâu Cần Thơ, khám tim mạch tại miền Tây...)*.
  2. **Nhóm Giải đáp Chi phí & BHYT:** `[Chi phí/Bảng giá/BHYT] + [Tên dịch vụ/Tên bệnh viện]` *(Ví dụ: chi phí chụp MRI mạch máu não Bệnh viện SIS Cần Thơ, khám BHYT tại Bệnh viện Cần Thơ...)*.
  3. **Nhóm Thương hiệu Chuyên gia:** `[Bác sĩ] + [Chuyên khoa] + [giỏi/uy tín] + [Cần Thơ]` *(Ví dụ: bác sĩ tim mạch giỏi Cần Thơ, TS.BS Trần Chí Cường bác sĩ đột quỵ uy tín Cần Thơ...)*.
  4. **Nhóm Tiện ích & Hướng dẫn thủ tục:** `[Hướng dẫn đặt lịch/Thủ tục khám BHYT/Xe đưa đón] + Bệnh viện Cần Thơ`.
- **Đảm bảo Từ Khóa Chính:** Luôn duy trì từ khóa trung tâm `Bệnh viện Cần Thơ` bôi đậm ngay mở đầu và lặp lại đều đặn chuẩn xác.
- **Viết bài Chuẩn Y Khoa E-E-A-T:** Cấu trúc 4 thẻ H2 khoa học, dễ hiểu cho người bệnh, kèm hỏi đáp nhanh FAQ cuối bài.
- **Tự động tải & xử lý ảnh Cover:** Tải ảnh gốc từ CDN TikTok lưu trực tiếp trên máy chủ `Benhviencantho.com`, chống lỗi ảnh trắng và 403 Hotlink.
- **Nhúng Video TikTok chính chủ:** Tự động gắn đoạn mã trình phát TikTok chính thức của `@bvquoctesis` vào cuối bài viết.
- **Tự động hóa 24/7 qua GitHub Actions:** Chạy định kỳ mỗi 2 tiếng/lần trên đám mây GitHub.

---

## 🚀 Hướng Dẫn Triển Khai Lên GitHub (Chỉ Mất 3 Phút)

### Bước 1: Tạo Kho Lưu Trữ (Repository) Mới Trên GitHub
1. Truy cập [GitHub.com](https://github.com/new) -> Bấm **New Repository**.
2. Đặt tên Repo: `benhviencantho-auto-sync` (hoặc tên tùy thích).
3. Chọn **Private** (bảo mật code) hoặc **Public** -> Bấm **Create repository**.

### Bước 2: Đẩy Mã Nguồn Lên GitHub
Copy toàn bộ các file trong thư mục này (`main.py`, `requirements.txt`, `README.md` và thư mục `.github/workflows/auto_post.yml`) tải lên repository vừa tạo.

### Bước 3: Cấu Hình 4 Biến Bảo Mật (GitHub Secrets)
Vào **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret** để thêm 4 biến sau:

| Tên Secret (Name) | Giá Trị (Secret Value) | Giải Thích |
| :--- | :--- | :--- |
| **`GEMINI_API_KEY`** | `AIzaSy...` | API Key miễn phí từ Google AI Studio (`aistudio.google.com`). |
| **`WP_URL`** | `https://benhviencantho.com/wp-json/wp/v2/posts` | Đường dẫn API chính thức của website Benhviencantho.com. |
| **`WP_USERNAME`** | `admin_username` | Tên đăng nhập tài khoản quản trị viên WordPress (Role: Administrator/Author). |
| **`WP_PASSWORD`** | `xxxx xxxx xxxx xxxx` | **Application Password** (Mật khẩu ứng dụng 16 ký tự tạo trong Users -> Profile trên WordPress). |

---

## ⚡ Cách Khởi Chạy Thủ Công Lần Đầu

1. Vào tab **Actions** trên repository GitHub của bạn.
2. Nhấp vào workflow **`Auto Post TikTok to Benhviencantho.com`** ở danh sách bên trái.
3. Bấm nút **Run workflow** -> **Run workflow**.
4. ⏳ Đợi khoảng 2 - 3 phút để hệ thống tự động xuất bản 15 bài y khoa đầu tiên lên `Benhviencantho.com`!

---
*Phát triển bởi Antigravity AI - Nâng tầm giải pháp truyền thông y tế kỹ thuật số.*
