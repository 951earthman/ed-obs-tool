import streamlit as st
import pandas as pd
import re
from datetime import datetime
import os

# ==========================================
# 系統設定與全域變數
# ==========================================
st.set_page_config(page_title="急診臨床決策輔助系統", page_icon="🚨", layout="wide")
LOG_FILE = "assessment_log.csv"

# ==========================================
# 核心解析神經中樞 (強化版防呆機制)
# ==========================================
def parse_his_vitals(raw_text):
    parsed_data = []
    for line in raw_text.strip().split('\n'):
        line = line.strip('\r')
        if not line.strip(): continue
        has_tabs = '\t' in line
        tokens = line.split('\t') if has_tabs else line.split()
        bp_idx = -1
        for i, t in enumerate(tokens):
            t_clean = t.strip()
            if '/' in t_clean and len(t_clean.split('/')) == 2 and t_clean.split('/')[0].isdigit():
                bp_idx = i; break
        if bp_idx >= 2:
            try:
                sbp = int(tokens[bp_idx].strip().split('/')[0])
                hr = None
                if has_tabs and (bp_idx - 2) >= 0:
                    hr_str = tokens[bp_idx - 2].strip()
                    if hr_str.isdigit(): hr = int(hr_str)
                if hr is None:
                    clean_tokens = line.split()
                    clean_bp_idx = -1
                    for i, t in enumerate(clean_tokens):
                        if '/' in t and len(t.split('/')) == 2 and t.split('/')[0].isdigit():
                            clean_bp_idx = i; break
                    if clean_bp_idx >= 2:
                        sub_tokens = clean_tokens[2:clean_bp_idx]
                        ints = [int(x) for x in sub_tokens if x.isdigit()]
                        if len(ints) == 1: hr = ints[0]
                        elif len(ints) >= 2:
                            if ints[-1] <= 45 and ints[-2] >= 40: hr = ints[-2]
                            elif 34 <= ints[-2] <= 42 and ints[-1] > 40: hr = ints[-1]
                            else: hr = ints[-2]
                if hr is not None:
                    date_str = tokens[0].strip() if has_tabs else clean_tokens[0]
                    time_str = tokens[1].strip() if has_tabs else clean_tokens[1]
                    if len(time_str) >= 4 and time_str[:4].isdigit(): time_formatted = f"{time_str[:2]}:{time_str[2:4]}"
                    else: time_formatted = time_str
                    if len(date_str) == 7 and date_str.startswith('1'): dt_str = f"{date_str[3:5]}/{date_str[5:7]} {time_formatted}"
                    else: dt_str = f"{date_str} {time_formatted}"
                    parsed_data.append({"時間": dt_str, "心跳 (HR)": hr, "收縮壓 (SBP)": sbp, "休克指數 (SI)": round(hr / sbp, 2)})
            except Exception as e:
                pass 
    return pd.DataFrame(parsed_data)

# ==========================================
# 側邊欄 (Sidebar)：導覽、學理搜尋、管理員
# ==========================================
st.sidebar.title("🏥 急診臨床決策輔助系統")
page = st.sidebar.radio("請選擇功能模組：", [
    "📝 留觀風險評估 (交班)", 
    "📈 生命徵象趨勢 (查房)",
    "🩸 ABG 血液氣體判讀",
    "💉 血液檢驗報告 (CBC+BCS)"  # <-- 合併後的新分頁
])

st.sidebar.divider()

# --- 學理依據 (EBP) 搜尋系統 ---
st.sidebar.subheader("📚 臨床學理檢索 (EBP)")
search_query = st.sidebar.text_input("🔍 關鍵字 (如: AKI, 貧血,休克)", placeholder="搜尋學理依據...")

