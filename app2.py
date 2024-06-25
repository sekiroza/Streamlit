import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import numpy as np
from streamlit_drawable_canvas import st_canvas

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
    canvas_width = min(image.width, 700)
    scale_ratio = canvas_width / image.width
    scaled_height = int(image.height * scale_ratio)

    st.image(image, caption=f"第 {idx + 1} 頁", use_column_width=True)

    image = image.resize((canvas_width, scaled_height))
    image_array = np.array(image)

    st.write(f"Image array shape: {image_array.shape}")

    image_pil = Image.fromarray(image_array)

    st.write("Image object created")

    # 輸出 PIL 圖像的調試信息
    st.write(f"PIL image size: {image_pil.size}")

    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=2,
        stroke_color="#e00",
        background_image=image_pil,
        update_streamlit=True,
        height=scaled_height,
        width=canvas_width,
        drawing_mode="rect",
        key=f"canvas_{idx}"
    )

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

if __name__ == "__main__":
    main()
