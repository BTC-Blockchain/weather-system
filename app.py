import streamlit.components.v1 as components
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
# 🌌 科幻UI样式（优化为浅色）
# ======================
st.markdown("""
<style>
body, .stApp {
    background: linear-gradient(135deg, #e6f7ff, #f0fbff, #ffffff);
    color: #003344;
}

h1 {
    text-align: center;
    color: #00aaff;
    text-shadow: 0 0 6px rgba(0,170,255,0.4);
}

section[data-testid="stHorizontalBlock"] > div {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(0, 170, 255, 0.2);
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 12px rgba(0, 170, 255, 0.15);
}

[data-testid="stMetricValue"] {
    color: #0099cc;
    font-size: 28px;
}

h2, h3 {
    color: #0077aa;
}

.stSuccess {
    background-color: rgba(0,200,150,0.15);
    color: #009966;
    border: 1px solid #00aa88;
}

.stWarning {
    background-color: rgba(255,180,0,0.15);
    color: #cc8800;
    border: 1px solid #ffaa00;
}

.stError {
    background-color: rgba(255,0,80,0.12);
    color: #cc0033;
    border: 1px solid #ff4d6d;
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
# 历史数据（双源）
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

    try:
        now = now_local()
        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={now.year}&mes={now.month}&day={now.day}&hora=00&anof={now.year}&mesf={now.month}&dayf={now.day}&horaf=23&minf=59"
        text = requests.get(url, timeout=3).text
        lines = text.split("\n")

        data = []
        for line in lines:
            if "ZSPD" not in line:
                continue

            t = re.search(r'(\d{2})(\d{2})(\d{2})Z', line)
            temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', line)

            if not t or not temp_match:
                continue

            day, hour, minute = t.groups()
            temp = int(temp_match.group(1).replace("M", "-"))
            dt = utc_to_local(day, hour, minute)

            if dt.date() == now.date():
                data.append({
                    "metar_time": f"{day}{hour}{minute}",
                    "time": dt.strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": line.strip()
                })

        if len(data) > 5:
            data = sorted(data, key=lambda x: x["time"])
            save_cache(data)
            return data
    except:
        pass

    return load_cache()

# ======================
# 实时数据
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

    score = 0
    score += max(0, -acc) * 30
    score += position * 50

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

dt_current = pd.to_datetime(current["time"])
formatted_time = dt_current.strftime("%Y年%m月%d日 %H:%M:%S")

max_record = next(x for x in data if x["temp"] == max_temp)
max_dt = pd.to_datetime(max_record["time"])
max_time_str = max_dt.strftime("%H:%M:%S")

last_dt = pd.to_datetime(current["time"])
delay_min = (now_local() - last_dt).total_seconds() / 60
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


# ======================
# 🔊 声音系统（修复版）
# ======================
if "audio_unlocked" not in st.session_state:
    st.session_state.audio_unlocked = False

# 初始化时，将当前最新的数据时间记录下来，避免解锁瞬间误报
if "last_alert_metar" not in st.session_state:
    st.session_state.last_alert_metar = current["metar_time"]

if st.button("🔊 启用声音提醒"):
    st.session_state.audio_unlocked = True
    # 使用 HTML5 原生 audio 标签播放解锁提示音
    st.markdown("""
    <audio autoplay style="display:none;">
        <source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg">
    </audio>
    """, unsafe_allow_html=True)
    st.success("声音提醒已解锁！获取到新数据时将自动播放提示音。")

# ✅ 新数据触发逻辑
if (
    st.session_state.audio_unlocked
    and current["metar_time"] != st.session_state.last_alert_metar
):
    # 更新最后一次提醒的时间记录
    st.session_state.last_alert_metar = current["metar_time"]

    # 播放新数据提示音（添加时间戳参数防止浏览器缓存导致不播放）
    st.markdown(f"""
    <audio autoplay style="display:none;">
        <source src="https://www.soundjay.com/buttons/sounds/button-3.mp3?t={datetime.utcnow().timestamp()}" type="audio/mpeg">
    </audio>
    """, unsafe_allow_html=True)

# 数据来源
if source == "REALTIME":
    st.success("🟢 数据来源：实时METAR")
else:
    st.warning("🟡 数据来源：缓存")

st.caption(f"⏱ 数据延迟：{int(delay_min)} 分钟")

# 🔔 新数据提醒
if is_new and len(data) >= 2:
    prev_temp = data[-2]["temp"]
    curr_temp = data[-1]["temp"]
    delta_temp = curr_temp - prev_temp

    if delta_temp > 0:
        st.success(f"🟢 新数据：{prev_temp}°C → {curr_temp}°C（+{delta_temp}°C）")
    elif delta_temp < 0:
        st.error(f"🔻 新数据：{prev_temp}°C → {curr_temp}°C（{delta_temp}°C）")
    else:
        st.info(f"➖ 新数据：{curr_temp}°C（无变化）")

# ======================
# 三栏（完全未改）
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

with col1:
    st.markdown("### 🧠 见顶概率")
    prob = peak_probability(data)
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

    st.markdown("### 📊 概率解释")
    if len(data) >= 2:
        if data[-1]["temp"] < data[-2]["temp"]:
            st.write("🔻 已下降（已见顶）")
        else:
            st.write("📈 上升中")

    st.markdown("### 🚨 信号面板")
    if is_delayed:
        st.error(f"🚨 数据延迟：{int(delay_min)} 分钟")
        st.error("🔴 信号已降级")
    else:
        if prob >= 90:
            st.error("🔴 强卖")
        elif prob > 60:
            st.warning("🟡 接近顶部")
        else:
            st.success("🟢 上升趋势")

with col2:
    st.markdown("### 📡 当前数据")
    
    col_a, col_b = st.columns(2)

    with col_a:
        st.metric("当前温度", f"{current['temp']}°C")

    with col_b:
        st.metric("今日最高", f"{max_temp}°C", delta=max_time_str)

    st.markdown(f"**METAR最新发布：{formatted_time}**")

    st.markdown("### 📈 温度曲线")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    st.line_chart(df.set_index("time")["temp"])

    st.info("📌 夜间无数据属正常（观测频率降低）")

    st.markdown("### 🧩 数据完整性")
    gaps = []
    for i in range(1, len(data)):
        t1 = pd.to_datetime(data[i-1]["time"])
        t2 = pd.to_datetime(data[i]["time"])
        if (t2 - t1).total_seconds()/60 > 60:
            gaps.append(1)

    if not gaps:
        st.success("数据完整")
    else:
        st.error(f"缺失 {len(gaps)} 处")

with col3:
    st.markdown("### 📋 历史数据")

    df_table = pd.DataFrame(data)
    df_table["time"] = pd.to_datetime(df_table["time"])
    df_table = df_table.sort_values(by="time", ascending=False).reset_index(drop=True)

    def highlight_latest(row):
        if row.name == 0:
            return ['background-color: #d4edda'] * len(row)
        return [''] * len(row)

    st.write(df_table.style.apply(highlight_latest, axis=1))

    st.markdown("### 📡 最近METAR")
    for row in reversed(data[-5:]):
        st.markdown(f"**🕒 {row['time']} (UTC+8)**")
        st.code(row["raw"])