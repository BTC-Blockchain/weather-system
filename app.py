import streamlit.components.v1 as components
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import re
import math
from datetime import datetime, timedelta, timezone 
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. 页面基础配置 (必须作为第一个 Streamlit 命令执行)
# =========================================================
st.set_page_config(page_title="METAR监控系统", layout="wide")

# =========================================================
# 2. 功能函数定义
# =========================================================
def now_local():
    """获取北京时间 (UTC+8)"""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)

# =========================================================
# 3. 自动刷新与 CSS 注入 (极致紧凑布局)
# =========================================================
st_autorefresh(interval=30000, key="refresh")

st.markdown("""
    <style>
        header[data-testid="stHeader"] { visibility: hidden; height: 0px; }
        .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; margin-top: -35px !important; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div style='text-align:center; margin-top: -20px; padding-top: 0px;'>
        <h1 style='margin: 0px; padding: 0px; color: #00aaff; font-size: 34px;'>🚀 METAR 智能监控终端</h1>
        <p style='margin: 5px 0; color: #00aaff; font-size: 16px; font-weight: bold;'>实时气象 · 概率模型 · 信号系统</p>
        <p style='margin: 2px 0; font-size: 14px; color: #888; font-weight: bold;'>更新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p style='margin: 2px 0; font-size: 14px; color: #666; font-weight: bold;'>数据来源：METAR(ZSPD) ｜ 系统每30S自动刷新 ｜ Design by Kylin</p>
    </div>
""", unsafe_allow_html=True)

