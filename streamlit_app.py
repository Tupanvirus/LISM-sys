import streamlit as st
from datetime import datetime
from supabase import create_client, Client
import qrcode
import io
import tempfile
from fpdf import FPDF

# Настройки Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Нормативы качества нефти
LIMITS = {
    "density_min": 700,
    "density_max": 1000,
    "kinematic_viscosity_max": 50,
    "dynamic_viscosity_max": 100,
    "water_max": 0.5,
    "mechanical_max": 0.05,
    "salt_max": 100,
    "sulfur_max": 3.5,
    "flash_point_min": 323,
    "boiling_point_range": (323, 673)
}

def evaluate_sample(params):
    issues = []
    if not (LIMITS["density_min"] <= params["density"] <= LIMITS["density_max"]):
        issues.append("Плотность вне нормы")
    if params["kinematic_viscosity"] > LIMITS["kinematic_viscosity_max"]:
        issues.append("Кинематическая вязкость слишком высокая")
    if params["dynamic_viscosity"] > LIMITS["dynamic_viscosity_max"]:
        issues.append("Динамическая вязкость слишком высокая")
    if params["water"] > LIMITS["water_max"]:
        issues.append("Содержание воды выше нормы")
    if params["mechanical"] > LIMITS["mechanical_max"]:
        issues.append("Присутствуют механические примеси")
    if params["salt"] > LIMITS["salt_max"]:
        issues.append("Содержание солей выше нормы")
    if params["sulfur"] > LIMITS["sulfur_max"]:
        issues.append("Содержание серы выше нормы")
    if params["flash_point"] < LIMITS["flash_point_min"]:
        issues.append("Температура вспышки ниже нормы")
    bp_min, bp_max = LIMITS["boiling_point_range"]
    if not (bp_min <= params["boiling_point_min"] <= bp_max) or not (bp_min <= params["boiling_point_max"] <= bp_max):
        issues.append("Фракционный состав вне диапазона кипения")

    if len(issues) == 0:
        decision = "ГОДНА"
    elif len(issues) <= 2:
        decision = "УСЛОВНО ГОДНА"
    else:
        decision = "НЕГОДНА"

    return decision, issues

# QR Генерация
def generate_qr(sample_data: dict) -> bytes:
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(str(sample_data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# PDF через pdfkit (HTML)
def create_pdf_html(sample_data, issues):
    html = f"""
    <h2>Протокол лабораторного анализа нефти</h2>
    <p><strong>Дата:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <ul>
    """
    for k, v in sample_data.items():
        if k != "issues":
            html += f"<li><strong>{k}:</strong> {v}</li>"
    if issues:
        html += "<li><strong>Причины отклонений:</strong><ul>"
        for issue in issues:
            html += f"<li>{issue}</li>"
        html += "</ul></li>"
    html += "</ul>"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        pdfkit.from_string(html, f.name)
        f.seek(0)
        pdf_bytes = f.read()
    return pdf_bytes

# UI Streamlit
st.title("ЛИС для нефтебазы")

# Ввод параметров
train = st.text_input("Номер состава", help = "Вводите номер из 4 цифр")
tank = st.text_input("Номер цистерны", help = "Вводите номер из 8 цифр, первая цифра - 7")
sample_number = st.text_input("Номер пробы")
product_name = st.text_input("Наименование продукта",help= "Указывайте в таком виде:[Тип продукта] + [Марка/Характеристика] + [Нормативный документ (ГОСТ/ТУ)] \n Например:Топливо реактивное ТС-1")
supplier = st.text_input("Поставщик", help= "Укажите название организации")
batch = st.text_input("Номер партии")
operator = st.text_input("ФИО отборщика")

# Показатели нефти
density = st.number_input("Плотность, кг/м³", 700.0, 1000.0, 820.0)
kinematic_viscosity = st.number_input("Кинематическая вязкость, мм²/с")
dynamic_viscosity = st.number_input("Динамическая вязкость, мПа·с")
mass_fraction_of_water = st.number_input("Вода, %")
mechanical = st.number_input("Механические примеси, %")
salt = st.number_input("Содержание солей, мг/дм³")
sulfur = st.number_input("Сера, %")
flash_point = st.number_input("Температура вспышки, K")
boiling_point_min = st.number_input("Нижняя температура кипения, K")
boiling_point_max = st.number_input("Верхняя температура кипения, K")

# Создание пробы
if st.button("Создать и оценить пробу"):
    required_fields = [
        train, tank, sample_number, product_name, supplier, batch, operator,
        density, kinematic_viscosity, dynamic_viscosity, mass_fraction_of_water,
        mechanical, salt, sulfur, flash_point, boiling_point_min, boiling_point_max
    ]
    if not all(required_fields):
        st.error("Пожалуйста, заполните все обязательные поля!")
    else:
        # Проверка уникальности
        existing = supabase.table("samples").select("id").eq("train_number", train).eq("tank_number", tank).execute()
        if existing.data and len(existing.data) > 0:
            st.warning("Эта комбинация состава и цистерны уже существует!")
        else:
            params = {
                "density": density,
                "kinematic_viscosity": kinematic_viscosity,
                "dynamic_viscosity": dynamic_viscosity,
                "water": mass_fraction_of_water,
                "mechanical": mechanical,
                "salt": salt,
                "sulfur": sulfur,
                "flash_point": flash_point,
                "boiling_point_min": boiling_point_min,
                "boiling_point_max": boiling_point_max
            }
            decision, issues = evaluate_sample(params)

            sample_data = {
                "sample_number": sample_number,
                "product_name": product_name,
                "supplier": supplier,
                "batch_number": batch,
                "tank_number": tank,
                "train_number": train,
                "operator": operator,
                **params,
                "decision": decision,
                "issues": ", ".join(issues),
                "date": datetime.now().isoformat()
            }
            st.session_state.sample_data = sample_data
            st.session_state.issues = issues
            # Сохраняем в Supabase
            supabase.table("samples").insert(sample_data).execute()

            # QR
            qr_buf = generate_qr(sample_data)
            st.image(qr_buf, caption="QR код пробы")
            st.download_button("Скачать QR", qr_buf, file_name=f"QR_{sample_number}.png")

            # PDF
if st.session_state.sample_data:
    if st.button("Сгенерировать PDF"):
        pdf = create_pdf_bytes(
            st.session_state.sample_data,
            st.session_state.issues
        )

        st.download_button(
            "Скачать PDF",
            pdf,
            file_name=f"protocol_{st.session_state.sample_data['sample_number']}.pdf",
            mime="application/pdf"
        )
# Дэшборд
st.header("Дэшборд по пробам")
all_samples = supabase.table("samples").select("*").execute()
if all_samples.data:
    st.dataframe(all_samples.data)
else:
    st.info("В базе нет данных")
