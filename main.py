import os
import re
import time
import requests
import feedparser

# Lấy các biến môi trường (Secrets từ GitHub Actions)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_URL = os.environ.get("WP_URL")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_PASSWORD = os.environ.get("WP_PASSWORD")

# RSS Tự động từ Google Apps Script
RSS_FEED_URL = "https://script.google.com/macros/s/AKfycbwGNOdHsbfP21P3HoLYHr29VgUS0w2YXUW-13WrhMfnxqzqr-CAWP7RJybGSVMzCDkF/exec"

def extract_video_id(url):
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    return None

def get_existing_wp_posts():
    """Lấy danh sách tối đa 300 bài viết (3 trang) đã đăng trên WordPress để tránh trùng lặp 2 lớp"""
    posts_by_id = {}
    seen_titles = {}
    
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        return posts_by_id, seen_titles
        
    try:
        session = requests.Session()
        session.auth = (WP_USERNAME, WP_PASSWORD)
        
        # Quét qua 3 trang đầu tiên (mỗi trang 100 bài) -> Tổng 300 bài mới nhất
        for page in range(1, 4):
            res = session.get(f"{WP_URL}?per_page=100&page={page}", timeout=20)
            if res.status_code == 200:
                posts = res.json()
                if not posts:
                    break
                for p in posts:
                    title = p.get("title", {}).get("rendered", "")
                    content = p.get("content", {}).get("rendered", "")
                    feat_id = p.get("featured_media", 0)
                    post_id = p.get("id")
                    
                    # Trích xuất video_id từ nội dung bài viết
                    vid_match = re.search(r'tiktok\.com/@[^/]+/video/(\d+)', content)
                    vid = vid_match.group(1) if vid_match else None
                    
                    post_info = {
                        "post_id": post_id,
                        "title": title,
                        "content": content,
                        "featured_media": feat_id,
                        "vid": vid
                    }
                    
                    if vid:
                        posts_by_id[vid] = post_info
                    
                    # Lưu lại title gốc đã được dọn sạch để đối chiếu lớp 2
                    clean_title_key = re.sub(r'\[Y Khoa Cần Thơ\]|\s+|#.*$', ' ', title).strip().lower()[:30]
                    seen_titles[clean_title_key] = post_info
            else:
                break
    except Exception as e:
        print(f"⚠️ Lỗi kết nối lấy danh sách WordPress cũ: {e}")
        
    return posts_by_id, seen_titles

def get_available_gemini_models():
    """Tải danh sách model Gemini chính thức có hỗ trợ generateContent"""
    if not GEMINI_API_KEY:
        return []
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            valid_models = []
            for m in data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    model_name = m["name"].replace("models/", "")
                    if "gemini" in model_name.lower():
                        valid_models.append(model_name)
            if valid_models:
                print(f"🤖 Đã tải danh sách model AI chính thức từ Google: {valid_models}")
                return valid_models
        elif res.status_code in [400, 403]:
            print(f"❌ LỖI API KEY GEMINI ({res.status_code}): Secret GEMINI_API_KEY bị sai, hết hạn hoặc bị chặn! Chi tiết: {res.text[:150]}")
    except Exception as e:
        print(f"⚠️ Lỗi kết nối tải danh sách model: {e}")
        
    return [
        "gemini-1.5-flash-001", "gemini-1.5-flash-002", "gemini-1.5-flash",
        "gemini-1.5-pro-001", "gemini-1.5-pro-002", "gemini-1.5-pro",
        "gemini-pro", "gemini-1.0-pro-001", "gemini-1.0-pro"
    ]