ebp_dict = {
    "預警分數 (MEWS/PEWS) 與 休克指數 (SI)": "MEWS ≥ 5 分 或 SI ≥ 1.0 代表高度休克與惡化風險，列為紅區。PEWS 整合兒童行為、膚色與呼吸費力程度提供早期預警。",
    "高危輸液 (IV Pump) 與 假性穩定": "依賴升壓劑 (Levophed, Dopamine) 維持血壓即代表重度心血管衰竭，無視當下血壓直接列為紅區。降壓劑則列黃區監測。",
    "潛在不穩定主訴 (高危險特徵)": "癲癇 (Seizure)、消化道出血 (GI Bleeding)、不明原因暈厥等，極易發生突發性呼吸道阻塞或休克，強制歸類為黃區監測。",
    "危險檢驗值 (Lactate / CRP / K)": "Lactate ≥ 4.0 提示嚴重組織缺氧 (敗血症黃金指標)；CRP ≥ 10.0 提示嚴重感染；K < 3.0 或 > 6.0 易引發致命性心律不整。",
    "ANC 免疫低下與貧血判讀 (CBC)": "ANC < 500 為重度低下 (極高感染風險)。MCV < 80 為小球性貧血 (缺鐵/地中海)；80-100 為正球性 (急性出血/慢性病)；> 100 為大球性 (B12缺乏/肝病)。",
    "腎臟功能與 BUN/CRE 比例": "BUN/CRE > 20 提示腎前性氮血症 (Prerenal Azotemia)，急診常見於嚴重脫水或急性腸胃道出血 (UGIB)。",
    "KDIGO 慢性腎臟病 (CKD) 分級": "Stage 1 (≥90), Stage 2 (60-89), Stage 3a (45-59), Stage 3b (30-44), Stage 4 (15-29), Stage 5 (<15 末期腎臟病)。",
    "肝功能與猛爆性肝損傷 (AST/ALT)": "AST/ALT > 100 提示實質性肝炎；若 > 1000 則強烈提示猛爆性肝炎或缺血性肝炎 (Shock Liver)。"
}

# 根據搜尋字串顯示對應的學理
for title, content in ebp_dict.items():
    if search_query == "" or search_query.lower() in title.lower() or search_query.lower() in content.lower():
        with st.sidebar.expander(title, expanded=(search_query != "")):
            st.write(content)

st.sidebar.divider()

# --- 隱藏在左下方的管理員系統 ---
st.sidebar.subheader("🔒 管理員後台")
admin_password = st.sidebar.text_input("輸入密碼解鎖後台", type="password")
if admin_password == "alex":
    st.sidebar.success("✅ 身分驗證成功")
    if os.path.exists(LOG_FILE):
        df_log = pd.read_csv(LOG_FILE)
        st.sidebar.caption(f"目前累積 {len(df_log)} 筆紀錄")
        st.sidebar.download_button("📥 下載完整紀錄 (CSV)", data=df_log.to_csv(index=False, encoding='utf-8-sig'), file_name="ed_obs_log.csv", mime="text/csv", use_container_width=True)
        if st.sidebar.button("🗑️ 清空所有紀錄", use_container_width=True):
            os.remove(LOG_FILE)
            st.rerun()
    else:
        st.sidebar.info("尚無任何評估紀錄。")
elif admin_password != "":
    st.sidebar.error("❌ 密碼錯誤")

