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
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        print("❌ Lỗi cấu hình: Thiếu biến Secret WP_URL, WP_USERNAME hoặc WP_PASSWORD.")
        return []
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    try:
        res = session.get(f"{WP_URL}?per_page=100", timeout=20)
        if res.status_code == 200:
            posts = res.json()
            print(f"📚 Đã kết nối WordPress Benhviencantho.com thành công. Đang có {len(posts)} bài viết trên web.")
            return [p["content"]["rendered"] for p in posts] + [p["title"]["rendered"] for p in posts]
        elif res.status_code == 401:
            print("❌ LỖI 401 WORDPRESS (KHI ĐỌC BÀI): Sai Username hoặc Application Password!")
        else:
            print(f"⚠️ Không thể đọc danh sách bài cũ từ WordPress (Status {res.status_code}): {res.text[:100]}")
    except Exception as e:
        print(f"⚠️ Lỗi kết nối kiểm tra bài đăng cũ: {e}")
    return []

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

def upload_image_to_wp(image_url):
    """
    Tải ảnh từ link TikTok CDN (trích xuất từ RSS description/enclosure) về và upload thẳng
    lên thư viện Media của Benhviencantho.com để làm ảnh đại diện (featured_media).
    Chống lỗi ảnh trắng (src="") và chống lỗi 403 hotlink từ TikTok CDN.
    """
    if not image_url or not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        return None, None
        
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/"
        }
        img_res = requests.get(image_url, headers=headers, timeout=20)
        if img_res.status_code != 200:
            print(f"⚠️ Không thể tải ảnh gốc từ TikTok (Status {img_res.status_code})")
            return None, None
            
        media_url = WP_URL.replace("/posts", "/media")
        filename = f"benh-vien-can-tho-sis-y-khoa-{int(time.time())}.jpg"
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
                        
                        if local_img_url:
                            full_content = f'<div style="text-align: center; margin-bottom: 25px;"><img src="{local_img_url}" alt="Bệnh viện Cần Thơ - Tư vấn y khoa chăm sóc sức khỏe" style="max-width: 100%; border-radius: 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.12);"></div>\n\n{html_content}'
                        else:
                            full_content = html_content
                            
                        return full_content
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

def create_wp_post(clean_title, content, media_id=None):
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        print("❌ Lỗi: Chưa cấu hình đủ Secrets WordPress.")
        return False
        
    session = requests.Session()
    session.auth = (WP_USERNAME, WP_PASSWORD)
    session.headers.update({"Content-Type": "application/json"})
    
    payload = {
        "title": f"[Y Khoa Cần Thơ] {clean_title[:65]}",
        "content": content,
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
    existing_content = get_existing_wp_posts()
    
    models_list = get_available_gemini_models()
    if not models_list:
        print("❌ Lỗi: Không có model AI nào khả dụng cho API Key của bạn.")
        return
    
    posted_count = 0
    # Xử lý tối đa 15 bài trong mỗi lần chạy
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
            
        # Nếu chưa có, tự động dùng Regex bóc tách link ảnh bên trong thẻ <description> / <summary> của RSS
        if not thumbnail_url:
            desc_text = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            match_img = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', desc_text, re.IGNORECASE)
            if match_img:
                thumbnail_url = match_img.group(1)
                print(f"🔎 Đã trích xuất được link ảnh thumbnail từ RSS description: {thumbnail_url[:60]}...")
            
        if not video_id:
            continue
            
        is_posted = any(video_id in str(c) for c in existing_content)
        if is_posted:
            print(f"⏩ Video ID {video_id} ({title[:30]}...) đã đăng trên web rồi, bỏ qua.")
            continue
            
        print(f"✍️ Đang viết bài y khoa chuẩn SEO cho video: {title[:50]}...")
        
        # Tải ảnh thumbnail về máy chủ WordPress để làm ảnh đại diện + chèn vào đầu bài viết
        media_id, local_img_url = upload_image_to_wp(thumbnail_url)
        
        article_html = generate_seo_article(title, url, video_id, local_img_url, models_list)
        if article_html:
            if create_wp_post(title, article_html, media_id):
                posted_count += 1
            time.sleep(5)
            
    if posted_count == 0:
        print("ℹ️ Hoàn tất chạy: Tất cả video trong RSS đều đã được đăng lên Benhviencantho.com, không có bài mới.")
    else:
        print(f"🎉 Hoàn tất xuất sắc! Đã đăng thành công {posted_count} bài viết y khoa mới lên Benhviencantho.com.")

if __name__ == "__main__":
    main()