def get_fresh_cover_by_video_id(video_id):
    """Lấy lại link ảnh bìa mới nhất từ 3 nguồn API (TikWM Single, oEmbed, TikWM Posts) cho video_id nếu link cũ bị hết hạn"""
    if not video_id:
        return None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}
    
    # Phương pháp 1: Gọi TikWM API cho riêng Video ID
    try:
        r1 = requests.get(f"https://www.tikwm.com/api/?url=https://www.tiktok.com/@bvquoctesis/video/{video_id}", headers=headers, timeout=12)
        if r1.status_code == 200:
            d1 = r1.json().get("data", {})
            c1 = d1.get("origin_cover") or d1.get("cover")
            if c1 and "http" in c1:
                return c1
    except Exception as e:
        pass

    # Phương pháp 2: Gọi TikTok oEmbed chính thức
    try:
        r2 = requests.get(f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@bvquoctesis/video/{video_id}", headers=headers, timeout=12)
        if r2.status_code == 200:
            c2 = r2.json().get("thumbnail_url")
            if c2 and "http" in c2:
                return c2
    except Exception as e:
        pass

    # Phương pháp 3: Quét qua danh sách video mới nhất trên kênh
    try:
        cursor = 0
        for _ in range(8):
            r3 = requests.get(f"https://www.tikwm.com/api/user/posts?unique_id=bvquoctesis&count=50&cursor={cursor}", headers=headers, timeout=15)
            if r3.status_code == 200:
                d3 = r3.json().get("data", {})
                for v in d3.get("videos", []):
                    if str(v.get("video_id")) == str(video_id):
                        c3 = v.get("origin_cover") or v.get("cover")
                        if c3 and "http" in c3:
                            return c3
                cursor = d3.get("cursor", 0)
                if not cursor or not d3.get("has_more"):
                    break
    except Exception as e:
        pass
        
    return None

def upload_image_to_wp(image_url, video_id=None):
    """
    Tải ảnh từ link TikTok CDN (trích xuất từ RSS description/enclosure hoặc gọi tự động qua Video ID)
    vè upload thẳng lên thư viện Media của Benhviencantho.com để làm ảnh đại diện (featured_media).
    """
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        return None, None
        
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/"
    }
    
    img_res = None
    if image_url:
        try:
            img_res = requests.get(image_url, headers=headers, timeout=20)
        except Exception as e:
            pass
            
    # Nếu tải từ link cũ (trong RSS) bị lỗi HTTP != 200 (như 403 Hết hạn), lập tức lấy link gốc từ 3 nguồn API đa tầng!
    if (not img_res or img_res.status_code != 200) and video_id:
        print(f"🔄 Link ảnh cũ của video {video_id} bị hết hạn/lỗi. Đang tự động lấy link gốc chất lượng cao từ 3 nguồn API đa tầng...")
        fresh_url = get_fresh_cover_by_video_id(video_id)
        if fresh_url:
            try:
                img_res = requests.get(fresh_url, headers=headers, timeout=20)
            except Exception as e:
                pass
                
    if not img_res or img_res.status_code != 200:
        print(f"⚠️ Không thể tải ảnh từ TikTok cho video {video_id} sau khi đã thử tất cả 3 nguồn API.")
        return None, None
        
    try:
        media_url = WP_URL.replace("/posts", "/media")
        filename = f"benh-vien-can-tho-sis-y-khoa-{video_id or int(time.time())}.jpg"
        wp_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg"
        }
        media_res = session.post(media_url, headers=wp_headers, data=img_res.content, timeout=30)
        
        if media_res.status_code in [200, 201]:
            media_data = media_res.json()
            media_id = media_data.get("id")
            source_url = media_data.get("source_url")
            print(f"📸 Đã lưu ảnh thành công lên máy chủ Benhviencantho.com (ID: {media_id}): {source_url}")
            return media_id, source_url
        else:
            print(f"⚠️ Lỗi upload ảnh lên WordPress Media ({media_res.status_code}): {media_res.text[:100]}")
    except Exception as e:
        print(f"⚠️ Lỗi xử lý ảnh media: {e}")
        
    return None, None

def update_wp_post_featured_media(post_id, media_id, local_img_url=None):
    """Cập nhật bổ sung ảnh đại diện và thay thế link ảnh lỗi/hết hạn trong bài viết cũ"""
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD or not post_id or not media_id:
        return False
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    session.headers.update({"Content-Type": "application/json"})
    
    payload = {"featured_media": media_id}
    
    if local_img_url:
        try:
            res = session.get(f"{WP_URL}/{post_id}", timeout=20)
            if res.status_code == 200:
                current_content = res.json().get("content", {}).get("rendered", "")
                
                # Cập nhật thay thế tât cả các link ảnh tiktokcdn cũ bị hết hạn thành ảnh nội bộ
                if "tiktokcdn" in current_content or "tikwm" in current_content:
                    updated_content = re.sub(r'<img[^>]+src=["\']https?://[^"\']*(tiktokcdn|tikwm)[^"\']*["\'][^>]*>', '', current_content)
                    
                    img_html = f'<p style="text-align: center; margin: 20px 0;"><img src="{local_img_url}" alt="Bệnh viện Cần Thơ" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></p>\n'
                    payload["content"] = img_html + updated_content
        except Exception as e:
            pass
            
    try:
        res = session.post(f"{WP_URL}/{post_id}", json=payload, timeout=20)
        if res.status_code in [200, 201]:
            print(f"✅ Đã chữa lành bài viết ID {post_id}: Đính kèm ảnh đại diện mới thành công!")
            return True
    except Exception as e:
        pass
    return False

