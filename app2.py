import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io
import numpy as np
import cv2

# 主函数
def main():
    st.title("基於Streamlit的PDF圖片提取並進行編輯")

    uploaded_file = st.file_uploader("上傳PDF文件", type="pdf")
    if uploaded_file is not None:
        with st.spinner("正在加载PDF文件..."):
            images = read_pdf(uploaded_file)
        
        st.write("PDF檔案已成功讀取！請選擇您要處理的頁面：")
        
        image_options = [f"第 {i + 1} 頁" for i in range(len(images))]
        selected_page = st.selectbox("選擇頁面", image_options)
        page_idx = image_options.index(selected_page)
        
        display_page(images[page_idx], page_idx)

def display_page(image, idx):
    st.image(image, caption=f"第 {idx + 1} 頁", use_column_width=True)

    text = st.text_area("輸入要添加的文本", "")
    font_size = st.slider("選擇字體大小", 10, 100, 30)

    if st.button("在圖像上添加文本"):
        x = st.slider("X 坐标", 0, image.width, 10)
        y = st.slider("Y 坐标", 0, image.height, 10)
        w = st.slider("宽度", 10, image.width, 100)
        h = st.slider("高度", 10, image.height, 50)

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
    font = ImageFont.load_default()  # 使用内置默认字体
    draw.text((x, y), text, font=font, fill="black")
    return image

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

if __name__ == "__main__":
    main()
