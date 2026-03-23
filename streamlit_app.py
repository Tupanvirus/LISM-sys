import streamlit as st
from datetime import datetime
from supabase import create_client, Client
import qrcode
import io
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import math

# API Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Функции ГОСТ для расчета времени и кол-ва цистерн для анализа
def calculate_samples(total_tanks: int) -> int:
    return max(2, math.ceil(total_tanks / 4))

def get_sampling_positions(total_tanks: int):
    if total_tanks <= 2:
        return list(range(1, total_tanks + 1))
    positions = list(range(4, total_tanks + 1, 4))
    if len(positions) < 2:
        positions = [1, total_tanks]
    return positions

def calculate_analysis_time(samples_count: int, heavy_oil: bool = False) -> int:
    base_time = (3 * samples_count) + 10 + (10 * samples_count)
    if heavy_oil:
        base_time += samples_count * 2
    return base_time

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
        issues.append("Присутствуют соли выше нормы")
    if params["sulfur"] > LIMITS["sulfur_max"]:
        issues.append("Содержание серы выше нормы")
    if params["flash_point"] < LIMITS["flash_point_min"]:
        issues.append("Температура вспышки ниже нормы")
    bp_min, bp_max = LIMITS["boiling_point_range"]
    if not (bp_min <= params["boiling_point_min"] <= bp_max) or not (bp_min <= params["boiling_point_max"] <= bp_max):
        issues.append("Фракционный состав вне диапазона кипения")

    if len(issues) == 0:
        decision = "Качество нефтепродуктов удовлетворительное"
    elif len(issues) <= 2:
        decision = "Качество нефтепродуктов условно удовлетворительное"
    else:
        decision = "Качество нефтепродуктов неудовлетворительное"

    return decision, issues

# PDF генерация
def create_pdf(sample_data, issues):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 50, "Протокол лабораторного анализа нефти")
    c.setFont("Helvetica", 12)
    y = height - 80
    for key, value in sample_data.items():
        if key != "issues":
            c.drawString(50, y, f"{key}: {value}")
            y -= 20
    if issues:
        c.drawString(50, y, "Причины отклонений:")
        y -= 20
        for issue in issues:
            c.drawString(70, y, f"- {issue}")
            y -= 15
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# Streamlit UI
st.title("ЛИС нефтебазы — полный контроль качества")

st.header("Ввод параметров пробы")
train = st.text_input("Номер состава")
tank = st.text_input("Номер цистерны")
total_tanks = st.number_input("Кол-во цистерн в составе", min_value=2)
samples_count = calculate_samples(total_tanks)
positions = get_sampling_positions(total_tanks)
time_needed = calculate_analysis_time(samples_count)
st.info(f"Отобрать цистерн: {samples_count}\nНомера цистерн: {positions}\nВремя анализа: {time_needed} мин")

sample_number = st.text_input("Номер пробы")
product_name = st.text_input("Наименование продукта")
supplier = st.text_input("Поставщик")
batch = st.text_input("Номер партии")
operator = st.text_input("ФИО отборщика")

# Показатели
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

# Создание и оценка проб
if st.button("Создать и оценить пробу"):
    required_fields = [
    train,
    tank,
    sample_number,
    product_name,
    supplier,
    batch,
    operator,
    density,
    kinematic_viscosity,
    dynamic_viscosity,
    mass_fraction_of_water,
    mechanical,
    salt,
    sulfur,
    flash_point,
    boiling_point_min,
    boiling_point_max
]
    if not all(required_fields):
        st.error("Заполните все обязательные поля!")
    else:
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
                "sampling_positions": ",".join(map(str, positions)),
                "samples_count": samples_count,
                "analysis_time": time_needed,
                "date": datetime.now().isoformat()
            }

            supabase.table("samples").insert(sample_data).execute()

            qr_buf = generate_qr(sample_data)
            st.image(qr_buf, caption="QR код пробы")
            st.download_button("Скачать QR", qr_buf, file_name=f"QR_{sample_number}.png")

            pdf_buf = create_pdf(sample_data, issues)
            st.download_button("Скачать PDF протокол", pdf_buf, file_name=f"Protocol_{sample_number}.pdf")

            if decision == "Качество нефтепродуктов удовлетворительное":
                st.success("Нефть соответствует требованиям")
            elif decision == "Качество нефтепродуктов условно удовлетворительное":
                st.warning("Есть отклонения, необходима доработка")
            else:
                st.error("Качество нефтепродуктов не удовлетворяет требованиям ГОСТ")

            if issues:
                st.write("Причины отклонений:")
                for i in issues:
                    st.write(f"- {i}")

# Авто-дэшборд с подсветкой
st.header("Дэшборд по пробам")

all_samples = supabase.table("samples").select("*").execute()
if all_samples.data:
    df = pd.DataFrame(all_samples.data)
    st.subheader("Таблица проб с подсветкой")

    def highlight_decision(val):
        color = ''
        if val == 'Качество нефтепродуктов удовлетворительно':
            color = 'background-color: lightgreen'
        elif val == 'Качество нефтепродуктов условно удовлетворительно':
            color = 'background-color: yellow'
        elif val == 'Качество нефтепродуктов неудовлетворительно':
            color = 'background-color: tomato'
        return color

    st.dataframe(df.style.applymap(lambda x: highlight_decision(x) if x in ['ГОДНА','УСЛОВНО ГОДНА','НЕГОДНА'] else '', subset=['decision']))

    st.subheader("Распределение по решению")
    st.bar_chart(df['decision'].value_counts())

    st.subheader("Средние показатели")
    numeric_cols = ['density','kinematic_viscosity','dynamic_viscosity','water','mechanical','salt','sulfur','flash_point']
    st.write(df[numeric_cols].mean())
else:
    st.info("В базе нет данных")
