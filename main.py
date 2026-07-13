import os
import re
import json
import time
import base64
import requests
import feedparser

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_URL = os.environ.get("WP_URL")
WP_USERNAME = os.environ.get("WP_USERNAME")
WP_PASSWORD = os.environ.get("WP_PASSWORD")

# !!! ĐƯỜNG LINK RSS KÊNH TIKTOK DÀNH CHO BENHVIENCANTHO.COM !!!
RSS_FEED_URL = "https://script.google.com/macros/s/AKfycbwGNOdHsbfP21P3HoLYHr29VgUS0w2YXUW-13WrhMfnxqzqr-CAWP7RJybGSVMzCDkF/exec"

def get_existing_wp_posts():
    """
    Trả về danh sách bài viết cũ kèm thông tin ID, featured_media và tiêu đề chuẩn hóa để đối chiếu.
    1. Chống lặp bài 2 lớp: Kiểm tra trùng theo cả Video ID lẫn Tiêu đề bài viết.
    2. Tự động dọn dẹp bài trùng lặp: Nếu phát hiện trên website có 2-3 bài bị trùng tiêu đề,
       hệ thống tự động xóa bài trùng (giữ lại bài gốc đầu tiên) để làm sạch website.
    3. Phục hồi ảnh: Nếu bài gốc bị mất ảnh (featured_media == 0), tự động cập nhật lại ảnh.
    """
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        print("❌ Lỗi cấu hình: Thiếu biến Secret WP_URL, WP_USERNAME hoặc WP_PASSWORD.")
        return {}, {}
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    posts_by_id = {}
    seen_titles_map = {}
    
    try:
        total_fetched = 0
        for page in range(1, 4):
            res = session.get(f"{WP_URL}?per_page=100&page={page}", timeout=20)
            if res.status_code == 200:
                posts = res.json()
                if not posts:
                    break
                total_fetched += len(posts)
                
                for p in posts:
                    content = p.get("content", {}).get("rendered", "")
                    title = p.get("title", {}).get("rendered", "")
                    post_id = p.get("id")
                    featured_media = p.get("featured_media", 0)
                    
                    # Chuẩn hóa tiêu đề để so sánh chính xác (chỉ lấy 30 ký tự đầu không dấu/không tag)
                    clean_title_key = re.sub(r'\[Y Khoa Cần Thơ\]|\s+|#.*$', ' ', title).strip().lower()[:30]
                    
                    # 💡 TỰ ĐỘNG DỌN DẸP BÀI TRÙNG LẶP CŨ TRÊN WORDPRESS:
                    if clean_title_key and clean_title_key in seen_titles_map:
                        print(f"🗑️ Phát hiện bài viết bị lặp lại trên web (ID {post_id}: '{title[:40]}...') -> Đang tự động dọn dẹp xóa bỏ...")
                        try:
                            del_res = session.delete(f"{WP_URL}/{post_id}?force=true", timeout=15)
                            if del_res.status_code in [200, 201]:
                                print(f"✅ Đã dọn dẹp thành công bài viết trùng lặp ID {post_id}.")
                                continue
                        except Exception as err:
                            print(f"⚠️ Lỗi khi xóa bài trùng ID {post_id}: {err}")
                    
                    # Tìm Video ID trong nội dung hoặc tiêu đề
                    vid = None
                    for match in re.finditer(r'/video/(\d+)|data-video-id=["\'](\d+)["\']', content + title):
                        vid = match.group(1) or match.group(2)
                        if vid:
                            break
                            
                    post_data = {"post_id": post_id, "featured_media": featured_media, "title": title, "content": content, "vid": vid}
                    
                    if clean_title_key:
                        seen_titles_map[clean_title_key] = post_data
                    if vid:
                        posts_by_id[vid] = post_data
            elif res.status_code == 400 and "rest_post_invalid_page_number" in res.text:
                break
            elif res.status_code == 401:
                print("❌ LỖI 401 WORDPRESS (KHI ĐỌC BÀI): Sai Username hoặc Application Password!")
                break
            else:
                print(f"⚠️ Trang {page}: Không thể đọc danh sách bài từ WordPress ({res.status_code})")
                break
                
        print(f"📚 Đã kết nối WordPress Benhviencantho.com thành công. Đang quản lý {total_fetched} bài viết trên web.")
        return posts_by_id, seen_titles_map
    except Exception as e:
        print(f"⚠️ Lỗi kết nối kiểm tra bài đăng cũ: {e}")
    return {}, {}

