import streamlit as st
import sqlite3
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import io
import numpy as np
import cv2
from datetime import datetime, timedelta
import easyocr

# 初始化数据库连接
conn = sqlite3.connect('users.db')
c = conn.cursor()

# 检查并创建表
def create_table_if_not_exists(cursor, table_name):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            username TEXT PRIMARY KEY,
            password TEXT,
            membership TEXT,
            role TEXT DEFAULT 'user',
            credits INTEGER DEFAULT 0,
            premium_expiry TEXT,
            free_uses INTEGER DEFAULT 2,
            last_reset TEXT
        )
    """)

create_table_if_not_exists(c, 'users')

# 检查并添加缺失的数据库列
def add_column_if_not_exists(cursor, table_name, column_name, column_type):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

add_column_if_not_exists(c, 'users', 'membership', 'TEXT')
add_column_if_not_exists(c, 'users', 'role', 'TEXT DEFAULT "user"')
add_column_if_not_exists(c, 'users', 'credits', 'INTEGER DEFAULT 0')
add_column_if_not_exists(c, 'users', 'premium_expiry', 'TEXT')
add_column_if_not_exists(c, 'users', 'free_uses', 'INTEGER DEFAULT 2')
add_column_if_not_exists(c, 'users', 'last_reset', 'TEXT')

# 初始化 EasyOCR 读者
reader = easyocr.Reader(['ch_sim', 'en'])

# 主函数
def main():
    st.title("基於Streamlit的PDF圖片提取並進行編輯")

    # 初始化session state
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.session_state['membership'] = ""
        st.session_state['role'] = ""
        st.session_state['credits'] = 0
        st.session_state['premium_expiry'] = None
        st.session_state['free_uses'] = 2
        st.session_state['last_reset'] = None

    # 登录状态判断
    if st.session_state['logged_in']:
        st.sidebar.write(f"歡迎，{st.session_state['username']}！")
        check_reset_free_uses()
        user_info()
        if st.session_state['role'] == 'admin':
            admin_page()
        else:
            user_page()
    else:
        menu = ["登錄", "註冊"]
        choice = st.sidebar.selectbox("選擇操作", menu)

        if choice == "登錄":
            login()
        elif choice == "註冊":
            signup()

# 登录功能
def login():
    st.subheader("請登入")
    username = st.text_input("使用者名稱")
    password = st.text_input("密碼", type="password")

    if st.button("登入", key="login_button"):
        user = validate_login(username, password)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.session_state['membership'] = user[2]
            st.session_state['role'] = user[3]
            st.session_state['credits'] = user[4] if user[4] is not None else 0
            st.session_state['premium_expiry'] = user[5]
            st.session_state['free_uses'] = user[6] if user[6] is not None else 2
            st.session_state['last_reset'] = user[7] if user[7] is not None else datetime.now().strftime('%Y-%m-%d')
            st.success("登入成功！")
            st.experimental_rerun()
        else:
            st.error("使用者名稱或密碼錯誤")

# 注册功能
def signup():
    st.subheader("註冊新帳戶")
    new_username = st.text_input("新使用者")
    new_password = st.text_input("新密碼", type="password")
    membership_type = st.selectbox("選擇會員類型", ["free"])

    if st.button("註冊", key="signup_button"):
        if not validate_signup(new_username):
            create_user(new_username, new_password, membership_type)
            st.success("註冊成功，請登入！")
            # 设置登录状态并重定向到登录页面
            st.session_state['logged_in'] = False
            st.experimental_rerun()
        else:
            st.error("名字已存在，請選擇其他名字。")

# 验证登录
def validate_login(username, password):
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    return c.fetchone()

# 验证注册
def validate_signup(username):
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    return c.fetchone()

# 创建用户
def create_user(username, password, membership, role='user'):
    c.execute("INSERT INTO users (username, password, membership, role, credits, free_uses, last_reset) VALUES (?, ?, ?, ?, ?, ?, ?)", 
              (username, password, membership, role, 0, 2, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()

# 升级会员
def upgrade_membership(username):
    expiry_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    c.execute("UPDATE users SET membership = 'premium', premium_expiry = ? WHERE username = ?", (expiry_date, username))
    conn.commit()

# 降级会员
def downgrade_membership(username):
    c.execute("UPDATE users SET membership = 'free', premium_expiry = NULL WHERE username = ?", (username,))
    conn.commit()

# 删除用户
def delete_user(username):
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()

# 更新免费会员的使用次数
def update_free_uses(username, new_free_uses):
    c.execute("UPDATE users SET free_uses = ? WHERE username = ?", (new_free_uses, username))
    conn.commit()

# 检查并重置免费使用次数
def check_reset_free_uses():
    last_reset = st.session_state['last_reset']
    if last_reset:
        try:
            last_reset_date = datetime.strptime(str(last_reset), '%Y-%m-%d').date()
        except ValueError:
            last_reset_date = datetime.now().date()
            st.session_state['last_reset'] = last_reset_date.strftime('%Y-%m-%d')
            c.execute("UPDATE users SET last_reset = ? WHERE username = ?", (st.session_state['last_reset'], st.session_state['username']))
            conn.commit()
        current_date = datetime.now().date()
        if current_date > last_reset_date:
            st.session_state['free_uses'] = 2
            st.session_state['last_reset'] = current_date.strftime('%Y-%m-%d')
            c.execute("UPDATE users SET free_uses = ?, last_reset = ? WHERE username = ?", (2, current_date.strftime('%Y-%m-%d'), st.session_state['username']))
            conn.commit()

# 用户信息显示在侧边栏
def user_info():
    with st.sidebar.expander("用户信息", expanded=True):
        if st.session_state['role'] != 'admin':  # 仅非管理员用户显示付款和升级信息
            if st.session_state['membership'] == 'premium':
                if st.session_state['premium_expiry']:
                    expiry_date = datetime.strptime(st.session_state['premium_expiry'], '%Y-%m-%d').date()
                    remaining_days = (expiry_date - datetime.now().date()).days
                    st.write(f"您的付費會員還剩 {remaining_days} 天")
            else:
                st.write(f"您還有 {st.session_state['free_uses']} 次免費使用更改的機會")
                st.write("免費次數會在每天晚上12點重製")

            st.write(f"您的剩餘點數: {st.session_state['credits']}")
            st.write("花費100點數可升級到付費會員")

            # 显示充值和升级选项
            st.write("### 充值")
            card_number = st.text_input('信用卡號')
            expiry_date = st.text_input('到期日（MM/YY）')
            cvv = st.text_input('CVV', type='password')
            amount = st.number_input('輸入儲值金額', min_value=1, max_value=100)

            if st.button('儲值', key="top_up_button"):
                if not validate_card_number(card_number):
                    st.error('無效的信用卡號，應為十六位數字')
                elif not validate_expiry_date(expiry_date):
                    st.error('無效的到期日，格式應為MM/YY')
                elif not validate_cvv(cvv):
                    st.error('無效的CVV，應為三位數字')
                else:
                    update_credits(st.session_state['username'], amount)
                    st.session_state['credits'] += amount
                    st.success(f'成功增加 {amount} 點數！')
                    st.experimental_rerun()

            if st.session_state['credits'] is not None and st.session_state['credits'] >= 100:
                if st.session_state['premium_expiry'] and datetime.now().date() < datetime.strptime(st.session_state['premium_expiry'], '%Y-%m-%d').date():
                    st.write(f"您的會員資格將於 {st.session_state['premium_expiry']} 過期，在此之前無法再購買")
                else:
                    if st.button("使用100點數升級到付費會員", key="upgrade_button"):
                        if st.session_state['credits'] >= 100:
                            upgrade_membership(st.session_state['username'])
                            st.session_state['credits'] -= 100
                            st.session_state['membership'] = 'premium'
                            st.session_state['premium_expiry'] = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                            st.success("升級成功！現在您是付費會員，可以存取更多內容")
                            st.experimental_rerun()
                        else:
                            st.error("您的點數不足")

        if st.button("登出", key="logout_button"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = ""
            st.session_state['membership'] = ""
            st.session_state['role'] = ""
            st.session_state['credits'] = 0
            st.session_state['premium_expiry'] = None
            st.session_state['free_uses'] = 2
            st.experimental_rerun()

# 用户界面
def user_page():
    # 检查付费会员到期时间
    if st.session_state['membership'] == 'premium':
        if st.session_state['premium_expiry']:
            expiry_date = datetime.strptime(st.session_state['premium_expiry'], '%Y-%m-%d').date()
            remaining_days = (expiry_date - datetime.now().date()).days
            if remaining_days <= 0:
                downgrade_membership(st.session_state['username'])
                st.session_state['membership'] = 'free'
                st.session_state['premium_expiry'] = None
                st.warning("您的付費會員已過期。")
                st.experimental_rerun()
        protected_content()
    else:
        st.write("這是免費會員內容")
        if st.session_state['free_uses'] > 0:
            protected_content()
        else:
            st.warning("您的免費次數已用完。請儲值以獲得更多次數或升級至付費會員")

# 管理员界面
def admin_page():
    st.write("這是管理者介面。您可以管理用戶。")

    users = get_all_users()
    for user in users:
        expiry_date_display = user[5] if user[5] else "無"
        free_uses_display = user[6] if user[6] else "無"
        credits_display = user[4] if user[4] else 0
        st.write(f"使用者名稱: {user[0]}, 會員類型: {user[2]}, 角色: {user[3]}, 點數: {credits_display}, 會員到期時間: {expiry_date_display}, 免費使用次數: {free_uses_display}")
        if user[3] != "admin":  # 管理者不能被删除
            if st.button(f"刪除 {user[0]}", key=f"delete_button_{user[0]}"):
                delete_user(user[0])
                st.success(f"使用者 {user[0]} 已刪除。")
                st.experimental_rerun()
    
    if st.button("重置所有免費用戶的使用次數", key="reset_all_button"):
        reset_free_uses()
        st.success("所有免費用戶的使用次數已重置。")
        st.experimental_rerun()

    if st.button("登出", key="admin_logout_button"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.session_state['membership'] = ""
        st.session_state['role'] = ""
        st.session_state['credits'] = 0
        st.session_state['premium_expiry'] = None
        st.session_state['free_uses'] = 2
        st.experimental_rerun()

# 获取所有用户
def get_all_users():
    c.execute("SELECT * FROM users")
    return c.fetchall()

# 受保护内容
def protected_content():
    st.write("這裡是可以上傳PDF檔案並處理的部分")
    uploaded_file = st.file_uploader("上傳PDF文件", type="pdf")
    if uploaded_file is not None:
        with st.spinner("正在加载PDF文件..."):
            images = read_pdf(uploaded_file)
        
        st.write("PDF檔案已成功讀取！請選擇您要處理的頁面：")
        
        if 'ocr_results' not in st.session_state:
            st.session_state.ocr_results = {}

        image_options = [f"第 {i + 1} 頁" for i in range(len(images))]
        selected_page = st.selectbox("選擇頁面", image_options)
        page_idx = image_options.index(selected_page)

        if st.session_state.get('updated_images') is None:
            st.session_state.updated_images = [None] * len(images)

        if st.session_state.updated_images[page_idx] is None:
            st.session_state.updated_images[page_idx] = images[page_idx]

        display_page(st.session_state.updated_images[page_idx], page_idx)

def display_page(image, idx):
    st.image(image, caption=f"第 {idx + 1} 頁", use_column_width=True)
    if st.button("偵測文字區域"):
        text_regions = perform_ocr(image)
        st.session_state.ocr_results[idx] = text_regions
        for region_idx, region in enumerate(text_regions):
            x, y, w, h, text, font_size = region
            st.image(image.crop((x, y, x + w, y + h)), caption=f"區域 {region_idx + 1}", use_column_width=True)
            st.session_state[f"editable_text_{idx}_{region_idx}"] = text

    if idx in st.session_state.ocr_results:
        text_regions = st.session_state.ocr_results[idx]
        for region_idx, region in enumerate(text_regions):
            x, y, w, h, text, font_size = region
            editable_text = st.text_area(f"編輯第 {idx + 1} 頁第 {region_idx + 1} 區域的文字", value=text, key=f"editable_text_{idx}_{region_idx}")
            font_size = st.slider("選擇字體大小", 1, 50, font_size, key=f"font_size_slider_{idx}_{region_idx}")
            thickness = st.slider("選擇文字粗細度", 1, 10, 2, key=f"thickness_slider_{idx}_{region_idx}")
            
            if st.button(f"在圖片上更新第 {idx + 1} 頁第 {region_idx + 1} 區域的文字", key=f"update_button_{idx}_{region_idx}"):
                updated_image = update_image_text(st.session_state.updated_images[idx], x, y, w, h, editable_text, font_size, thickness)
                st.session_state.updated_images[idx] = updated_image
                st.experimental_rerun()

    if st.button(f"重新載入第 {idx + 1} 頁", key=f'reload_button_{idx}'):
        st.session_state.updated_images[idx] = None
        st.experimental_rerun()

# 执行OCR识别并返回文字区域
def perform_ocr(image):
    im = image.filter(ImageFilter.MedianFilter())
    enhancer = ImageEnhance.Contrast(im)
    im = enhancer.enhance(2)
    im = im.convert('L')
    image_np = np.array(im)
    results = reader.readtext(image_np, detail=1)
    
    text_regions = []
    for result in results:
        bbox, text = result[:2]
        x_min, y_min = min(bbox[0][0], bbox[3][0]), min(bbox[0][1], bbox[1][1])
        x_max, y_max = max(bbox[1][0], bbox[2][0]), max(bbox[2][1], bbox[3][1])
        w, h = x_max - x_min, y_max - y_min
        font_size = estimate_font_size(bbox)
        text_regions.append((x_min, y_min, w, h, text, font_size))

    # 合并接近的矩形框
    merged_regions = merge_nearby_boxes(text_regions, threshold=10)
    
    return merged_regions

# 合并接近的矩形框
def merge_nearby_boxes(boxes, threshold):
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))  # 按 y 和 x 排序
    merged_boxes = [boxes[0]]

    for box in boxes[1:]:
        last_box = merged_boxes[-1]
        if (abs(last_box[1] - box[1]) < threshold and abs((last_box[1] + last_box[3]) - (box[1] + box[3])) < threshold) or \
           (abs(last_box[0] - box[0]) < threshold and abs((last_box[0] + last_box[2]) - (box[0] + box[2])) < threshold):
            new_x = min(last_box[0], box[0])
            new_y = min(last_box[1], box[1])
            new_w = max(last_box[0] + last_box[2], box[0] + box[2]) - new_x
            new_h = max(last_box[1] + last_box[3], box[1] + box[3]) - new_y
            new_text = f"{last_box[4]} {box[4]}"
            new_font_size = max(last_box[5], box[5])
            merged_boxes[-1] = (new_x, new_y, new_w, new_h, new_text, new_font_size)
        else:
            merged_boxes.append(box)

    # 将矩形框加大一点
    expanded_boxes = []
    for box in merged_boxes:
        x, y, w, h, text, font_size = box
        expanded_boxes.append((x - 5, y - 5, w + 10, h + 10, text, font_size))

    return expanded_boxes

# 估算字体大小
def estimate_font_size(bbox):
    if not bbox:
        return 1
    height = np.linalg.norm(np.array(bbox[0]) - np.array(bbox[3]))
    return max(1, int(height / 2))

# 更新图片上的文字
def update_image_text(image, left, top, width, height, text, font_size, thickness):
    cv_image = np.array(image)
    cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
    
    # 删除原来的区域
    cv2.rectangle(cv_image, (int(left), int(top)), (int(left + width), int(top + height)), (255, 255, 255), -1)
    
    # 添加新的文本
    font = cv2.FONT_HERSHEY_SIMPLEX
    color = (0, 0, 0)

    # 计算新的文本位置
    text_x = int(left)
    text_y = int(top + font_size)  # 调整 y 坐标以匹配原始字体的基线

    wrapped_text = wrap_text(text, width, font_size)
    for line in wrapped_text:
        cv2.putText(cv_image, line, (text_x, text_y), font, font_size / 10, color, thickness)
        text_y += int(font_size * 3)  # 调整 y 坐标以匹配每行的高度

    pil_image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
    return pil_image

# 将文本分行
def wrap_text(text, max_width, font_size):
    lines = []
    current_line = ""
    current_width = 0
    space_width = font_size / 2  # 空格字符的近似宽度

    for char in text:
        if char == '\n':
            lines.append(current_line)
            current_line = ""
            current_width = 0
        else:
            char_width = font_size / 2  # 每个字符的近似宽度
            if current_width + char_width > max_width:
                lines.append(current_line)
                current_line = char
                current_width = char_width
            else:
                current_line += char
                current_width += char_width

    if current_line:
        lines.append(current_line)
    return lines

# 添加初始管理员
def add_initial_admin():
    if not validate_signup("admin"):
        create_user("admin", "adminpass", "premium", "admin")

# 验证信用卡号
def validate_card_number(card_number):
    return card_number.isdigit() and len(card_number) in [13, 16, 19]

# 验证到期日
def validate_expiry_date(expiry_date):
    if len(expiry_date) != 5 or expiry_date[2] != '/':
        return False
    month, year = expiry_date.split('/')
    return month.isdigit() and year.isdigit() and 1 <= int(month) <= 12

# 验证CVV
def validate_cvv(cvv):
    return cvv.isdigit() and len(cvv) == 3

# 更新点数
def update_credits(username, amount):
    c.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amount, username))
    conn.commit()

# 重置所有免费用户的使用次数
def reset_free_uses():
    c.execute("UPDATE users SET free_uses = 2, last_reset = ? WHERE membership = 'free'", (datetime.now().strftime('%Y-%m-%d'),))
    conn.commit()

if __name__ == "__main__":
    add_initial_admin()
    main()
    conn.close()