def generate_seo_article(title, url, video_id, local_img_url, models_list):
    if not GEMINI_API_KEY:
        print("❌ LỖI: Chưa có GEMINI_API_KEY trong cấu hình Secrets.")
        return None
        
    prompt = f"""
Bạn là Bác sĩ Chuyên khoa & Biên tập viên Y tế Cao cấp thuộc Cổng thông tin Y khoa miền Tây "Bệnh Viện Cần Thơ" (Website: https://benhviencantho.com/ & Bệnh viện Đa khoa Quốc tế S.I.S Cần Thơ).

Hãy viết một bài phân tích y khoa & tư vấn chăm sóc sức khỏe CHUẨN SEO GOOGLE E-E-A-T (Chuyên môn - Thẩm quyền - Tin cậy) dài khoảng 1000 - 1200 từ dựa trên video TikTok chuyên môn sau:
- Tiêu đề chia sẻ y khoa: {title}
- Link video tham chiếu: {url}

QUY TẮC TỐI ƯU SEO & HIỂN THỊ Y KHOA:
1. Từ khóa chính: Trích xuất ngay 1 từ khóa y khoa cốt lõi nhất từ tiêu đề (ví dụ: "Đột quỵ", "Suy tim", "Phình mạch máu não", "Đau dạ dày") và phải xuất hiện tự nhiên ít nhất 4-5 lần trải đều toàn bài.
2. Phải lập tự động 4 nhóm từ khóa ngách (Niche Keyword Matrix): Dựa vào chuyên khoa/chủ đề cụ thể của video (Đột quỵ, Tim mạch, Thần kinh, Cơ xương khớp, Thận niệu...), bạn BẮT BUỘC phải tự tổng hợp và lồng ghép thật tự nhiên (đúng ngữ cảnh y khoa, câu cú mượt mà) đầy đủ 4 nhóm từ khóa ngách sau vào các thẻ H2/H3 hoặc đoạn nội dung:
   - Nhóm Bệnh viện/Phòng khám: "bệnh viện đa khoa quốc tế SIS Cần Thơ", "bệnh viện Cần Thơ", "phòng khám chuyên khoa Cần Thơ", "bác sĩ giỏi Cần Thơ".
   - Nhóm Xét nghiệm/Tầm soát: "chụp MRI 3 Tesla", "tầm soát đột quỵ", "khám tổng quát", "xét nghiệm máu", "siêu âm mạn tính".
   - Nhóm Cấp cứu/Điều trị: "cấp cứu đột quỵ", "can thiệp mạch máu não", "phẫu thuật thần kinh", "cấp cứu 24/7", "điều trị nội khoa".
   - Nhóm Vị trí địa lý (Local SEO): "miền Tây", "Đồng bằng sông Cửu Long", "Cần Thơ", "Hậu Giang", "Vĩnh Long", "An Giang".

TIÊU CHUẨN BỐ CỤC & VĂN PHONG Y KHOA:
- Sử dụng HTML semantic: Có <h1> (tuyệt đối không trùng tiêu đề bài), ít nhất ba <h2>, và nhiều <h3>.
- Viết văn phong chuyên gia y tế: Lời lẽ thấu cảm, khoa học, trấn an người bệnh, dễ hiểu nhưng học thuật.
- Đoạn mở đầu (Lead paragraph): Gây chú ý bằng thực trạng bệnh lý, nỗi đau của người bệnh và dẫn dắt vào chủ đề chính một cách khoa học.
- Đoạn giữa (Body): Giải thích cặn kẽ cơ chế bệnh sinh, nguyên nhân, triệu chứng cảnh báo sớm, và giải pháp phòng ngừa/điều trị (luôn nhắc đến tầm quan trọng của việc thăm khám sớm tại cơ sở y tế uy tín).
- KHÔNG BAO GIỜ viết những cụm từ như: "Dưới đây là bài viết...", "Trong video này...", "Theo tiêu đề...". Viết thẳng vào vấn đề y khoa.

BỐ CỤC BẮT BUỘC (Sử dụng trực tiếp HTML):
1. [Nội dung chuyên sâu
