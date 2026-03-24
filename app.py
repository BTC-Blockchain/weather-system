import streamlit as st
import requests
import pandas as pd
import json
import re
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

st.set_page_config(page_title="METAR监控系统", layout="wide")
st_autorefresh(interval=30000, key="refresh")

# ======================
# 🌤 浅科技UI（已优化）
# ======================
st.markdown("""
<style>
html, body, .stApp {
    background: linear-gradient(180deg, #eef3f8 0%, #e6edf5 100%);
    color: #1f2d3d;
}

h1 {
    text-align: center;
    color: #0b5cff;
}

section[data-testid="stHorizontalBlock"] > div {
    background: rgba(255,255,255,0.75);
    border: 1px solid rgba(0,120,255,0.15);
    border-radius: 12px;
    padding: 15px;
    backdrop-filter: blur(6px);
}

h2, h3 {
    color: #0b5cff;
}

[data-testid="stMetricValue"] {
    color: #0b5cff;
    font-size: 28px;
}

.stSuccess {
    background-color: rgba(0,200,120,0.08);
    color: #00a86b;
}

.stWarning {
    background-color: rgba(255,180,0,0.1);
    color: #cc8800;
}

.stError {
    background-color: rgba(255,60,60,0.08);
    color: #d32f2f;
}

code {
    background: rgba(240,245,250,0.9) !important;
    color: #0b5cff !important;
}
</style>
""", unsafe_allow_html=True)

# ======================
# 时间
# ======================
def now_local():
    return datetime.utcnow() + timedelta(hours=8)

# ======================
# 缓存
# ======================
def load_cache():
    try:
        with open("cache.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_cache(data):
    with open("cache.json", "w") as f:
        json.dump(data, f)

# ======================
# 初始化历史
# ======================
def init_today_history():
    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 24}
        res = requests.get(url, params=params, timeout=3)
        metars = res.json()

        data = []
        for m in metars:
            temp = m.get("temp") or m.get("temp_c")
            obs = m.get("obsTime") or m.get("observation_time")

            if temp and obs:
                dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                if dt.date() == now_local().date():
                    data.append({
                        "time": dt.strftime("%Y-%m-%d %H:%M"),
                        "temp": int(temp),
                        "raw": m.get("rawOb")
                    })

        if len(data) > 5:
            data = sorted(data, key=lambda x: x["time"])
            save_cache(data)
            return data
    except:
        pass

    return load_cache()

# ======================
# 实时
# ======================
def get_today_data():
    data = load_cache()
    source = "CACHE"

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=2).text
        metar = txt.strip().split("\n")[1]

        temp_match = re.search(r' (M?\d{2})/', metar)

        if temp_match:
            source = "REALTIME"
            temp = int(temp_match.group(1).replace("M", "-"))

            data.append({
                "time": now_local().strftime("%Y-%m-%d %H:%M"),
                "temp": temp,
                "raw": metar
            })
            save_cache(data)

    except:
        pass

    return data, source

# ======================
# 模型
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0
    if data[-1]["temp"] < data[-2]["temp"]:
        return 95

    temps = [x["temp"] for x in data[-5:]]
    return min(int(temps[-1] / max(temps) * 100), 100)

# ======================
# 启动
# ======================
data = load_cache()
if not data:
    data = init_today_history()

data, source = get_today_data()

current = data[-1]
max_temp = max(x["temp"] for x in data)

# 找最高时间
max_record = next(x for x in data if x["temp"] == max_temp)
max_time = max_record["time"][-5:]

# ======================
# 标题
# ======================
st.markdown(f"""
<div style='text-align:center;'>
<h1>METAR监控系统</h1>
<div>更新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div style='font-size:12px;'>数据来源：METAR(ZSPD) ｜自动刷新｜Design by Kylin</div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ======================
# 三栏
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

# 左
with col1:
    st.subheader("见顶概率")
    prob = peak_probability(data)
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

# 中
with col2:
    st.subheader("当前")

    col_a, col_b = st.columns(2)

    with col_a:
        st.metric("当前温度", f"{current['temp']}°C")

    with col_b:
        st.metric("今日最高", f"{max_temp}°C", delta=max_time)

    st.subheader("温度曲线")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    st.line_chart(df.set_index("time")["temp"])

# 右
with col3:
    st.subheader("历史数据")
    df_table = pd.DataFrame(data)
    df_table = df_table.sort_values(by="time", ascending=False)
    st.write(df_table)

    st.subheader("最近METAR")
    for row in data[-5:]:
        st.code(row["raw"])