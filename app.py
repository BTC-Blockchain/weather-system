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
# 🌌 科技UI（彻底统一版）
# ======================
st.markdown("""
<style>

html, body, .stApp {
    background: linear-gradient(180deg, #0a0f1c 0%, #05070d 100%);
    color: #e6f7ff;
}

h1 {
    text-align: center;
    color: #00eaff;
    text-shadow: 0 0 20px #00eaff;
}

section[data-testid="stHorizontalBlock"] > div {
    background: rgba(10, 25, 50, 0.55);
    border: 1px solid rgba(0, 234, 255, 0.2);
    border-radius: 14px;
    padding: 18px;
    backdrop-filter: blur(8px);
    box-shadow: 0 0 20px rgba(0,234,255,0.08);
}

h2, h3 {
    color: #00eaff;
}

[data-testid="stMetricValue"] {
    color: #00ffc3;
    font-size: 30px;
}

/* 图表 */
canvas {
    background-color: transparent !important;
}

/* dataframe */
[data-testid="stDataFrame"] {
    background: transparent !important;
}

/* 表格 */
thead tr th {
    color: #00eaff !important;
    background: transparent !important;
}
tbody tr {
    background: transparent !important;
}

/* code块 */
code {
    background: rgba(0,20,40,0.6) !important;
    color: #00ffc3 !important;
    border: 1px solid rgba(0,234,255,0.2);
}

/* 提示框 */
.stSuccess {
    background-color: rgba(0,255,170,0.12);
    color: #00ffcc;
    border: 1px solid #00ffcc;
}

.stWarning {
    background-color: rgba(255,200,0,0.12);
    color: #ffd54f;
    border: 1px solid #ffd54f;
}

.stError {
    background-color: rgba(255,0,80,0.12);
    color: #ff4d6d;
    border: 1px solid #ff4d6d;
}

hr {
    border: 1px solid rgba(0,234,255,0.15);
}

</style>
""", unsafe_allow_html=True)

# ======================
# 时间
# ======================
def now_local():
    return datetime.utcnow() + timedelta(hours=8)

def utc_to_local(day, hour, minute):
    now = datetime.utcnow()
    dt = datetime(now.year, now.month, int(day), int(hour), int(minute))
    return dt + timedelta(hours=8)

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
# 历史数据
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
            raw = m.get("rawOb") or m.get("raw_text")
            obs = m.get("obsTime") or m.get("observation_time")

            if temp and obs:
                dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                if dt.date() == now_local().date():
                    data.append({
                        "metar_time": dt.strftime("%d%H%M"),
                        "time": dt.strftime("%Y-%m-%d %H:%M"),
                        "temp": int(temp),
                        "raw": raw
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
    is_new = False
    source = "CACHE"

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=2).text
        metar = txt.strip().split("\n")[1]

        t = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)

        if t and temp_match:
            source = "REALTIME"
            metar_time = t.group(1)
            temp = int(temp_match.group(1).replace("M", "-"))

            if len(data) == 0 or data[-1]["metar_time"] != metar_time:
                is_new = True
                data.append({
                    "metar_time": metar_time,
                    "time": now_local().strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": metar
                })
                save_cache(data)

    except:
        pass

    return data, is_new, source

# ======================
# 模型
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0
    if data[-1]["temp"] < data[-2]["temp"]:
        return 95

    temps = [x["temp"] for x in data[-5:]]
    acc = (temps[-1] - temps[-2]) - (temps[-2] - temps[-3])
    position = temps[-1] / max(temps)

    score = max(0, -acc)*30 + position*50
    return min(round(score), 100)

# ======================
# 启动
# ======================
data = load_cache()
if not data:
    data = init_today_history()

data, is_new, source = get_today_data()

if not data:
    st.error("❌ 无法获取数据")
    st.stop()

current = data[-1]
max_temp = max(x["temp"] for x in data)

# 延迟
last_dt = pd.to_datetime(current["time"])
delay_min = (now_local() - last_dt).total_seconds()/60
is_delayed = delay_min > 10

# ======================
# 标题
# ======================
st.markdown(f"""
<div style='text-align:center; padding:10px;'>
<h1>🚀 METAR 智能监控终端</h1>
<div style='color:#66d9ff;'>实时气象 · 概率模型 · 信号系统</div>
<div style='font-size:12px;color:#888;'>更新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div style='font-size:12px;color:#666;'>数据来源：METAR(ZSPD) ｜自动刷新｜Design by Kylin</div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

if source == "REALTIME":
    st.success("🟢 数据来源：实时METAR")
else:
    st.warning("🟡 数据来源：缓存")

st.caption(f"⏱ 数据延迟：{int(delay_min)} 分钟")

# ======================
# 三栏
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

# 左
with col1:
    st.markdown("### 🧠 见顶概率")
    prob = peak_probability(data)
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

    st.markdown("### 📊 概率解释")
    st.write("📈 上升中" if len(data)>=2 and data[-1]["temp"]>=data[-2]["temp"] else "🔻 已见顶")

    st.markdown("### 🚨 信号面板")
    if is_delayed:
        st.error(f"🚨 数据延迟：{int(delay_min)} 分钟")
        st.error("🔴 信号已降级")
    else:
        st.success("🟢 上升趋势")

# 中
with col2:
    st.markdown("### 📈 温度曲线")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    st.line_chart(df.set_index("time")["temp"], height=250)

# 右
with col3:
    st.markdown("### 📋 历史数据")
    df_table = pd.DataFrame(data)
    df_table["time"] = pd.to_datetime(df_table["time"])
    df_table = df_table.sort_values(by="time", ascending=False)

    def highlight_latest(row):
        return ['background-color: #003344']*len(row) if row.name==0 else ['']*len(row)

    st.write(df_table.style.apply(highlight_latest, axis=1))

    st.markdown("### 📡 最近METAR")
    for row in reversed(data[-5:]):
        st.markdown(f"""
<div style="background:rgba(0,20,40,0.6);padding:8px;border-radius:8px;border:1px solid rgba(0,234,255,0.2);color:#00ffc3;">
{row["raw"]}
</div>
""", unsafe_allow_html=True)