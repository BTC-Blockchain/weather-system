# ======================
# 历史数据（全天候无死角兜底版）
# ======================
def init_today_history():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # 禁用SSL警告
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    aviation_data = []

    # --- 数据源 1：Aviation Weather ---
    try:
        url = "https://aviationweather.gov/api/data/metar?ids=ZSPD&format=json&hours=48"
        # 增加 verify=False 绕过证书阻拦，增加 timeout 到 10s
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        
        if res.status_code == 200:
            metars = res.json()
            for m in metars:
                temp = m.get("temp") if m.get("temp") is not None else m.get("temp_c")
                raw = m.get("rawOb") or m.get("raw_text")
                obs = m.get("obsTime") or m.get("observation_time")

                if temp is not None and obs:
                    dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                    if dt.date() == now_local().date():
                        aviation_data.append({
                            "metar_time": dt.strftime("%d%H%M"),
                            "time": dt.strftime("%Y-%m-%d %H:%M"),
                            "temp": int(temp),
                            "raw": raw
                        })

            if len(aviation_data) > 0:
                aviation_data = sorted(aviation_data, key=lambda x: x["time"])
                first_time = datetime.strptime(aviation_data[0]["time"], "%Y-%m-%d %H:%M")
                
                # 如果数据不完整，提示去 Ogimet 补充，但【保留已获取的 aviation_data】
                if now_local().hour >= 3 and first_time.hour > 1:
                    st.toast("Aviation 数据不完整，尝试使用 Ogimet 补充", icon="🔄")
                else:
                    return aviation_data
        else:
            st.toast(f"Aviation 状态码异常: {res.status_code}", icon="⚠️")
    except Exception as e:
        st.toast(f"Aviation 请求异常: 正在重试备用源...", icon="⚠️")

    # --- 数据源 2：Ogimet ---
    try:
        now_loc = now_local()
        local_start = datetime(now_loc.year, now_loc.month, now_loc.day, 0, 0)
        utc_start = local_start - timedelta(hours=8)
        utc_end = datetime.utcnow()

        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={utc_start.year}&mes={utc_start.month:02d}&day={utc_start.day:02d}&hora={utc_start.hour:02d}&anof={utc_end.year}&mesf={utc_end.month:02d}&dayf={utc_end.day:02d}&horaf={utc_end.hour:02d}&minf=59"
        
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        
        if res.status_code == 200 and "<html" not in res.text.lower():
            lines = res.text.split("\n")
            ogimet_data = []
            for line in lines:
                if "ZSPD" not in line: continue
                t = re.search(r'(\d{2})(\d{2})(\d{2})Z', line)
                temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', line)
                if not t or not temp_match: continue

                day, hour, minute = t.groups()
                temp = int(temp_match.group(1).replace("M", "-"))
                dt = utc_to_local(day, hour, minute)

                if dt.date() == now_loc.date():
                    ogimet_data.append({
                        "metar_time": f"{day}{hour}{minute}", "time": dt.strftime("%Y-%m-%d %H:%M"),
                        "temp": temp, "raw": line.strip()
                    })

            if len(ogimet_data) > 0:
                # 合并两个源的数据并去重（最强融合技！）
                combined = ogimet_data + aviation_data
                seen = set()
                unique = []
                for d in combined:
                    if d["time"] not in seen:
                        seen.add(d["time"])
                        unique.append(d)
                return sorted(unique, key=lambda x: x["time"])
    except:
        pass

    # 🚨 终极防线：如果 Ogimet 也挂了，但 Aviation 抓到了不完整数据，直接用！绝对不扔！
    if len(aviation_data) > 0:
        st.toast("备用源失效，已启用不完整的 Aviation 历史数据进行兜底！", icon="🛡️")
        return aviation_data

    st.toast("历史数据源全面熔断，等待实时数据重建", icon="🚨")
    return []

# ======================
# 实时数据
# ======================
def get_today_data(existing_data=None): 
    if existing_data is not None:
        data = existing_data
        source = "LIVE_SYNC"
    else:
        data = load_cache()
        source = "CACHE"

    is_new = False
    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=3).text
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

# ======================
# 启动与单向数据流逻辑 (彻底修复覆写 Bug)
# ======================
initial_data = load_cache()

if initial_data:
    try:
        if datetime.strptime(initial_data[-1]["time"], "%Y-%m-%d %H:%M").date() != now_local().date():
            initial_data = []
    except:
        initial_data = []

if not initial_data or len(initial_data) <= 2:
    h_data = init_today_history()
    if h_data and len(h_data) > len(initial_data):
        initial_data = h_data
        save_cache(initial_data)

# ✅ 全局唯一一次调用，绝对不可在下方重复写！
data, is_new, source = get_today_data(existing_data=initial_data)

# === 计算核心环境变量 ===
if data and len(data) > 0:
    temp_list = [x["temp"] for x in data]
    max_temp = max(temp_list)
    max_idx = temp_list.index(max_temp)
    max_time_str = data[max_idx]["time"].split(" ")[1]
    formatted_time = data[-1]["time"]
    current = data[-1]  # 确保 current 对象正确绑定
else:
    max_temp = "--"
    max_time_str = "无"
    formatted_time = "未同步"
    current = {"temp": "--", "time": "无数据", "raw": "等待获取..."}

# ======================
# 🔊 声音系统
# ======================
if "audio_unlocked" not in st.session_state:
    st.session_state.audio_unlocked = False

if st.button("🔊 启用声音提醒"):
    st.session_state.audio_unlocked = True
    test_audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
    st.markdown(f'<audio autoplay><source src="{test_audio_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    st.success("✅ 声音提醒已解锁！")

if st.session_state.audio_unlocked and is_new:
    alert_url = f"https://actions.google.com/sounds/v1/alarms/beep_short.ogg?t={datetime.utcnow().timestamp()}"
    st.markdown(f'<audio autoplay><source src="{alert_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    st.toast("🔔 抓取到新 METAR 数据，已触发声音警报！", icon="🔊")

# ======================
# 🚨 延迟计算与防御
# ======================
delay_min = 0 
last_dt = now_local()

if data and len(data) > 0:
    try:
        last_dt = pd.to_datetime(current["time"])
        delay_min = (now_local() - last_dt).total_seconds() / 60
    except Exception as e:
        st.toast(f"时间解析异常: {e}", icon="⚠️")
else:
    st.warning("📡 正在等待数据源响应，请稍后...")

delay_info = f"**{int(delay_min)}** 分钟" 
is_delayed = delay_min > 10