# ==========================================
# 模組 1：留觀單次評估與交班
# ==========================================
if page == "📝 留觀風險評估 (交班)":
    st.title("🚨 急診留觀風險自動評估與交班")
    patient_type = st.radio("👥 請選擇病患評估類別：", ["🧑 成人 (MEWS標準)", "👶 兒科 (PEWS標準)"], horizontal=True)
    vitals_input = st.text_area("📋 1. 請貼上單次生命徵象 (例如：體溫：36.0 ℃；脈搏：85 次...)：", height=100)
    
    total_score = 0
    if patient_type == "🧑 成人 (MEWS標準)":
        gcs_input = st.number_input("🧠 意識狀態 (GCS 分數, 3-15) ⚠️必填", min_value=3, max_value=15, value=None, step=1)
        log_score_name = "MEWS"
    else:
        st.info("💡 兒科病患優先依據下方『臨床表徵』進行 PEWS 風險計分。")
        age_group = st.selectbox("👶 選擇病童年齡區間：", ["0-3個月", "4-11個月", "1-4歲", "5-11歲", "12歲以上"])
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1: pews_behavior = st.radio("行為狀態", ["正常(0分)", "焦躁/嗜睡(1分)", "對痛無反應(2分)"])
        with col_p2: pews_cv = st.radio("心血管/膚色", ["粉紅/充填<2秒(0分)", "蒼白/充填2-3秒(1分)", "發紺/大理石斑/充填>3秒(2分)"])
        with col_p3: pews_resp = st.radio("呼吸狀態", ["正常且無費力(0分)", "呼吸急促/需給氧(1分)", "胸凹/呻吟/SPO2<90%(2分)"])
        log_score_name = "PEWS"

    st.subheader("💉 2. 高危險連續輸液 (IV Pump)")
    iv_pumps = st.multiselect("➤ 病患是否使用以下滴注藥物？", ["Levophed", "easydopamine", "Isoket", "Perdipine", "其他降壓或強心"])

    st.subheader("⚠️ 3. 潛在不穩定主訴與病史")
    high_risk_cc = st.multiselect("➤ 是否有易發生「突發惡化」狀況？", 
                                  ["🧠 癲癇/TIA", "🫀 暈厥/胸痛", "🩸 疑似 GI Bleeding", "🫁 嚴重氣喘/COPD", "☠️ 嚴重低血糖/酒精戒斷"])

    st.subheader("🧪 4. 補充檢驗報告 (可搭配左側抽血報告模組使用)")
    col1, col2 = st.columns(2)
    with col1: k_input, crp_input = st.text_input("➤ K："), st.text_input("➤ CRP：")
    with col2: tni_input, lactate_input = st.text_input("➤ Hs-TnI："), st.text_input("➤ Lactate：")

    if st.button("🚀 開始評估並生成紀錄", type="primary"):
        if vitals_input.strip() == "": st.error("⚠️ 請先貼上生命徵象！")
        elif patient_type == "🧑 成人 (MEWS標準)" and gcs_input is None: st.error("⚠️ 請輸入 GCS 意識分數！")
        else:
            temp = hr = rr = sbp = None 
            if re.search(r'體溫：([\d.]+)', vitals_input): temp = float(re.search(r'體溫：([\d.]+)', vitals_input).group(1))
            if re.search(r'脈搏：(\d+)', vitals_input): hr = int(re.search(r'脈搏：(\d+)', vitals_input).group(1))
            if re.search(r'呼吸：(\d+)', vitals_input): rr = int(re.search(r'呼吸：(\d+)', vitals_input).group(1))
            if re.search(r'血壓：(\d+)/', vitals_input): sbp = int(re.search(r'血壓：(\d+)/', vitals_input).group(1))

            if patient_type == "🧑 成人 (MEWS標準)":
                if temp: total_score += (2 if temp < 35 or temp >= 38.5 else 1 if temp < 36 else 0)
                if hr: total_score += (3 if hr <= 40 or hr >= 130 else 2 if 111 <= hr <= 129 else 1 if 41 <= hr <= 50 or 101 <= hr <= 110 else 0)
                if rr: total_score += (3 if rr >= 30 else 2 if rr <= 8 or 21 <= rr <= 29 else 1 if 15 <= rr <= 20 else 0)
                if sbp: total_score += (3 if sbp <= 70 else 2 if sbp <= 80 or sbp >= 200 else 1 if sbp <= 100 else 0)
                gcs_score = 0 if gcs_input == 15 else 1 if 13 <= gcs_input <= 14 else 2 if 9 <= gcs_input <= 12 else 3
                total_score += gcs_score
                score_display = f"MEWS {total_score}分 (GCS {gcs_input})"
            else:
                total_score = int(pews_behavior[-2]) + int(pews_cv[-2]) + int(pews_resp[-2])
                score_display = f"PEWS {total_score}分"

            shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

            lab_alert = False
            lab_records_list = []
            if k_input.strip() and (float(k_input) < 3.0 or float(k_input) > 6.0): lab_alert = True; lab_records_list.append(f"K {k_input}")
            elif k_input.strip(): lab_records_list.append(f"K {k_input}")
            if tni_input.strip() and float(tni_input) > 17.5: lab_alert = True; lab_records_list.append(f"TnI {tni_input}")
            elif tni_input.strip(): lab_records_list.append(f"TnI {tni_input}")
            if crp_input.strip() and float(crp_input) >= 10.0: lab_alert = True; lab_records_list.append(f"CRP {crp_input}(≥10)")
            elif crp_input.strip(): lab_records_list.append(f"CRP {crp_input}")
            if lactate_input.strip() and float(lactate_input) >= 4.0: lab_alert = True; lab_records_list.append(f"Lac {lactate_input}(≥4)")
            elif lactate_input.strip(): lab_records_list.append(f"Lac {lactate_input}")
            lab_record_text = " / ".join(lab_records_list) if lab_records_list else "無異常"

            has_vasopressor = any("Levophed" in p or "easydopamine" in p for p in iv_pumps)
            has_vasodilator = any("Isoket" in p or "Perdipine" in p for p in iv_pumps)
            pump_record_text = " / ".join(iv_pumps) if iv_pumps else "無"
            
            has_high_risk_cc = len(high_risk_cc) > 0
            cc_record_text = " / ".join(high_risk_cc) if has_high_risk_cc else "無"

            if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0) or has_vasopressor:
                risk_level, disposition = "🔴 紅區", "具高度惡化或休克風險，建議收治或轉急救區。"
                st.error(f"判定：{risk_level}")
            elif total_score >= 3 or has_vasodilator or has_high_risk_cc:
                risk_level, disposition = "🟡 黃區", "潛在突發惡化風險，請落實防跌、密切監測意識/出血，縮短 Vital signs 頻率。"
                st.warning(f"判定：{risk_level}")
            else:
                risk_level, disposition = "🟢 綠區", "生命徵象穩定，持續常規留觀。"
                st.success(f"判定：{risk_level}")

            st.code(f"""[留觀風險自動評估紀錄]
1. 對象：{patient_type}
2. 生理：體溫 {temp}℃, 脈搏 {hr}次/分, 呼吸 {rr}次/分, 血壓 {sbp}mmHg
3. 預警：{score_display} / SI {shock_index}
4. 輸液/風險：{pump_record_text} / {cc_record_text}
5. 檢驗：{lab_record_text}
6. 判定/處置：{risk_level} - {disposition}""", language="text")

            new_record = pd.DataFrame([{
                "評估時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "類別": log_score_name, "分數": total_score, "休克指數": shock_index,
                "高危主訴": "有" if has_high_risk_cc else "無", "檢驗項目": lab_record_text, "系統判定": risk_level
            }])
            if not os.path.exists(LOG_FILE): new_record.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
            else: new_record.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

