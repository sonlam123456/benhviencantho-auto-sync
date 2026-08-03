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
        print("❌ LỖI NGHIÊM TRỌNG: Chưa cấu hình Secret GEMINI_API_KEY trên GitHub!")
        return None
        
    prompt = f"""
Bạn là Bác sĩ Chuyên khoa & Biên tập viên Y tế Cao cấp thuộc Cổng thông tin Y khoa miền Tây "Bệnh Viện Cần Thơ" (Website: https://benhviencantho.com/). Bạn đang ứng dụng kỹ năng "LamContent" - kết hợp giữa Copywriting thuyết phục (khung PAS), SEO Y khoa (E-E-A-T), và Vibe Ái Ngữ (Thấu cảm, chữa lành, không hứa hẹn suông).

Hãy viết một bài phân tích y khoa CHUẨN SEO dài 1000 - 1200 từ dựa trên video TikTok sau:
- Tiêu đề video: {title}
- Link video gốc: {url}
- Link ảnh minh họa: {local_img_url or ''}

CẤU TRÚC BÀI VIẾT BẮT BUỘC (TUÂN THỦ LAMCONTENT & PAS):
- H1: <h1 style="color: #0056b3; font-size: 24px;">[Tiêu đề thu hút, đồng cảm với bệnh nhân]</h1> (KHÔNG TRÙNG tiêu đề video).
- Đoạn mở đầu (Pain - Nỗi đau & Ái ngữ): Thấu cảm sâu sắc với nỗi lo lắng, sự mệt mỏi của bệnh nhân khi đối mặt với triệu chứng này. Tránh Toxic Positivity (không nói "đừng lo lắng", hãy nói "chúng tôi hiểu sự mệt mỏi của bạn"). Nhắc đến "Bệnh viện Cần Thơ" ngay trong 2 câu đầu tiên (bôi đậm <strong>Bệnh viện Cần Thơ</strong>).
- H2 số 1 (Agitate - Xoáy sâu & Chuyên môn E-E-A-T): Giải thích cặn kẽ cơ chế bệnh sinh theo video. Phân tích hậu quả nếu trì hoãn thăm khám. Lồng ghép từ khóa: [Dịch vụ/Bệnh] + [ở đâu / tại Cần Thơ].
- H2 số 2 (Solution - Giải pháp chữa lành): Phân tích hướng điều trị, khích lệ bệnh nhân bằng năng lượng bình an. Lồng ghép từ khóa: Bác sĩ giỏi Cần Thơ.
- H2 số 3: Chi phí & Hướng dẫn thủ tục BHYT tại Bệnh viện S.I.S Cần Thơ.

QUY TẮC LAMCONTENT & SEO (MANDATORY RULE):
1. TRẢ LỜI THẲNG BẰNG HTML THUẦN TÚY (<h2>, <p>, <ul>). KHÔNG dùng markdown ```html.
2. KHÔNG GIỚI THIỆU (như "Dưới đây là bài viết..."), KHÔNG GIẢI THÍCH thêm ở cuối bài.
3. Từ khóa: Phải lặp lại tự nhiên các cụm "Bệnh viện Cần Thơ", "S.I.S Cần Thơ", "tầm soát đột quỵ", "khám tổng quát", "bác sĩ giỏi miền Tây", "chụp MRI 3 Tesla". Bôi đậm <strong> cho ít nhất 5 từ khóa ngách.
4. Hình ảnh minh họa: BẮT BUỘC chèn đoạn mã này ngay dưới H1:
<p style="text-align: center; margin: 20px 0;"><img src="{local_img_url or ''}" alt="Bệnh viện Cần Thơ - {title}" style="max-width: 100%; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></p>
5. Kêu gọi hành động (CTA) bằng Ái Ngữ: Cuối bài, BẮT BUỘC bọc khối HTML sau để khuyên bệnh nhân đặt lịch:
<div style="background-color: #f8fcfd; border-left: 5px solid #0056b3; padding: 20px; margin-top: 30px; border-radius: 4px;">
    <h3 style="color: #0056b3; margin-top: 0;">Bệnh Viện Cần Thơ - Đồng Hành Cùng Bạn Trên Hành Trình Chữa Lành</h3>
    <p>Sức khỏe là tài sản quý giá nhất, và chúng tôi thấu hiểu những lo âu của bạn khi cơ thể lên tiếng. Đừng tự gồng gánh nỗi đau một mình. Tại <strong>Bệnh viện Đa khoa Quốc tế S.I.S Cần Thơ</strong>, đội ngũ y bác sĩ tận tâm cùng hệ thống máy móc hiện đại (MRI 3 Tesla, CT 128) luôn sẵn sàng lắng nghe và tìm ra giải pháp tốt nhất cho bạn.</p>
    <ul style="list-style-type: none; padding-left: 0;">
        <li>📍 <strong>Địa chỉ:</strong> 397 Nguyễn Văn Cừ nối dài, P. An Bình, Q. Ninh Kiều, Cần Thơ</li>
        <li>🌐 <strong>Website:</strong> <a href="https://benhviencantho.com/" style="text-decoration: none; color: #0056b3;">benhviencantho.com</a></li>
        <li>📞 <strong>Tổng đài tư vấn miễn phí:</strong> 1800 1115</li>
    </ul>
</div>
6. Nhúng Video Gốc: Cuối cùng, BẮT BUỘC chèn mã HTML nhúng video sau:
<div style="display: flex; justify-content: center; margin: 25px auto;">
  <blockquote class="tiktok-embed" cite="https://www.tiktok.com/@bvquoctesis/video/{video_id}" data-video-id="{video_id}" style="max-width: 360px; min-width: 325px; border-radius: 16px;">
    <section><a target="_blank" href="https://www.tiktok.com/@bvquoctesis">@bvquoctesis</a></section>
  </blockquote>
</div><script async src="https://www.tiktok.com/embed.js"></script>
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for model in models_list:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(2):
            try:
                res = requests.post(api_url, json=payload, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        html_content = data["candidates"][0]["content"]["parts"][0]["text"]
                        html_content = re.sub(r'^```html\n|```$', '', html_content, flags=re.MULTILINE).strip()
                        return html_content
                elif res.status_code == 503:
                    print(f"⚠️ Model {model} hơi nghẽn mạng (503), chờ 5s thử lại...")
                    time.sleep(5)
                elif res.status_code == 429:
                    print(f"⚠️ Model {model} bị giới hạn tần suất (429 Quota Exceeded), chờ 10s...")
                    time.sleep(10)
                elif res.status_code == 404:
                    print(f"⚠️ Model {model} không tìm thấy (404), đang thử model tiếp theo...")
                    break
                elif res.status_code in [400, 403]:
                    print(f"❌ LỖI API KEY GEMINI ({res.status_code}): Secret GEMINI_API_KEY bị sai, hết hạn hoặc không hợp lệ!")
                    return None
                else:
                    print(f"⚠️ Model {model} báo lỗi ({res.status_code}): {res.text[:150]}")
                    break
            except Exception as e:
                print(f"⚠️ Lỗi kết nối model {model}: {e}")
                time.sleep(3)
            
    print("❌ Không thể tạo bài viết từ AI Gemini sau khi đã thử tất cả các model.")
    return None

def create_wp_post(clean_title, content, media_id=None, local_img_url=None):
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        print("❌ Lỗi: Chưa cấu hình đủ Secrets WordPress.")
        return False
        
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    session.headers.update({"Content-Type": "application/json"})
    
    final_content = content
    if local_img_url and local_img_url not in content:
        img_html = f'<p style="text-align: center; margin: 20px 0;"><img src="{local_img_url}" alt="Bệnh viện Cần Thơ - {clean_title[:50]}" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></p>\n'
        final_content = img_html + content
        
    payload = {
        "title": clean_title[:80], # Bỏ tiền tố [Y Khoa Cần Thơ]
        "content": final_content,
        "status": "publish"
    }
    if media_id:
        payload["featured_media"] = media_id
        
    try:
        res = session.post(WP_URL, json=payload, timeout=30)
        if res.status_code in [200, 201]:
            print(f"✅ ĐÃ ĐĂNG THÀNH CÔNG BÀI LÊN BENHVIENCANTHO.COM: {clean_title[:55]} (Media ID: {media_id})")
            return True
        elif res.status_code == 401:
            print("❌ LỖI 401 WORDPRESS: Tài khoản trong Secret WP_USERNAME không có quyền đăng bài (Role phải là Administrator hoặc Author)!")
            return False
        else:
            print(f"❌ Lỗi đăng WordPress ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"❌ Lỗi kết nối WordPress: {e}")
        return False

def main():
    print(f"🔍 Đang tải danh sách video từ RSS Benhviencantho.com: {RSS_FEED_URL}")
    
    try:
        rss_res = requests.get(RSS_FEED_URL, timeout=15)
        if rss_res.status_code != 200:
            print(f"❌ LỖI NGHIÊM TRỌNG: Link RSS trả về mã lỗi HTTP {rss_res.status_code}!")
            return
    except Exception as e:
        print(f"❌ Lỗi không thể kết nối đến link RSS: {e}")
        return

    feed = feedparser.parse(rss_res.content)
    if not feed.entries:
        print("❌ LỖI NGHIÊM TRỌNG: Link RSS không chứa video nào (Danh sách trống)!")
        return
        
    print(f"🎯 Tìm thấy {len(feed.entries)} video trong link RSS của Benhviencantho.com.")
    posts_by_id, seen_titles_map = get_existing_wp_posts()
    
    models_list = get_available_gemini_models()
    if not models_list:
        print("❌ Lỗi: Không có model AI nào khả dụng cho API Key của bạn.")
        return
    
    posted_count = 0
    updated_image_count = 0
    
    # 🛠️ QUÉT VÀ TỰ ĐỘNG KHÔI PHỤC ẢNH CHO CÁC BÀI VIẾT CŨ TRÊN WORDPRESS (Sửa tối đa 100 bài/lần chạy)
    print(f"🛠️ Đang quét tự động danh sách bài viết cũ trên Benhviencantho.com để phát hiện & sửa triệt để lỗi ảnh...")
    checked_ids = set()
    for post_info in list(posts_by_id.values()) + list(seen_titles_map.values()):
        if updated_image_count >= 100:
            print("🛑 Đã sửa khôi phục 100 bài viết trong 1 lượt chạy (giới hạn an toàn). Các bài lỗi còn lại sẽ tự khôi phục tiếp ở lượt chạy sau.")
            break
        post_id = post_info["post_id"]
        if post_id in checked_ids:
            continue
        checked_ids.add(post_id)
        
        feat_id = post_info.get("featured_media", 0)
        content = post_info.get("content", "")
        title = post_info.get("title", "")
        vid = post_info.get("vid")
        
        # Nếu bài viết không có ảnh đại diện HOẶC trong nội dung có link tiktokcdn bị lỗi/hết hạn
        if feat_id == 0 or "tiktokcdn" in content:
            print(f"🛠️ Phát hiện bài viết ID {post_id} ('{title[:35]}...') bị lỗi/mất ảnh -> Đang tự động khôi phục từ TikWM API...")
            media_id, local_url = upload_image_to_wp("", vid)
            if media_id and update_wp_post_featured_media(post_id, media_id, local_url):
                updated_image_count += 1
                post_info["featured_media"] = media_id
                time.sleep(1.5)
    
    for entry in feed.entries:
        if posted_count >= 2:
            print("🛑 Đã đạt giới hạn đăng 2 bài viết mới mỗi lượt chạy (3 lần/ngày = 6 bài/ngày). Dừng viết bài mới.")
            break
        url = getattr(entry, 'link', '')
        title = getattr(entry, 'title', '')
        video_id = extract_video_id(url)
        
        # 🎯 TRÍCH XUẤT THUMBNAIL TỪ DESCRIPTION HOẶC ENCLOSURES
        thumbnail_url = ""
        if hasattr(entry, 'media_thumbnail') and len(entry.media_thumbnail) > 0:
            thumbnail_url = entry.media_thumbnail[0]['url']
        elif hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
            thumbnail_url = entry.enclosures[0]['url']
            
        if not thumbnail_url:
            desc_text = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            match_img = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', desc_text, re.IGNORECASE)
            if match_img:
                thumbnail_url = match_img.group(1)
                
        if not video_id:
            continue
            
        # Chuẩn hóa tiêu đề từ RSS để đối chiếu 2 lớp
        entry_title_key = re.sub(r'\[Y Khoa Cần Thơ\]|\s+|#.*$', ' ', title).strip().lower()[:30]
        
        # 🛡️ KIỂM TRA TRÙNG LẶP 2 LỚP: Nếu trùng Video ID HOẶC trùng Tiêu đề bài viết -> Bỏ qua ngay!
        if video_id in posts_by_id:
            old_post = posts_by_id[video_id]
            if old_post.get("featured_media", 0) == 0 and updated_image_count < 100:
                print(f"🛠️ Phát hiện bài viết cũ '{title[:35]}...' bị mất ảnh đại diện -> Đang tải bổ sung ảnh gốc...")
                media_id, local_url = upload_image_to_wp(thumbnail_url, video_id)
                if media_id and update_wp_post_featured_media(old_post["post_id"], media_id, local_url):
                    updated_image_count += 1
                    time.sleep(2)
            else:
                print(f"⏩ Video ID {video_id} ('{title[:30]}...') đã tồn tại trên web & đã có ảnh, bỏ qua.")
            continue
        elif entry_title_key and entry_title_key in seen_titles_map:
            old_post = seen_titles_map[entry_title_key]
            print(f"⏩ Bài viết có tiêu đề '{title[:35]}...' đã tồn tại trên web (ID {old_post['post_id']}), bỏ qua để chống trùng lặp.")
            if old_post.get("featured_media", 0) == 0 and updated_image_count < 100:
                media_id, local_url = upload_image_to_wp(thumbnail_url, video_id)
                if media_id and update_wp_post_featured_media(old_post["post_id"], media_id, local_url):
                    updated_image_count += 1
                    time.sleep(2)
            continue
            
        print(f"✍️ Đang viết bài y khoa chuẩn SEO cho video mới: {title[:50]}...")
        media_id, local_img_url = upload_image_to_wp(thumbnail_url, video_id)
        
        article_html = generate_seo_article(title, url, video_id, local_img_url, models_list)
        if article_html:
            if create_wp_post(title, article_html, media_id, local_img_url):
                posted_count += 1
            time.sleep(5)
            
    print(f"ℹ️ Hoàn tất chạy! Kết quả: Đăng mới {posted_count} bài viết, và Tự động phục hồi ảnh cho {updated_image_count} bài viết cũ.")

if __name__ == "__main__":
    main()