# ======================
# 🌌 科幻UI样式（优化为浅色）
# ======================
st.markdown("""
<style>
body, .stApp { background: linear-gradient(135deg, #e6f7ff, #f0fbff, #ffffff); color: #003344; }
[data-testid="stAppViewBlockContainer"] { padding-top: 1rem !important; padding-bottom: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; }
h1 { text-align: center; color: #00aaff; text-shadow: 0 0 6px rgba(0,170,255,0.4); }
section[data-testid="stHorizontalBlock"] > div { background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(0, 170, 255, 0.3); border-radius: 15px; backdrop-filter: blur(10px); padding: 20px; box-shadow: 0 8px 32px rgba(0, 170, 255, 0.1); transition: all 0.3s ease; }
@keyframes border-glow { 0% { border-color: rgba(0, 170, 255, 0.3); box-shadow: 0 0 5px rgba(0, 170, 255, 0.1); } 50% { border-color: rgba(0, 170, 255, 0.6); box-shadow: 0 0 15px rgba(0, 170, 255, 0.3); } 100% { border-color: rgba(0, 170, 255, 0.3); box-shadow: 0 0 5px rgba(0, 170, 255, 0.1); } }
section[data-testid="stHorizontalBlock"] > div:hover { animation: border-glow 2s infinite ease-in-out; }
[data-testid="stMetricValue"] { color: #0099cc; font-size: 28px; }
h2, h3 { color: #0077aa; }
.stSuccess { background-color: rgba(0,200,150,0.15); color: #009966; border: 1px solid #00aa88; }
.stWarning { background-color: rgba(255,180,0,0.15); color: #cc8800; border: 1px solid #ffaa00; }
.stError { background-color: rgba(255,0,80,0.12); color: #cc0033; border: 1px solid #ff4d6d; }
[data-testid="stMetric"] { background: linear-gradient(to right, rgba(0,170,255,0.05), transparent); padding: 10px; border-radius: 10px; }
.metar-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 10px; }
.metar-item { background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(0, 170, 255, 0.3); border-radius: 8px; padding: 10px; box-shadow: 0 2px 6px rgba(0, 170, 255, 0.1); transition: transform 0.2s; }
.metar-item:hover { transform: translateY(-2px); border-color: #00aaff; }
.metar-item-title { color: #0077aa; font-size: 12px; font-weight: bold; margin-bottom: 5px; display: flex; align-items: center; gap: 5px; }
.metar-item-value { color: #003344; font-size: 14px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

def utc_to_local(day_str, hour_str, min_str):
    now = now_local()
    day, hour, minute = int(day_str), int(hour_str), int(min_str)
    try:
        utc_dt = datetime(now.year, now.month, day, hour, minute)
        if utc_dt > datetime.now().replace(tzinfo=None) + timedelta(hours=2): 
            raise ValueError("Future date")
    except ValueError:
        first_of_this_month = now.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        utc_dt = datetime(last_month_end.year, last_month_end.month, day, hour, minute)
    return utc_dt + timedelta(hours=8)

def load_cache():
    try:
        with open("cache.json", "r") as f: return json.load(f)
    except:
        return []

def save_cache(data):
    with open("cache.json", "w") as f: json.dump(data, f)

def init_today_history():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 48}
        res = requests.get(url, params=params, headers=headers, timeout=15)
        metars = res.json()
        data = []
        for m in metars:
            temp = m.get("temp") or m.get("temp_c")
            raw = m.get("rawOb") or m.get("raw_text")
            obs = m.get("obsTime") or m.get("observation_time")
            if temp is not None and obs:
                dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                if dt.date() == now_local().date():
                    data.append({"metar_time": dt.strftime("%d%H%M"), "time": dt.strftime("%Y-%m-%d %H:%M"), "temp": int(temp), "raw": raw})
        if len(data) >= 1:
            data = sorted(data, key=lambda x: x["time"])
            save_cache(data)
            return data
    except Exception as e:
        print(f"⚠️ 历史源1抓取跳过: {e}")

    try:
        now_loc = now_local()
        local_start = now_loc.replace(hour=0, minute=0, second=0, microsecond=0)
        utc_start = local_start - timedelta(hours=8)
        utc_end = datetime.now(timezone.utc).replace(tzinfo=None)
        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={utc_start.year}&mes={utc_start.month:02d}&day={utc_start.day:02d}&hora={utc_start.hour:02d}&anof={utc_end.year}&mesf={utc_end.month:02d}&dayf={utc_end.day:02d}&horaf={utc_end.hour:02d}&minf=59"
        text = requests.get(url, headers=headers, timeout=15).text
        data = []
        for line in text.split("\n"):
            if "ZSPD" not in line: continue
            t = re.search(r'(\d{2})(\d{2})(\d{2})Z', line)
            temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', line)
            if not t or not temp_match: continue
            day, hour, minute = t.groups()
            temp = int(temp_match.group(1).replace("M", "-"))
            dt = utc_to_local(day, hour, minute)
            if dt.date() == now_loc.date():
                data.append({"metar_time": f"{day}{hour}{minute}", "time": dt.strftime("%Y-%m-%d %H:%M"), "temp": temp, "raw": line.strip()})
        if len(data) >= 1:
            data = sorted(data, key=lambda x: x["time"])
            save_cache(data)
            return data
    except Exception as e:
        print(f"❌ 历史源2最终失败: {e}")
    return load_cache()

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
                data.append({"metar_time": metar_time, "time": now_local().strftime("%Y-%m-%d %H:%M"), "temp": temp, "raw": metar})
                save_cache(data)
    except:
        pass
    return data, is_new, source

def decode_metar(raw, obs_time):
    data = {"time": obs_time, "wx": "无显著天气", "wind": "数据缺失", "cloud": "晴空", "vis": "数据缺失", "qnh": "数据缺失", "dew": "数据缺失", "rh": "数据缺失"}
    wind_match = re.search(r'\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(MPS|KT)\b', raw)
    if wind_match:
        dir_str = "变向" if wind_match.group(1) == "VRB" else f"{wind_match.group(1)}°"
        speed_mps = round(int(wind_match.group(2)) * 0.5144, 1) if wind_match.group(4) == "KT" else int(wind_match.group(2))
        data["wind"] = f"{dir_str}  {speed_mps} m/s"
    vis_match = re.search(r'\s(\d{4})\s', raw + " ") 
    if vis_match:
        data["vis"] = "> 10 公里" if vis_match.group(1) == "9999" else f"{vis_match.group(1)} 米"
    clouds = re.findall(r'\b(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?\b', raw)
    if clouds:
        cloud_map = {"FEW": "少云", "SCT": "疏云", "BKN": "多云", "OVC": "阴天", "VV": "垂直能见度"}
        data["cloud"] = " / ".join([f"{cloud_map.get(c[0], c[0])} {int(c[1])*30}m" for c in clouds])
    elif "CAVOK" in raw:
        data["cloud"] = "晴空良好 (CAVOK)"
        data["vis"] = "> 10 公里"
    qnh_match = re.search(r'\bQ(\d{4})\b', raw)
    if qnh_match: data["qnh"] = f"{qnh_match.group(1)} hPa"
    temp_match = re.search(r'\b(M?\d{2})/(M?\d{2})\b', raw)
    if temp_match:
        t, td = int(temp_match.group(1).replace("M", "-")), int(temp_match.group(2).replace("M", "-"))
        data["dew"] = f"{td}°C"
        es, e = 6.112 * math.exp((17.67 * t) / (t + 243.5)), 6.112 * math.exp((17.67 * td) / (td + 243.5))
        data["rh"] = f"{int(max(0, min(100, (e / es) * 100)))}%"
    wx_map = {"-RA": "小雨", "RA": "中雨", "+RA": "大雨", "SN": "降雪", "DZ": "毛毛雨", "FG": "大雾", "BR": "轻雾", "HZ": "霾", "TS": "雷暴", "VCTS": "周边雷暴", "SHRA": "阵雨"}
    wx_list = [name for code, name in wx_map.items() if re.search(r'\b' + re.escape(code) + r'\b', raw)]
    if wx_list: data["wx"] = ", ".join(wx_list)
    return data

def peak_probability(data):
    if len(data) < 5: return 0
    if data[-1]["temp"] < data[-2]["temp"]: return 95
    temps = [x["temp"] for x in data[-5:]]
    acc = (temps[-1] - temps[-2]) - (temps[-2] - temps[-3])
    score = max(0, -acc) * 30 + (temps[-1] / max(temps)) * 50
    return min(round(score), 100)

# ======================
# 启动与核心逻辑
# ======================
delay_min = 0  
is_delayed = False
is_new = False
source = "UNKNOWN"
current = None 
data = load_cache()

if len(data) < 1:
    st.toast("正在尝试补全今日历史报文...", icon="🔄")
    data = init_today_history()

data, is_new, source = get_today_data()

if not data:
    st.error("❌ 无法获取任何数据，请检查网络连接或 API 状态")
    st.stop()

# ======================
# 💡 修复重点：计算所有必须的 UI 变量
# ======================
current = data[-1]
formatted_time = current["time"]

# 计算最高温度及其时间
max_record = max(data, key=lambda x: x["temp"])
max_temp = max_record["temp"]
max_time_str = max_record["time"].split(" ")[1] if " " in max_record["time"] else max_record["time"]

# 计算延迟时间
try:
    last_dt = datetime.strptime(formatted_time, "%Y-%m-%d %H:%M")
    delay_min = (now_local() - last_dt).total_seconds() / 60
    # 如果超过 40 分钟未更新，视为延迟（标准 METAR 通常30分钟更新）
    is_delayed = delay_min > 40  
except Exception as e:
    delay_min = 0
    is_delayed = False

# ======================
# 🔊 声音系统
# ======================
if "audio_unlocked" not in st.session_state:
    st.session_state.audio_unlocked = False

if st.button("🔊 启用声音提醒"):
    st.session_state.audio_unlocked = True
    test_audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
    st.markdown(f'<audio autoplay><source src="{test_audio_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    st.success("✅ 声音提醒已解锁！您刚才应该已经听到了一声测试的“滴”声。")

if st.session_state.audio_unlocked and is_new:
    alert_url = f"https://actions.google.com/sounds/v1/alarms/beep_short.ogg?t={datetime.now(timezone.utc).timestamp()}"
    st.markdown(f'<audio autoplay><source src="{alert_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    st.toast("🔔 抓取到新 METAR 数据，已触发声音警报！", icon="🔊")

delay_info = f"**{int(delay_min)}** 分钟" 
space = "&nbsp;" * 80

if source == "REALTIME":
    st.success(f" {space} 🟢 数据来源：实时METAR {space} ⌛⌛截至当前时间，距离上一次获取实时数据已经延迟：{delay_info}")
else:
    st.warning(f"🟡 数据来源：缓存 (🚨🚨注意，缓存数据无意义,联系作者排查数据原因: {delay_info})")

if is_new and len(data) >= 2:
    prev_temp, curr_temp = data[-2]["temp"], data[-1]["temp"]
    delta_temp = curr_temp - prev_temp
    if delta_temp > 0: st.success(f"🟢 新数据：{prev_temp}°C → {curr_temp}°C（+{delta_temp}°C）")
    elif delta_temp < 0: st.error(f"🔻 新数据：{prev_temp}°C → {curr_temp}°C（{delta_temp}°C）")
    else: st.info(f"➖ 新数据：{curr_temp}°C（无变化）")

# ======================
# 三栏UI
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

with col1:
    st.markdown("### 🧠 见顶概率")
    prob = peak_probability(data)
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

    st.markdown("### 📊 概率解释")
    if len(data) >= 2:
        if data[-1]["temp"] < data[-2]["temp"]: st.write("🔻 已下降（已见顶）")
        else: st.write("📈 上升中")

    st.markdown("### 🚨 信号面板")
    if is_delayed:
        st.error(f"🚨 数据延迟：{int(delay_min)} 分钟")
        st.error("🔴 信号已降级")
    else:
        if prob >= 90: st.error("🔴 强卖")
        elif prob > 60: st.warning("🟡 接近顶部")
        else: st.success("🟢 上升趋势")
            
    st.markdown("---")
    st.markdown("### 🔍 METAR 解码")
    
    decoded = decode_metar(current["raw"], formatted_time)
    
    html_content = f"""
    <div class="metar-grid">
        <div class="metar-item" style="grid-column: span 2;">
            <div class="metar-item-title">🕒 观测时间</div>
            <div class="metar-item-value">{decoded['time']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">🌬️ 风速风向</div>
            <div class="metar-item-value">{decoded['wind']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">👁️ 能见度</div>
            <div class="metar-item-value">{decoded['vis']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">☁️ 云况</div>
            <div class="metar-item-value">{decoded['cloud']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">⏱️ 气压 (QNH)</div>
            <div class="metar-item-value">{decoded['qnh']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">💧 相对湿度</div>
            <div class="metar-item-value">{decoded['rh']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">🌡️ 露点</div>
            <div class="metar-item-value">{decoded['dew']}</div>
        </div>
        <div class="metar-item" style="grid-column: span 2; background: rgba(0, 170, 255, 0.05);">
            <div class="metar-item-title">⛈️ 当前天气</div>
            <div class="metar-item-value">{decoded['wx']}</div>
        </div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

with col2:
    st.markdown("### 📡 当前数据")
    col_a, col_b = st.columns(2)

    with col_a:
        temp_style = """
        <style>
            .temp-container { text-align: left; font-family: 'Inter', sans-serif; margin-bottom: 20px; }
            .temp-label { font-size: 16px; color: #888; margin-bottom: 4px; }
            .temp-value { font-size: 52px; font-weight: 450; color: #00aaff; line-height: 1.2; text-shadow: 0px 0px 10px rgba(0, 170, 255, 0.3); }
        </style>
        """
        st.markdown(temp_style, unsafe_allow_html=True)
        st.markdown(f"""
            <div class="temp-container">
                <div class="temp-label">当前温度</div>
                <div class="temp-value">{current['temp']}°C</div>
            </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.metric("截至当前已捕获的今日最高温度", f"{max_temp}°C", delta=f"捕获发生在：{max_time_str}")

    st.markdown(f"**METAR最新发布：{formatted_time}**")
    st.info("📌 当系统启动运行将自动获取当天0点开始的历史数据以填充温度图")
    st.markdown("### 📈 温度曲线")    
    
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["temp"], mode='lines+markers', name='温度',
        line=dict(color='#00aaff', width=3, shape='spline'),
        marker=dict(size=6, color='#0077aa', symbol='circle', line=dict(color='white', width=1)),
        fill='tozeroy', fillcolor='rgba(0, 170, 255, 0.15)',
        hovertemplate='时间: %{x|%H:%M}<br>温度: %{y}°C<extra></extra>'
    ))
    
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
        xaxis=dict(showgrid=True, gridcolor='rgba(0, 170, 255, 0.1)', tickformat='%H:%M', tickfont=dict(color='#0077aa')),
        yaxis=dict(showgrid=True, gridcolor='rgba(0, 170, 255, 0.1)', title=dict(text='温度 (°C)', font=dict(color='#0077aa')), tickfont=dict(color='#0077aa'), zeroline=False),
        hovermode='x unified' 
    )

    st.plotly_chart(fig, width="stretch")

    st.markdown("### 🧩 数据完整性")
    gaps = [1 for i in range(1, len(data)) if (pd.to_datetime(data[i]["time"]) - pd.to_datetime(data[i-1]["time"])).total_seconds()/60 > 60]

    if not gaps:
        status_color, status_bg, border_c, status_text = "#009966", "rgba(0,200,150,0.1)", "#00aa88", "🟢 数据链条完整"
    else:
        status_color, status_bg, border_c, status_text = "#cc0033", "rgba(255,0,80,0.1)", "#ff4d6d", f"🔴 检测到 {len(gaps)} 处缺失"

    integrity_html = f"""
    <div style="background:{status_bg}; border:1px solid {border_c}; border-radius:12px; padding:15px; min-height:228px; display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 4px 12px rgba(0,170,255,0.1);">
        <div style="font-size:30px; font-weight:bold; color:{status_color}; text-align:center; margin-bottom:10px;">{status_text}</div>
        <div style="display:flex; justify-content:space-between; border-top:1px dashed rgba(0,170,255,0.2); padding-top:12px;">
            <div style="text-align:left;"><span style="font-size:20px; color:#888;">捕获样本</span><br><span style="font-size:40px; color:#0077aa; font-weight:900;">{len(data)}</span><span style="font-size:30px; color:#666;"> 条</span></div>
            <div style="text-align:right;"><span style="font-size:20px; color:#888;">防御状态</span><br><span style="font-size:30px; color:{status_color}; font-weight:bold;">实时监控中 🛡️</span></div>
        </div>
    </div>
    """
    st.markdown(integrity_html, unsafe_allow_html=True)

with col3:
    st.markdown("### 📋 历史数据")
    if data:
        df_raw = pd.DataFrame(data)
        df_raw["time_dt"] = pd.to_datetime(df_raw["time"])
        df_raw = df_raw.sort_values(by="time_dt", ascending=False).reset_index(drop=True)

        table_style = """<style>
.custom-table-wrapper { max-height: 380px; overflow-y: auto; border: 1px solid rgba(0, 170, 255, 0.4); border-radius: 10px; background: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(230, 247, 255, 0.4)); box-shadow: 0 4px 15px rgba(0, 170, 255, 0.1); margin-bottom: 15px; }
.custom-table-wrapper::-webkit-scrollbar { width: 6px; }
.custom-table-wrapper::-webkit-scrollbar-track { background: rgba(230, 247, 255, 0.2); border-radius: 10px; }
.custom-table-wrapper::-webkit-scrollbar-thumb { background: rgba(0, 170, 255, 0.4); border-radius: 10px; }
.sci-fi-table { width: 100%; border-collapse: collapse; font-size: 15px; color: #003344; text-align: center; }
.sci-fi-table thead th { position: sticky; top: 0; background: rgba(230, 247, 255, 0.95); backdrop-filter: blur(5px); color: #0077aa; padding: 12px 8px; border-bottom: 2px solid #00aaff; z-index: 2; font-weight: bold; }
.sci-fi-table tbody td { padding: 10px 8px; border-bottom: 1px solid rgba(0, 170, 255, 0.15); }
.highlight-top-row { background: linear-gradient(90deg, rgba(0, 170, 255, 0.2) 0%, rgba(0, 170, 255, 0.05) 100%) !important; border-left: 4px solid #00aaff; font-weight: bold; color: #005588; }
</style>"""

        rows_html = "".join([f"<tr {'class=\"highlight-top-row\"' if i == 0 else ''}><td>{row['time_dt'].strftime('%Y-%m-%d %H:%M')}</td><td>{row['temp']}°C</td><td>{row['metar_time']}</td></tr>\n" for i, row in df_raw.iterrows()])

        full_html = f"""{table_style}
<div class="custom-table-wrapper"><table class="sci-fi-table"><thead><tr><th>观测时间</th><th>温度</th><th>原始报文时间</th></tr></thead><tbody>{rows_html}</tbody></table></div>"""
        st.markdown(full_html, unsafe_allow_html=True)
    else:
        st.info("⌛ 暂无历史观测数据")

    st.markdown("---")
    st.markdown("### 📡 最近METAR")
    
    if data:
        metar_blocks = "".join([f'<div style="background: rgba(0, 170, 255, 0.05); border-left: 4px solid #00aaff; padding: 8px; margin-bottom: 6px; border-radius: 4px; transition: all 0.2s ease;"><span style="color: #0077aa; font-size: 15px; font-weight: bold;">● {pd.to_datetime(row["time"]).strftime("%Y-%m-%d %H:%M:%S")}</span><br><code style="color: #003344; font-size: 11px; background: transparent;">{row["raw"]}</code></div>\n' for row in reversed(data[-10:])])
        st.markdown(f'<div style="max-height: 450px; overflow-y: auto; padding-right: 5px;">\n{metar_blocks}\n</div>', unsafe_allow_html=True)

# =========================================================
# 🏛️ 模块：Wunderground 官方结算参考
# =========================================================
st.markdown("---") 
st.markdown("### 🏛️ Wunderground 官方结算参考")

target_date = now_local().strftime('%Y-%m-%d')
wunderground_url = f"https://www.wunderground.com/history/daily/cn/shanghai/ZSPD/date/{target_date}"

settlement_html = f"""
<div style="background: rgba(255, 255, 255, 0.8); border: 2px solid #ffaa00; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(255, 170, 0, 0.15); font-family: sans-serif;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h4 style="margin: 0; color: #cc8800;">⚠️ Polymarket 结算预言机校验</h4>
            <p style="margin: 5px 0; font-size: 14px; color: #666;">
                当前监控站点：<b>ZSPD (Pudong Intl)</b> | 结算基准日期：<b>{target_date}</b>
            </p>
        </div>
        <a href="{wunderground_url}" target="_blank" style="text-decoration: none; background: #ffaa00; color: white; padding: 10px 20px; border-radius: 8px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">打开 Wunderground 官方页 🔗</a>
    </div>
</div>
"""
st.markdown(settlement_html, unsafe_allow_html=True)

with st.expander("👁️ 快速预览 Wunderground 表格 (若加载失败请点击上方按钮)"):
    st.iframe(wunderground_url, height=600, scrolling=True)
