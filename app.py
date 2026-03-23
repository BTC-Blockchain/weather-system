import streamlit as st
import requests
import json
import re
from streamlit_autorefresh import st_autorefresh
import pandas as pd

st.set_page_config(page_title="天气交易系统", layout="centered")

# 自动刷新（30秒）
st_autorefresh(interval=30000, key="refresh")

# ======================
# 获取 METAR
# ======================
def get_metar():
    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        res = requests.get(url, timeout=5).text
        return res.split("\n")[1]
    except:
        return None

# ======================
# 解析 METAR（时间+温度）
# ======================
def parse_metar(metar):
    if not metar:
        return None, None

    time_match = re.search(r'(\d{6})Z', metar)
    temp_match = re.search(r' (\d{2})/(\d{2}) ', metar)

    if not time_match or not temp_match:
        return None, None

    metar_time = time_match.group(1)  # 230600
    temp = int(temp_match.group(1))

    return metar_time, temp

# ======================
# 获取真实数据
# ======================
def get_real_data():
    metar = get_metar()
    return parse_metar(metar)

# ======================
# 保存数据（用METAR时间去重）
# ======================
def save_temp(metar_time, temp):
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        data = []

    if temp is None or metar_time is None:
        return data

    # 核心：用 METAR 时间去重
    if len(data) > 0 and data[-1]["metar_time"] == metar_time:
        return data

    data.append({
        "metar_time": metar_time,
        "temp": temp
    })

    with open("data.json", "w") as f:
        json.dump(data, f)

    return data

# ======================
# 读取数据
# ======================
def load_data():
    try:
        with open("data.json", "r") as f:
            return json.load(f)
    except:
        return []

# ======================
# 最高温
# ======================
def get_max_temp(data):
    if not data:
        return None
    return max(x["temp"] for x in data)

# ======================
# 升温速度
# ======================
def calc_speed(data):
    if len(data) < 2:
        return 0
    t1 = data[-2]["temp"]
    t2 = data[-1]["temp"]
    return (t2 - t1) * 2  # 半小时 → 每小时

# ======================
# 是否见顶
# ======================
def is_peaking(data):
    if len(data) < 3:
        return False
    t1 = data[-3]["temp"]
    t2 = data[-2]["temp"]
    t3 = data[-1]["temp"]
    return (t3 - t2) < (t2 - t1)

# ======================
# Kelly
# ======================
def kelly(p, m):
    if m <= 0:
        return 0
    b = (1/m) - 1
    q = 1 - p
    f = (b*p - q) / b
    return max(f * 0.3, 0)

# ======================
# 模型
# ======================
def model_probs(temp, speed):
    if temp is None:
        return {"14":0.33,"15":0.34,"16":0.33}

    if speed > 1:
        return {"14":0.1,"15":0.4,"16":0.5}
    elif speed < 0.3:
        return {"14":0.2,"15":0.6,"16":0.2}
    else:
        return {"14":0.2,"15":0.5,"16":0.3}

# ======================
# 市场（先手动）
# ======================
def get_market():
    return {"14":0.30,"15":0.48,"16":0.22}

# ======================
# UI
# ======================
st.title("🌡️ 天气交易系统（METAR对齐版）")

metar_time, temp = get_real_data()
data = save_temp(metar_time, temp)

speed = calc_speed(data)
peak = is_peaking(data)
market = get_market()
model = model_probs(temp, speed)

# 当前
st.subheader("🌡️ 当前数据")

st.metric("当前温度", f"{temp}°C" if temp else "N/A")
st.metric("今日最高温", f"{get_max_temp(data)}°C" if data else "N/A")

# 曲线（修复版）
st.subheader("📈 温度曲线（METAR）")

if data:
    df = pd.DataFrame(data)
    df["time"] = df["metar_time"].str[2:4] + ":" + df["metar_time"].str[4:6]
    st.line_chart(df.set_index("time")["temp"])

# 趋势
st.subheader("📊 趋势分析")

st.metric("升温速度", f"{speed:.2f} °C/h")

if peak:
    st.warning("⚠️ 接近峰值")
else:
    st.success("🔥 仍在上升")

# 市场
st.subheader("📡 市场概率")

for k in market:
    st.write(f"{k}°C → {market[k]*100:.1f}%")

# 模型
st.subheader("🧠 模型概率")

for k in model:
    st.write(f"{k}°C → {model[k]*100:.1f}%")

# 交易
st.subheader("💰 交易建议")

best = None
best_edge = -999

for k in model:
    edge = model[k] - market[k]
    bet = min(kelly(model[k], market[k]) * 10000, 2000)

    if edge > best_edge:
        best_edge = edge
        best = k

    st.write(f"{k}°C → Edge {edge*100:.1f}% | ${bet:.0f}")

if best_edge > 0.05:
    st.success(f"👉 建议下注：{best}°C")
else:
    st.warning("⚠️ 无明显机会")

st.caption("自动刷新：30秒 | 数据源：METAR（ZSPD）")