def get_available_gemini_models():
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
    """Lấy lại link ảnh bìa mới nhất từ API TikWM/TikTok cho video_id nếu link cũ trong RSS bị hết hạn (403)"""
    if not video_id:
        return None
    try:
        for cursor in [0, 1779879600001, 1776304800001]:
            url = f"https://www.tikwm.com/api/user/posts?unique_id=bvquoctesis&count=36&cursor={cursor}"
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}, timeout=15)
            if res.status_code == 200:
                data = res.json().get("data", {})
                for v in data.get("videos", []):
                    if str(v.get("video_id")) == str(video_id):
                        return v.get("origin_cover") or v.get("cover")
                if not data.get("has_more"):
                    break
    except Exception as e:
        print(f"⚠️ Lỗi tìm ảnh mới cho video {video_id}: {e}")
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
            
    # Nếu tải từ link cũ (trong RSS) bị lỗi HTTP != 200 (như 403 Hết hạn), tự động lấy link gốc mới từ TikWM bằng video_id!
    if (not img_res or img_res.status_code != 200) and video_id:
        print(f"🔄 Link ảnh trong RSS của video {video_id} bị hết hạn/lỗi (Status {img_res.status_code if img_res else 'Failed'}). Đang tự động lấy link ảnh mới từ API...")
        fresh_url = get_fresh_cover_by_video_id(video_id)
        if fresh_url:
            try:
                img_res = requests.get(fresh_url, headers=headers, timeout=20)
            except Exception as e:
                pass
                
    if not img_res or img_res.status_code != 200:
        print(f"⚠️ Không thể tải ảnh từ TikTok cho video {video_id} (Status {img_res.status_code if img_res else 'Failed'})")
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
    try:
        payload = {"featured_media": media_id}
        if local_img_url:
            get_res = session.get(f"{WP_URL}/{post_id}", timeout=15)
            if get_res.status_code == 200:
                old_content = get_res.json().get("content", {}).get("rendered", "")
                if "tiktokcdn" in old_content or "<img" not in old_content:
                    new_img_tag = f'<p style="text-align: center; margin: 20px 0;"><img src="{local_img_url}" alt="Bệnh viện Cần Thơ S.I.S" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></p>\n'
                    if re.search(r'<img[^>]+src=["\'][^"\']*tiktokcdn[^"\']*["\'][^>]*>', old_content):
                        new_content = re.sub(r'<img[^>]+src=["\'][^"\']*tiktokcdn[^"\']*["\'][^>]*>', f'<img src="{local_img_url}" alt="Bệnh viện Cần Thơ S.I.S" style="max-width: 100%; border-radius: 12px;" />', old_content)
                    else:
                        new_content = new_img_tag + old_content
                    payload["content"] = new_content
                    
        res = session.post(f"{WP_URL}/{post_id}", json=payload, timeout=20)
        if res.status_code in [200, 201]:
            print(f"✅ ĐÃ TỰ ĐỘNG BỔ SUNG ẢNH ĐẠI DIỆN VÀ KHẮC PHỤC ẢNH MINH HỌA CHO BÀI VIẾT CŨ (ID: {post_id}, Media ID: {media_id})")
            return True
    except Exception as e:
        print(f"⚠️ Lỗi cập nhật ảnh cho bài viết cũ: {e}")
    return False

def extract_video_id(url):
    match = re.search(r'/video/(\d+)', url)
    return match.group(1) if match else None

