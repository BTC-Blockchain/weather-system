import streamlit.components.v1 as components
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import json
import re
import math
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
/* METAR解码模块样式 */
.metar-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-top: 10px;
}
.metar-item {
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(0, 170, 255, 0.3);
    border-radius: 8px;
    padding: 10px;
    box-shadow: 0 2px 6px rgba(0, 170, 255, 0.1);
    transition: transform 0.2s;
}
.metar-item:hover {
    transform: translateY(-2px);
    border-color: #00aaff;
}
.metar-item-title {
    color: #0077aa;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 5px;
}
.metar-item-value {
    color: #003344;
    font-size: 14px;
    font-weight: 600;
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
# 历史数据（双源修复版：精准拉取本地凌晨数据）
# ======================
def init_today_history():
    # --- 数据源 1：Aviation Weather ---
    try:
        url = "https://aviationweather.gov/api/data/metar"
        # 优化点 1：将抓取时长增加到 48 小时。
        # 这样无论当前是下午还是晚上，都能确保覆盖到"昨天"的 UTC 时间，从而不漏掉本地今天凌晨的数据。
        params = {"ids": "ZSPD", "format": "json", "hours": 48}
        res = requests.get(url, params=params, timeout=3)
        metars = res.json()

        data = []
        for m in metars:
            temp = m.get("temp") or m.get("temp_c")
            raw = m.get("rawOb") or m.get("raw_text")
            obs = m.get("obsTime") or m.get("observation_time")

            if temp and obs:
                dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                # 严格过滤，只保留本地当天的记录
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

    # --- 数据源 2：Ogimet ---
    try:
        now_loc = now_local()
        # 优化点 2：明确获取本地当天的凌晨 00:00
        local_start = datetime(now_loc.year, now_loc.month, now_loc.day, 0, 0)
        # 转换为 Ogimet 需要的 UTC 时间（即前一天的 16:00 UTC）
        utc_start = local_start - timedelta(hours=8)
        
        # 结束时间直接设为当前的 UTC 时间即可
        utc_end = datetime.utcnow()

        # 将正确转换后的 UTC 年/月/日/时 填入 URL 
        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={utc_start.year}&mes={utc_start.month:02d}&day={utc_start.day:02d}&hora={utc_start.hour:02d}&anof={utc_end.year}&mesf={utc_end.month:02d}&dayf={utc_end.day:02d}&horaf={utc_end.hour:02d}&minf=59"
        
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

            # 同样严格过滤本地当天数据
            if dt.date() == now_loc.date():
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
# METAR 解码引擎（进阶版：支持单位自动换算）
# ======================
def decode_metar(raw, obs_time):
    # 步骤 1：初始化数据字典（设定安全默认值）
    data = {
        "time": obs_time,
        "wx": "无显著天气",  # 默认无复杂天气现象
        "wind": "数据缺失",  # 将"未知"改为更专业的"数据缺失"
        "cloud": "晴空",
        "vis": "数据缺失",
        "qnh": "数据缺失",
        "dew": "数据缺失",
        "rh": "数据缺失"
    }
    
    # 步骤 2：解析风速风向 (支持 MPS 和 KT 两种单位)
    # 正则解释：匹配 3位数字或VRB(方向) + 2到3位数字(速度) + 可选的G及阵风速度 + MPS或KT(单位)
    wind_match = re.search(r'\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(MPS|KT)\b', raw)
    if wind_match:
        # 获取风向
        dir_str = "变向" if wind_match.group(1) == "VRB" else f"{wind_match.group(1)}°"
        # 获取风速数值
        speed_raw = int(wind_match.group(2))
        # 获取单位
        unit = wind_match.group(4)
        
        # 核心逻辑：单位转换
        if unit == "KT":
            # 1 节(Knot) = 0.51444 米/秒，保留一位小数
            speed_mps = round(speed_raw * 0.5144, 1)
        else:
            speed_mps = speed_raw # 如果已经是 MPS，则保持不变
            
        data["wind"] = f"{dir_str}  {speed_mps} m/s"
        
    # 步骤 3：解析能见度 (例如 9999, 0800)
    # 增加前后空格限制，防止错误匹配到时间戳等其他4位数字
    vis_match = re.search(r'\s(\d{4})\s', raw + " ") 
    if vis_match:
        vis = vis_match.group(1)
        data["vis"] = "> 10 公里" if vis == "9999" else f"{vis} 米"
        
    # 步骤 4：解析云况
    clouds = re.findall(r'\b(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?\b', raw)
    if clouds:
        cloud_map = {"FEW": "少云", "SCT": "疏云", "BKN": "多云", "OVC": "阴天", "VV": "垂直能见度"}
        # 将飞行高度层(FL)转换为大致的米 (x30)
        c_list = [f"{cloud_map.get(c[0], c[0])} {int(c[1])*30}m" for c in clouds]
        data["cloud"] = " / ".join(c_list)
    elif "CAVOK" in raw:
        # CAVOK 代表能见度好、无云、无复杂天气
        data["cloud"] = "晴空良好 (CAVOK)"
        data["vis"] = "> 10 公里"
        
    # 步骤 5：解析气压 (例如 Q1018)
    qnh_match = re.search(r'\bQ(\d{4})\b', raw)
    if qnh_match:
        data["qnh"] = f"{qnh_match.group(1)} hPa"
        
    # 步骤 6：解析温度、露点，并计算相对湿度
    temp_match = re.search(r'\b(M?\d{2})/(M?\d{2})\b', raw)
    if temp_match:
        t = int(temp_match.group(1).replace("M", "-"))
        td = int(temp_match.group(2).replace("M", "-"))
        data["dew"] = f"{td}°C"
        
        # 使用马格努斯公式 (Magnus formula) 计算相对湿度
        es = 6.112 * math.exp((17.67 * t) / (t + 243.5))
        e = 6.112 * math.exp((17.67 * td) / (td + 243.5))
        rh = max(0, min(100, (e / es) * 100))
        data["rh"] = f"{int(rh)}%"
        
    # 步骤 7：解析特殊天气现象 (扫描常见标识符)
    wx_map = {"-RA": "小雨", "RA": "中雨", "+RA": "大雨", "SN": "降雪", "DZ": "毛毛雨", 
              "FG": "大雾", "BR": "轻雾", "HZ": "霾", "TS": "雷暴", "VCTS": "周边雷暴", "SHRA": "阵雨"}
    wx_list = []
    for code, name in wx_map.items():
        if re.search(r'\b' + re.escape(code) + r'\b', raw):
            wx_list.append(name)
    
    # 如果找到了匹配的天气现象，就会覆盖掉初始的"无显著天气"
    if wx_list:
        data["wx"] = ", ".join(wx_list)
        
    return data
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
# 🔊 声音系统（终极修复版）
# ======================
if "audio_unlocked" not in st.session_state:
    st.session_state.audio_unlocked = False

if st.button("🔊 启用声音提醒"):
    st.session_state.audio_unlocked = True
    # 更换为极其稳定、无防盗链的 Google 官方测试提示音
    test_audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
    st.markdown(f'<audio autoplay><source src="{test_audio_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    st.success("✅ 声音提醒已解锁！您刚才应该已经听到了一声测试的“滴”声。")

# ✅ 直接利用你原本代码中完美的 is_new 变量，最精准！
if st.session_state.audio_unlocked and is_new:
    # 加上时间戳防止浏览器缓存，确保每次新数据都响
    alert_url = f"https://actions.google.com/sounds/v1/alarms/beep_short.ogg?t={datetime.utcnow().timestamp()}"
    st.markdown(f'<audio autoplay><source src="{alert_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    
    # 加上一个视觉弹窗，做双重保障
    st.toast("🔔 抓取到新 METAR 数据，已触发声音警报！", icon="🔊")

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
            
 # === METAR 解码 ===     
    st.markdown("---")
    st.markdown("### 🔍 METAR 解码")
    
    # 提取并解码最新一条数据
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
        st.metric("当前温度", f"{current['temp']}°C")

    with col_b:
        st.metric("截至当前已捕获的今日最高温度", f"{max_temp}°C", delta=max_time_str)

    st.markdown(f"**METAR最新发布：{formatted_time}**")

    st.info("📌 当系统启动运行将自动获取当天0点开始的历史数据以填充温度图")
st.markdown("### 📈 温度曲线")
    
    # 准备数据
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    
    # 创建 Plotly 科技感图表
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df["time"], 
        y=df["temp"],
        mode='lines+markers',
        name='温度',
        # 设置线条颜色、粗细和平滑度(spline)
        line=dict(color='#00aaff', width=3, shape='spline'),
        # 设置数据点标记的样式
        marker=dict(size=6, color='#0077aa', symbol='circle', line=dict(color='white', width=1)),
        # 添加曲线下方的半透明浅蓝填充，增加全息科技感
        fill='tozeroy',
        fillcolor='rgba(0, 170, 255, 0.15)',
        # 自定义悬停提示框格式
        hovertemplate='时间: %{x|%H:%M}<br>温度: %{y}°C<extra></extra>'
    ))
    
    # 优化布局与背景
    fig.update_layout(
        height=350,  # 控制图表高度
        margin=dict(l=0, r=0, t=10, b=0),  # 消除多余边距
        plot_bgcolor='rgba(0,0,0,0)',  # 图表背景透明
        paper_bgcolor='rgba(0,0,0,0)', # 画布背景透明
        xaxis=dict(
            showgrid=True, 
            gridcolor='rgba(0, 170, 255, 0.1)', # 浅蓝色网格线
            tickformat='%H:%M', # X轴只显示小时:分钟
            color='#0077aa' # 坐标轴字体颜色
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(0, 170, 255, 0.1)',
            title='温度 (°C)',
            titlefont=dict(color='#0077aa'),
            color='#0077aa',
            zeroline=False # 隐藏Y轴0刻度粗线
        ),
        hovermode='x unified' # 开启科技感极强的全局悬停参考线
    )
    
    # 使用 Streamlit 渲染图表
    st.plotly_chart(fig, use_container_width=True)


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