# ==========================================
# 模組 2：生命徵象趨勢 (查房)
# ==========================================
elif page == "📈 生命徵象趨勢 (查房)":
    st.title("📈 留觀生命徵象趨勢分析")
    batch_vitals = st.text_area("📋 請貼上 HIS 系統的多筆生命徵象表格：", height=200)
    if st.button("📊 解析與繪製趨勢", type="primary") and batch_vitals.strip() != "":
        df = parse_his_vitals(batch_vitals)
        if not df.empty:
            tab1, tab2, tab3 = st.tabs(["🗂️ 數據表", "📉 SI 趨勢", "💓 血流動力交叉圖"])
            with tab1:
                def highlight_risk(row):
                    si = row['休克指數 (SI)']
                    if pd.isna(si): return [''] * len(row)
                    elif si >= 1.0: return ['background-color: #ffcccc; color: #900000;'] * len(row)
                    elif si >= 0.8: return ['background-color: #fff2cc; color: #8a6d3b;'] * len(row)
                    else: return ['background-color: #e6ffe6; color: #2b542c;'] * len(row)
                st.dataframe(df.style.apply(highlight_risk, axis=1), use_container_width=True)
            with tab2: st.line_chart(df.set_index("時間")[["休克指數 (SI)"]], color="#FF4B4B")
            with tab3: st.line_chart(df.set_index("時間")[["心跳 (HR)", "收縮壓 (SBP)"]])

