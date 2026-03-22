import streamlit as st
from datetime import datetime
from supabase import create_client, Client
import qrcode
import io

#Настройки Supabase
SUPABASE_URL = st.secrets[SUPABASE_URL]
SUPABASE_KEY = st.secrets[SUPABASE_KEY]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Функции ГОСТ
def calculate_samples(total_tanks: int) -> int:
    return max(2, total_tanks // 4)

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

#QR Генерация
def generate_qr(sample_data: dict) -> bytes:
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(str(sample_data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

#Streamlit UI
st.title("ЛИС для нефтебазы)")

train = st.text_input("Номер состава", help="Например 2456-789-01")
tank = st.text_input("Номер цистерны", help="8 цифр")
total_tanks = st.number_input("Кол-во цистерн в составе", min_value=2)
density = st.number_input("Плотность, кг/м³", min_value=700.0, max_value=1000.0, value=820.0)

samples_count = calculate_samples(total_tanks)
positions = get_sampling_positions(total_tanks)
time_needed = calculate_analysis_time(samples_count)

st.info(f"Отобрать цистерн: {samples_count}\nНомера цистерн: {positions}\nВремя анализа: {time_needed} мин")

sample_number = st.text_input("Номер пробы (журнал)")
product_name = st.text_input("Наименование продукта")
supplier = st.text_input("Поставщик")
batch = st.text_input("Номер партии")
operator = st.text_input("ФИО отборщика")
heavy_oil = st.checkbox("Тяжёлая нефть?", value=False)

#Создание пробы 
if st.button("Создать пробу"):
    # Проверка обязательных полей
    required_fields = [train, tank, sample_number, product_name, supplier, batch, operator]
    if not all(required_fields):
        st.error("Пожалуйста, заполните все обязательные поля!")
    else:
        #Проверка дубликата
        existing = supabase.table("samples") \
            .select("id") \
            .eq("train_number", train) \
            .eq("tank_number", tank) \
            .execute()

        if existing.data and len(existing.data) > 0:
            st.warning("Эта комбинация состава и цистерны уже существует в базе!")
        else:
            #Данные для вставки
            sample_data = {
                "sample_number": sample_number,
                "product_name": product_name,
                "supplier": supplier,
                "batch_number": batch,
                "tank_number": tank,
                "train_number": train,
                "operator": operator,
                "density": density,
                "sampling_positions": ",".join(map(str, positions)),  # строка для Supabase
                "samples_count": samples_count,
                "analysis_time": calculate_analysis_time(samples_count, heavy_oil),
                "date": datetime.now().isoformat()
            }

            # Вставка в Supabase
            response = supabase.table("samples").insert(sample_data).execute()
            if response.status_code != 201 and response.status_code != 200:
                st.error(f"Ошибка сохранения в Supabase: {response.data}")
            else:
                #Генерация QR
                qr_buf = generate_qr(sample_data)
                st.image(qr_buf, caption="QR для пробы")
                st.download_button("Скачать QR", qr_buf, file_name=f"QR_{sample_number}.png")
                st.success("Проба сохранена в Supabase и QR сгенерирован")