def generate_seo_article(title, url, video_id, local_img_url, models_list):
    if not GEMINI_API_KEY:
        print("❌ LỖI NGHIÊM TRỌNG: Chưa cấu hình Secret GEMINI_API_KEY trên GitHub!")
        return None
        
    prompt = f"""
Bạn là Bác sĩ Chuyên khoa & Biên tập viên Y tế Cao cấp thuộc Cổng thông tin Y khoa miền Tây "Bệnh Viện Cần Thơ" (Website: https://benhviencantho.com/ & Bệnh viện Đa khoa Quốc tế S.I.S Cần Thơ).

Hãy viết một bài phân tích y khoa & tư vấn chăm sóc sức khỏe CHUẨN SEO GOOGLE E-E-A-T (Chuyên môn - Thẩm quyền - Tin cậy) dài khoảng 1000 - 1200 từ dựa trên video TikTok chuyên môn sau:
- Tiêu đề chia sẻ y khoa: {title}
- Link video gốc từ Bác sĩ: {url}
- Link ảnh minh họa chính thức (đã lưu trên WordPress): {local_img_url or ''}

CHIẾN LƯỢC TỐI ƯU TỪ KHÓA NGÁCH CHUYÊN SÂU (BẮT BUỘC TUÂN THỦ 100%):
1. Từ khóa chính (Primary Keyword): "Bệnh viện Cần Thơ" (phải xuất hiện ngay trong 2 câu đầu tiên của bài viết và bôi đậm <strong>Bệnh viện Cần Thơ</strong>, lặp lại tự nhiên 4 - 5 lần xuyên suốt các đoạn).
2. Phối lặp tự động 4 nhóm từ khóa ngách (Niche Keyword Matrix): Dựa vào chuyên khoa/chủ đề cụ thể của video (Đột quỵ, Tim mạch, Thần kinh, Cơ xương khớp, Thận niệu...), bạn BẮT BUỘC phải tự tổng hợp và lồng ghép thật tự nhiên (đúng ngữ cảnh y khoa, câu cú mượt mà) đầy đủ 4 nhóm từ khóa ngách sau vào các thẻ H2/H3 hoặc đoạn nội dung:
   - NHÓM 1 (Dịch vụ / Chuyên khoa + Địa phương): [Tên bệnh / Dịch vụ / Phương pháp liên quan video] + [tại / ở đâu] + [Cần Thơ / Miền Tây]. (Ví dụ: tầm soát đột quỵ ở đâu Cần Thơ, khám tim mạch tại miền Tây, chụp MRI mạch máu não ở Cần Thơ, điều trị đau đầu tại Cần Thơ...). -> Phân bổ ở H2 đầu tiên hoặc đoạn giải thích triệu chứng.
   - NHÓM 2 (Giải đáp Chi phí & BHYT): [Chi phí / Bảng giá / BHYT] + [Tên dịch vụ / Tên bệnh viện]. (Ví dụ: chi phí chụp MRI Bệnh viện SIS Cần Thơ, khám BHYT tại Bệnh viện Cần Thơ có được thanh toán không, bảng giá tầm soát đột quỵ...). -> Phân bổ ở một thẻ H2 chuyên biệt hoặc mục giải đáp chi phí.
   - NHÓM 3 (Thương hiệu chuyên gia): [Bác sĩ] + [Chuyên khoa liên quan] + [giỏi / uy tín] + [Cần Thơ]. (Ví dụ: bác sĩ tim mạch giỏi Cần Thơ, TS.BS Trần Chí Cường - bác sĩ thần kinh uy tín Cần Thơ, bác sĩ đột quỵ giỏi miền Tây...). -> Phân bổ trong phần lời khuyên chuyên gia hoặc giới thiệu đội ngũ bác sĩ.
   - NHÓM 4 (Tiện ích & Hướng dẫn thủ tục): [hướng dẫn đặt lịch khám / thủ tục khám BHYT / xe đưa đón người bệnh / giờ làm việc] + Bệnh viện Cần Thơ. -> Phân bổ ở phần hướng dẫn đi khám hoặc trong H2 Hỏi đáp nhanh.
3. Định dạng từ khóa (Keyword Highlighting): BẮT BUỘC bôi đậm bằng thẻ <strong>...</strong> cho từ khóa chính và ít nhất 5 từ khóa ngách đại diện cho 4 nhóm trên khi chúng xuất hiện trong bài để Google Bot dễ dàng nhận diện cấu trúc E-E-A-T.

TIÊU CHUẨN BỐ CỤC & VĂN PHONG Y KHOA:
- Văn phong: Khoa học, chuẩn xác về mặt y lý, câu văn mạch lạc, dễ hiểu cho người bệnh, mang tính nhân văn sâu sắc.
- Cấu trúc 4 thẻ H2 chuẩn:
  + H2 số 1: Nhận biết sớm [Tên bệnh/chủ đề] & Khám [Dịch vụ/Chuyên khoa] ở đâu Cần Thơ?
  + H2 số 2: Phân tích chuyên môn từ [Bác sĩ Chuyên khoa uy tín Cần Thơ] & Phương pháp điều trị
  + H2 số 3: Chi phí & Hướng dẫn thủ tục khám BHYT tại Bệnh viện Cần Thơ / S.I.S
  + H2 số 4: 💡 Hỏi đáp nhanh cùng Chuyên gia Bệnh Viện Cần Thơ (Benhviencantho.com) (giải đáp 2-3 câu hỏi ngắn gọn thiết thực).
- Bắt buộc dùng danh sách bullet points <ul><li> để liệt kê triệu chứng, lời khuyên vàng và các bước đặt lịch.
- Hình ảnh minh họa chính: BẮT BUỘC chèn đoạn HTML ảnh sau ngay dưới đoạn mở đầu (trước thẻ H2 đầu tiên) nếu có Link ảnh minh họa chính thức:
<p style="text-align: center; margin: 20px 0;"><img src="{local_img_url or ''}" alt="Bệnh viện Cần Thơ - {title}" style="max-width: 100%; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></p>
- Trình phát video chính thức: Ở cuối cùng bài viết, BẮT BUỘC chèn chính xác đoạn mã HTML nhúng video TikTok gốc sau để người đọc kiểm chứng lời Bác sĩ:
<hr><h3 style="text-align: center; color: #0056b3;">🎬 Xem chia sẻ trực tiếp từ Bác sĩ Bệnh viện S.I.S Cần Thơ tại đây:</h3>
<div style="display: flex; justify-content: center; margin: 25px auto;">
  <blockquote class="tiktok-embed" cite="https://www.tiktok.com/@bvquoctesis/video/{video_id}" data-video-id="{video_id}" style="max-width: 360px; min-width: 325px; border-radius: 16px; box-shadow: 0 8px 25px rgba(0,0,0,0.15); overflow: hidden;">
    <section><a target="_blank" href="https://www.tiktok.com/@bvquoctesis">@bvquoctesis</a></section>
  </blockquote>
</div>
<script async src="https://www.tiktok.com/embed.js"></script>

QUY ĐỊNH KỸ THUẬT: Trả về HOÀN TOÀN bằng mã HTML thuần (<p>, <h2>, <ul>...). KHÔNG bọc trong định dạng JSON hay markdown ```html.
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
        "title": f"[Y Khoa Cần Thơ] {clean_title[:65]}",
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
        if posted_count >= 15:
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