# ==========================================
# 模組 3：ABG 血液氣體判讀
# ==========================================
elif page == "🩸 ABG 血液氣體判讀":
    st.title("🩸 動脈血液氣體分析 (ABG) 快速判讀")
    abg_input = st.text_area("📋 請貼上 HIS 系統的 Blood Gas 報告：", height=200)
    if st.button("🔬 解析 ABG 報告", type="primary") and abg_input.strip() != "":
        ph = float(re.search(r'pH\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'pH\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        pco2 = float(re.search(r'pCO2\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'pCO2\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        hco3 = float(re.search(r'HCO3\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'HCO3\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        po2 = float(re.search(r'pO2\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'pO2\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        if ph and pco2 and hco3:
            ph_status = "正常" if 7.35 <= ph <= 7.45 else "酸血症" if ph < 7.35 else "鹼血症"
            primary, comp = "", ""
            if ph < 7.35:
                if pco2 > 45 and hco3 < 22: primary = "混合性酸中毒"
                elif pco2 > 45: primary, comp = "呼吸性酸中毒", "伴隨代償" if hco3 > 26 else "(未代償)"
                elif hco3 < 22: primary, comp = "代謝性酸中毒", "伴隨代償" if pco2 < 35 else "(未代償)"
            elif ph > 7.45:
                if pco2 < 35 and hco3 > 26: primary = "混合性鹼中毒"
                elif pco2 < 35: primary, comp = "呼吸性鹼中毒", "伴隨代償" if hco3 < 22 else "(未代償)"
                elif hco3 > 26: primary, comp = "代謝性鹼中毒", "伴隨代償" if pco2 > 45 else "(未代償)"
            else: primary = "正常或完全代償"
            oxy = "正常" if po2 and po2 >= 80 else "低血氧" if po2 else "未提供"
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("pH", ph, ph_status, delta_color="inverse")
            col2.metric("pCO2", pco2, "異常" if pco2<35 or pco2>45 else "正常", delta_color="inverse")
            col3.metric("HCO3", hco3, "異常" if hco3<22 or hco3>26 else "正常", delta_color="inverse")
            if po2: col4.metric("pO2", po2, oxy, delta_color="inverse")
            st.code(f"[ABG 判讀]\npH {ph} / pCO2 {pco2} / HCO3 {hco3} / pO2 {po2}\n判讀: {primary} {comp} ({oxy})", language="text")

# ==========================================
# 模組 4：綜合抽血報告 (CBC + BCS)
# ==========================================
elif page == "💉 血液檢驗報告 (CBC+BCS)":
    st.title("💉 綜合抽血報告快速判讀 (CBC + BCS)")
    st.markdown("請將 HIS 系統內的**血液常規 (CBC)** 與 **生化檢驗 (BCS)** 一併複製貼上，系統將自動分類、抓取並執行交叉比對分析。")
    
    blood_input = st.text_area("📋 請貼上抽血報告 (可直接 Ctrl+A 全選貼上)：", height=250, placeholder="WBC 4.14...\nNa 137...\nBUN 40...")
    
    if st.button("🔬 綜合解析報告", type="primary"):
        if blood_input.strip() == "":
            st.error("⚠️ 請先貼上抽血報告！")
        else:
            # --- 1. CBC 變數抓取 ---
            wbc = float(re.search(r'WBC\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'WBC\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            hb = float(re.search(r'Hb\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'Hb\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            mcv = float(re.search(r'MCV\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'MCV\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            n_band = float(re.search(r'N\.?band\.?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'N\.?band\.?\s+([\d.]+)', blood_input, re.IGNORECASE) else 0.0
            n_seg = float(re.search(r'N\.?seg\.?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'N\.?seg\.?\s+([\d.]+)', blood_input, re.IGNORECASE) else 0.0
            
            # --- 2. BCS 變數抓取 ---
            na = float(re.search(r'Na\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'Na\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            k = float(re.search(r'K\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'K\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            glu = float(re.search(r'GLU\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'GLU\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            bun = float(re.search(r'BUN\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'BUN\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            
            cre_matches = re.findall(r'CRE\s+([\d.]+)', blood_input, re.IGNORECASE)
            cre = float(cre_matches[0]) if cre_matches else None
            
            egfr = float(re.search(r'eGFR[^\n\d]*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'eGFR[^\n\d]*([\d.]+)', blood_input, re.IGNORECASE) else None
            ast = float(re.search(r'AST\s*\(?GOT\)?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'AST\s*\(?GOT\)?\s+([\d.]+)', blood_input, re.IGNORECASE) else None
            alt = float(re.search(r'ALT\s*\(?GPT\)?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'ALT\s*\(?GPT\)?\s+([\d.]+)', blood_input, re.IGNORECASE) else None

            # --- 3. 邏輯判讀 ---
            anc_status = "未提供 WBC 資料"
            anc = None
            if wbc:
                anc = round(wbc * 1000 * ((n_band + n_seg) / 100), 1)
                anc_status = "🔴 重度低下 (<500)" if anc < 500 else "🟡 中度低下 (<1000)" if anc < 1000 else "🟡 輕度低下 (<1500)" if anc < 1500 else "🟢 正常"
            
            anemia_status = "無明顯貧血"
            if hb and hb < 12.0:
                if mcv: anemia_status = f"🟡 小球性貧血 (MCV={mcv})" if mcv < 80 else f"🟡 大球性貧血 (MCV={mcv})" if mcv > 100 else f"🟡 正球性貧血 (MCV={mcv})"
                else: anemia_status = "🟡 貧血"

            na_status = "正常" if na and 135 <= na <= 145 else "異常" if na else "未提供"
            k_status = "🚨 危急值" if k and (k < 3.0 or k > 6.0) else "異常" if k and (k < 3.5 or k > 5.1) else "正常" if k else "未提供"
            
            bc_ratio = round(bun / cre, 1) if bun and cre else None
            renal_status = "正常"
            if bc_ratio and bc_ratio > 20: renal_status = f"🔴 腎前性氮血症 (Ratio={bc_ratio} > 20)，強烈提示脫水或 GI Bleeding"
            elif cre and cre > 1.3: renal_status = "🟡 腎功能損傷"
            
            ckd_status = "未提供"
            if egfr:
                ckd_status = "Stage 1 (≥90)" if egfr >= 90 else "Stage 2 (60-89)" if egfr >= 60 else "Stage 3a (45-59)" if egfr >= 45 else "Stage 3b (30-44)" if egfr >= 30 else "Stage 4 (15-29)" if egfr >= 15 else "Stage 5 (<15)"

            liver_status = "正常"
            if ast and alt:
                liver_status = "🚨 猛爆性/缺血性肝損傷 (>1000)" if ast > 1000 or alt > 1000 else "🟡 肝炎 / 肝異常" if ast > 100 or alt > 100 else "正常"

            # --- 4. 畫面呈現 ---
            st.markdown("### 🧫 血液常規 (CBC & DC)")
            c1, c2, c3, c4 = st.columns(4)
            if wbc: c1.metric("WBC", wbc)
            if wbc: c2.metric("ANC 絕對嗜中性球", anc, anc_status.split(" ")[1] if anc < 1500 else "正常", delta_color="inverse" if anc < 1500 else "normal")
            if hb: c3.metric("Hb (血紅素)", hb, anemia_status.split(" ")[1] if hb < 12.0 else "正常", delta_color="inverse" if hb < 12.0 else "normal")
            if mcv: c4.metric("MCV", mcv)

            st.markdown("### 🧪 生化指標 (BCS)")
            b1, b2, b3, b4 = st.columns(4)
            if na: b1.metric("Na", na, na_status, delta_color="inverse" if na_status != "正常" else "normal")
            if k: b2.metric("K", k, k_status, delta_color="inverse" if k_status != "正常" else "normal")
            if cre: b3.metric("CRE", cre, "異常" if cre>1.3 else "正常", delta_color="inverse" if cre>1.3 else "normal")
            if egfr: b4.metric("eGFR", egfr, ckd_status.split(" ")[0], delta_color="inverse" if egfr<60 else "normal")
            
            if bc_ratio and bc_ratio > 20: st.error(f"**💧 體液與腎臟：** {renal_status}")
            elif bun and cre: st.info(f"**💧 體液與腎臟：** BUN/CRE Ratio {bc_ratio}")
            
            if ast and (ast > 100 or alt > 100): st.warning(f"**🩸 肝臟功能：** {liver_status}")
            
            st.subheader("📋 護理交班紀錄")
            st.code(f"""[綜合抽血檢驗判讀]
1. 免疫狀態：WBC {wbc} / ANC {anc} ({anc_status.split(' ')[0]})
2. 貧血狀態：Hb {hb} / MCV {mcv} ({anemia_status})
3. 腎臟體液：BUN {bun} / CRE {cre} (Ratio: {bc_ratio}) / eGFR {egfr} ({ckd_status.split(' ')[0]})
4. 肝臟酵素：AST {ast} / ALT {alt} ({liver_status.split(' ')[0]})
5. 電解質與血糖：Na {na} / K {k} / GLU {glu}""", language="text")

# ==========================================
# 全域頁尾
# ==========================================
st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown("""
<div style="text-align: center; color: gray; font-size: 0.85em;">
    <p><strong>© 2026 急診臨床決策輔助系統 (ER Clinical Decision Support)</strong></p>
    <p>💡 <b>System Design & Clinical Logic by：</b>花蓮慈濟醫學中心 急診護理師 [吳智弘] (D-MAT / BLS Instructor)</p>
    <p>⚠️ <b>免責聲明：</b>本系統基於臨床實證醫學 (EBP) 開發，不可替代臨床醫師之專業診斷。</p>
</div>
""", unsafe_allow_html=True)
