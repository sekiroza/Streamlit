import streamlit as st
import sqlite3
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import io
import numpy as np
import cv2
from datetime import datetime, timedelta
from streamlit_drawable_canvas import st_canvas
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
            free_uses INTEGER DEFAULT 5,
            last_reset TEXT
        )
    """)

create_table_if_not_exists(c, 'users')

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
        st.session_state['free_uses'] = 5
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
            st.session_state['free_uses'] = user[6] if user[6] is not None else 5
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
              (username, password, membership, role, 0, 5, datetime.now().strftime('%Y-%m-%d')))
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
            st.session_state['free_uses'] = 5
            st.session_state['last_reset'] = current_date.strftime('%Y-%m-%d')
            c.execute("UPDATE users SET free_uses = ?, last_reset = ? WHERE username = ?", (5, current_date.strftime('%Y-%m-%d'), st.session_state['username']))
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
            st.session_state['free_uses'] = 5
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
        st.session_state['free_uses'] = 5
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
        
        if 'cropped_images' not in st.session_state:
            st.session_state.cropped_images = []
        
        if 'ocr_results' not in st.session_state:
            st.session_state.ocr_results = {}
        
        if 'updated_images' not in st.session_state:
            st.session_state.updated_images = [None] * len(images)

        image_options = [f"第 {i + 1} 頁" for i in range(len(images))]
        selected_page = st.selectbox("選擇頁面", image_options)
        page_idx = image_options.index(selected_page)

        if st.session_state.updated_images[page_idx] is None:
            st.session_state.updated_images[page_idx] = images[page_idx]

        display_page(st.session_state.updated_images[page_idx], page_idx)

def display_page(image, idx):
    st.image(image, caption=f"第 {idx + 1} 頁", use_column_width=True)

    text = st.text_area("輸入要添加的文本", "")
    font_size = st.slider("選擇字體大小", 10, 100, 30)

    # 添加位置和大小的调整控件
    x = st.slider("X 坐标", 0, image.width, 10)
    y = st.slider("Y 坐标", 0, image.height, 10)
    w = st.slider("宽度", 10, image.width, 100)
    h = st.slider("高度", 10, image.height, 50)

    if x + w > image.width:
        w = image.width - x
    if y + h > image.height:
        h = image.height - y

    if st.button("在圖像上添加文本"):
        image_with_text = erase_and_add_text(image, text, font_size, x, y, w, h)
        st.image(image_with_text, caption="帶有文本的圖像", use_column_width=True)

def erase_and_add_text(image, text, font_size, x, y, w, h):
    # 将图像转换为 OpenCV 格式
    cv_image = np.array(image)
    cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)

    # 擦除指定区域
    cv2.rectangle(cv_image, (x, y), (x + w, y + h), (255, 255, 255), -1)

    # 将图像转换回 PIL 格式
    image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))

    # 在图像上添加文本
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()  # 使用默认字体
    draw.text((x, y), text, font=font, fill="black")
    return image

# 读取PDF文件并返回所有页面的图像
def read_pdf(file):
    pdf_document = fitz.open(stream=file.read(), filetype="pdf")
    images = []

    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        image_list = page.get_images(full=True)
        for img in image_list:
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image = Image.open(io.BytesIO(image_bytes))
            images.append(image)
    
    return images

# 执行OCR识别
def perform_ocr(image):
    im = image.filter(ImageFilter.MedianFilter())
    enhancer = ImageEnhance.Contrast(im)
    im = enhancer.enhance(2)
    im = im.convert('L')
    image_np = np.array(im)
    results = reader.readtext(image_np, detail=1)
    
    st.write("OCR Results:")
    st.write(results)
    
    text = '\n'.join([result[1] for result in results])
    bbox = results[0][0] if results else []
    font_size = estimate_font_size(bbox)
    return text, bbox, font_size

# 估算字体大小
def estimate_font_size(bbox):
    if not bbox:
        return 1
    height = np.linalg.norm(np.array(bbox[0]) - np.array(bbox[3]))
    return max(1, int(height / 2))

if __name__ == "__main__":
    add_initial_admin()
    main()
    conn.close()
