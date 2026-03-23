import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(page_title="天气交易系统", layout="centered")

# 自动刷新（30秒）
st_autorefresh(interval=30000, key="refresh")

# ======================
# 获取 METAR 历史数据（最近24小时）
# ======================
def get_today_metar():
    try:
        url = "https://aviationweather.gov/api/data/metar?ids=ZSPD&format=json&hours=24"
        res = requests.get(url, timeout=10).json()
        return res
    except:
        return []

# ======================
# 过滤“今天数据”
# ======================
def filter_today(data):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return [x for x in data if today in x.get("obsTime", "")]

# ======================
# 解析数据
# ======================
def parse_metar_list(data):
    result = []

    for item in data:
        try:
            temp = item.get("temp")
            time = item.get("obsTime")[11:16]  # HH:MM

            if temp is not None:
                result.append({
                    "time": time,
                    "temp": temp
                })
        except:
            continue

    # 按时间排序
    result.sort(key=lambda x: x["time"])
    return result

# ======================
# 获取完整数据（核心）
# ======================
def get_today_data():
    raw = get_today_metar()
    today_data = filter_today(raw)
    parsed = parse_metar_list(today_data)
    return parsed

# ======================
# 升温速度
# ======================
def calc_speed(data):
    if len(data) < 2:
        return 0
    t1 = data[-2]["temp"]
    t2 = data[-1]["temp"]
    return (t2 - t1) * 2

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
st.title("🌡️ 天气交易系统（完整历史版）")

data = get_today_data()

# 当前温度 = 最后一条
current_temp = data[-1]["temp"] if data else None

# 最高温
max_temp = max([x["temp"] for x in data]) if data else None

# 趋势
speed = calc_speed(data)
peak = is_peaking(data)

market = get_market()
model = model_probs(current_temp, speed)

# 当前数据
st.subheader("🌡️ 当前数据")

st.metric("当前温度", f"{current_temp}°C" if current_temp else "N/A")
st.metric("今日最高温", f"{max_temp}°C" if max_temp else "N/A")

# 曲线
st.subheader("📈 温度曲线（METAR）")

if data:
    df = pd.DataFrame(data)
    st.line_chart(df.set_index("time")["temp"])
else:
    st.warning("暂无数据")

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