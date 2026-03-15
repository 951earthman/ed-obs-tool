import streamlit as st
import pandas as pd
import re
from datetime import datetime
import os

# ==========================================
# 系統設定與全域變數
# ==========================================
st.set_page_config(page_title="急診留觀風險評估系統", page_icon="🚨", layout="wide")
LOG_FILE = "assessment_log.csv"

# ==========================================
# 核心解析神經中樞 (強化版防呆機制，專治 HIS 缺漏字)
# ==========================================
def parse_his_vitals(raw_text):
    parsed_data = []
    for line in raw_text.strip().split('\n'):
        line = line.strip('\r')
        if not line.strip(): continue
        
        # 判斷是否為複製貼上的 Tab 格式 (HIS 系統最常見)
        has_tabs = '\t' in line
        tokens = line.split('\t') if has_tabs else line.split()
        
        # 尋找血壓欄位 (特徵：包含 '/' 且前面是數字)
        bp_idx = -1
        for i, t in enumerate(tokens):
            t_clean = t.strip()
            if '/' in t_clean and len(t_clean.split('/')) == 2 and t_clean.split('/')[0].isdigit():
                bp_idx = i
                break
                
        if bp_idx >= 2:
            try:
                sbp = int(tokens[bp_idx].strip().split('/')[0])
                hr = None
                
                # 【策略 A】精準 Tab 定位法
                if has_tabs and (bp_idx - 2) >= 0:
                    hr_str = tokens[bp_idx - 2].strip()
                    if hr_str.isdigit():
                        hr = int(hr_str)
                        
                # 【策略 B】智慧防呆抓取法 (沒 Tab 或資料壓縮時)
                if hr is None:
                    clean_tokens = line.split()
                    clean_bp_idx = -1
                    for i, t in enumerate(clean_tokens):
                        if '/' in t and len(t.split('/')) == 2 and t.split('/')[0].isdigit():
                            clean_bp_idx = i
                            break
                            
                    if clean_bp_idx >= 2:
                        sub_tokens = clean_tokens[2:clean_bp_idx]
                        ints = [int(x) for x in sub_tokens if x.isdigit()]
                        
                        if len(ints) == 1:
                            hr = ints[0]
                        elif len(ints) >= 2:
                            if ints[-1] <= 45 and ints[-2] >= 40: hr = ints[-2]
                            elif 34 <= ints[-2] <= 42 and ints[-1] > 40: hr = ints[-1]
                            else: hr = ints[-2]
                
                if hr is not None:
                    # 日期與時間處理
                    date_str = tokens[0].strip() if has_tabs else clean_tokens[0]
                    time_str = tokens[1].strip() if has_tabs else clean_tokens[1]
                    
                    if len(time_str) >= 4 and time_str[:4].isdigit():
                        time_formatted = f"{time_str[:2]}:{time_str[2:4]}"
                    else:
                        time_formatted = time_str
                        
                    if len(date_str) == 7 and date_str.startswith('1'):
                        dt_str = f"{date_str[3:5]}/{date_str[5:7]} {time_formatted}"
                    else:
                        dt_str = f"{date_str} {time_formatted}"
                        
                    parsed_data.append({
                        "時間": dt_str,
                        "心跳 (HR)": hr,
                        "收縮壓 (SBP)": sbp,
                        "休克指數 (SI)": round(hr / sbp, 2)
                    })
            except Exception as e:
                pass # 遇到無法解析的亂碼列安靜跳過
                
    return pd.DataFrame(parsed_data)

# ==========================================
# 側邊欄導覽 (Sidebar Navigation)
# ==========================================
st.sidebar.title("🏥 系統導覽")
page = st.sidebar.radio("請選擇功能模組：", [
    "📝 單次評估 (交班專用)", 
    "📈 趨勢分析 (查房專用)", 
    "🔒 管理員後台"
])
st.sidebar.divider()
st.sidebar.caption("臨床實證醫學輔助系統 v3.0")

# ==========================================
# 模組 1：單次評估與交班 (成人 MEWS / 兒科 PEWS)
# ==========================================
if page == "📝 單次評估 (交班專用)":
    st.title("🚨 急診留觀風險自動評估與交班")
    
    with st.expander("📚 點此查看系統評分標準與學理依據 (EBP)"):
        st.markdown("""
        ### 1. 成人 MEWS (Modified Early Warning Score)
        * 用於早期發現潛在病情惡化，評估項目含體溫、脈搏、呼吸、收縮壓、意識狀態 (GCS)。
        * **≥ 5 分**：高度惡化風險，需立即醫療介入 (紅區)。
        
        ### 2. 休克指數 (Shock Index, SI)
        * **公式**：心率 (HR) / 收縮壓 (SBP)。
        * **≥ 1.0**：危險值，死亡率與需急救介入機率大幅提升，列為高度風險 (紅區)。
        
        ### 3. 危險檢驗數值 (Critical Labs)
        * **Lactate ≥ 4.0**：組織嚴重缺氧，敗血性休克黃金指標 (紅區)。
        * **Hs-TnI > 17.5**：高敏感度心肌酵素異常。
        * **K (鉀離子) < 3.0 或 > 6.0**：致命性心律不整高風險。
        
        ### 4. 兒科 PEWS (Pediatric Early Warning Score)
        * 整合行為、心血管 (膚色/CRT) 與呼吸費力程度，提供非特異性之惡化早期預警。
        """)
    st.divider()

    patient_type = st.radio("👥 請選擇病患評估類別：", ["🧑 成人 (MEWS標準)", "👶 兒科 (PEWS標準)"], horizontal=True)
    
    vitals_input = st.text_area("📋 請貼上單次生命徵象 (例如：體溫：36.0 ℃；脈搏：85 次...)：", height=100)
    
    total_score = 0
    risk_level = ""
    disposition = ""
    log_score_name = ""
    
    if patient_type == "🧑 成人 (MEWS標準)":
        gcs_input = st.number_input("🧠 意識狀態 (GCS 分數, 3-15) ⚠️必填", min_value=3, max_value=15, value=None, step=1)
        log_score_name = "MEWS"
    else:
        st.info("💡 兒科病患正常心率/呼吸隨年齡差異極大，系統將優先依據下方『臨床表徵』進行 PEWS 風險計分。")
        age_group = st.selectbox("👶 選擇病童年齡區間：", ["0-3個月", "4-11個月", "1-4歲", "5-11歲", "12歲以上"])
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            pews_behavior = st.radio("1. 行為狀態 (Behavior)", ["正常玩耍/清醒 (0分)", "焦躁/安撫無效/嗜睡 (1分)", "對痛無反應/無反應 (2分)"])
        with col_p2:
            pews_cv = st.radio("2. 心血管/膚色 (CV)", ["粉紅/微血管充填 < 2秒 (0分)", "蒼白/微血管充填 2-3秒 (1分)", "發紺/大理石斑/充填 > 3秒 (2分)"])
        with col_p3:
            pews_resp = st.radio("3. 呼吸狀態 (Respiratory)", ["正常且無費力 (0分)", "呼吸急促/使用呼吸輔助肌/需給氧 (1分)", "胸凹/呻吟/SPO2<90% (2分)"])
        log_score_name = "PEWS"

    st.subheader("🧪 補充檢驗報告 (若無則留白)")
    col1, col2 = st.columns(2)
    with col1:
        k_input = st.text_input("➤ 鉀離子 (K)：")
        crp_input = st.text_input("➤ CRP：")
    with col2:
        tni_input = st.text_input("➤ Hs-TnI：")
        lactate_input = st.text_input("➤ Lactate (乳酸)：")
        st.subheader("💉 高危險連續輸液 (IV Pump)")
# 使用 st.multiselect 讓護理師可以複選多種藥物
iv_pumps = st.multiselect(
    "➤ 請問病患目前是否使用以下滴注藥物？ (可複選，若無則留白)",
    ["Levophed (Norepinephrine)", "easydopamine (Dopamine)", "Isoket (Isosorbide dinitrate)", "Perdipine (Nicardipine)", "其他降壓/強心滴注"]
)

# --- 在後方的風險判定邏輯中，加入 Pump 的影響 ---
# 判斷是否使用 A 類 (升壓) 或 B 類 (降壓)
has_vasopressor = any("Levophed" in pump or "easydopamine" in pump for pump in iv_pumps)
has_vasodilator = any("Isoket" in pump or "Perdipine" in pump for pump in iv_pumps)

# (原本的 total_score 和 lab_alert 計算維持不變)

# 風險分層邏輯更新：
if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0) or has_vasopressor:
    risk_level = "🔴 紅區 (高度風險)"
    disposition = "病患具高度惡化或休克風險 (依賴升壓劑/危險數值)，強烈建議收治 ICU 或留在急救區。"
    st.error(f"系統判定：{risk_level}")
elif total_score >= 3 or has_vasodilator:
    risk_level = "🟡 黃區 (中度風險)"
    disposition = "需密切觀察，因使用高危險輸液，建議縮短 Vital signs 監測頻率 (如 Q15m - Q1H)。"
    st.warning(f"系統判定：{risk_level}")
else:
    risk_level = "🟢 綠區 (穩定狀態)"
    disposition = "生命徵象穩定，持續常規留觀或提醒醫師評估 MBD。"
    st.success(f"系統判定：{risk_level}")

    if st.button("🚀 開始評估並生成紀錄", type="primary"):
        if vitals_input.strip() == "":
            st.error("⚠️ 請先貼上生命徵象！")
        elif patient_type == "🧑 成人 (MEWS標準)" and gcs_input is None:
            st.error("⚠️ 選擇成人評估時，請輸入 GCS 意識分數！")
        else:
            temp = hr = rr = sbp = None 
            temp_match = re.search(r'體溫：([\d.]+)', vitals_input)
            if temp_match: temp = float(temp_match.group(1))
            hr_match = re.search(r'脈搏：(\d+)', vitals_input)
            if hr_match: hr = int(hr_match.group(1))
            rr_match = re.search(r'呼吸：(\d+)', vitals_input)
            if rr_match: rr = int(rr_match.group(1))
            sbp_match = re.search(r'血壓：(\d+)/', vitals_input)
            if sbp_match: sbp = int(sbp_match.group(1))

            if patient_type == "🧑 成人 (MEWS標準)":
                if temp: total_score += (2 if temp < 35 or temp >= 38.5 else 1 if temp < 36 else 0)
                if hr: total_score += (3 if hr <= 40 or hr >= 130 else 2 if 111 <= hr <= 129 else 1 if 41 <= hr <= 50 or 101 <= hr <= 110 else 0)
                if rr: total_score += (3 if rr >= 30 else 2 if rr <= 8 or 21 <= rr <= 29 else 1 if 15 <= rr <= 20 else 0)
                if sbp: total_score += (3 if sbp <= 70 else 2 if sbp <= 80 or sbp >= 200 else 1 if sbp <= 100 else 0)
                gcs_score = 0
                if gcs_input == 15: gcs_score = 0
                elif 13 <= gcs_input <= 14: gcs_score = 1
                elif 9 <= gcs_input <= 12: gcs_score = 2
                elif gcs_input <= 8: gcs_score = 3
                total_score += gcs_score
                score_display = f"MEWS 總分 {total_score} 分 (GCS {gcs_input})"
            else:
                b_score = int(re.search(r'\((\d)分\)', pews_behavior).group(1))
                c_score = int(re.search(r'\((\d)分\)', pews_cv).group(1))
                r_score = int(re.search(r'\((\d)分\)', pews_resp).group(1))
                total_score = b_score + c_score + r_score
                score_display = f"PEWS 總分 {total_score} 分 (年齡: {age_group})"

            shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

            lab_alert = False
            lab_records_list = []
            if k_input.strip() != "":
                k_val = float(k_input)
                if k_val < 3.0 or k_val > 6.0: lab_alert = True
                lab_records_list.append(f"K {k_val}")
            if tni_input.strip() != "":
                tni_val = float(tni_input)
                if tni_val > 17.5: lab_alert = True
                lab_records_list.append(f"Hs-TnI {tni_val}")
            if crp_input.strip() != "": lab_records_list.append(f"CRP {crp_input}")
            if lactate_input.strip() != "":
                lac_val = float(lactate_input)
                if lac_val >= 4.0: lab_alert = True 
                lab_records_list.append(f"Lac {lac_val}")
            lab_record_text = " / ".join(lab_records_list) if lab_records_list else "無異常或未驗"

            if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0):
                risk_level = "🔴 紅區 (高度風險)"
                disposition = "立即通知醫師評估處置，強烈建議收治或轉急救區。"
                st.error(f"系統判定：{risk_level}")
            elif total_score >= 3:
                risk_level = "🟡 黃區 (中度風險)"
                disposition = "需密切觀察，增加 Vital signs 監測頻率。"
                st.warning(f"系統判定：{risk_level}")
            else:
                risk_level = "🟢 綠區 (穩定狀態)"
                disposition = "生命徵象穩定，持續常規留觀或提醒醫師評估 MBD。"
                st.success(f"系統判定：{risk_level}")

            st.subheader("📋 護理交班紀錄")
            nursing_note = f"""[留觀風險自動評估紀錄]
1. 評估對象：{patient_type}
2. 當下生理數值：體溫 {temp}℃, 脈搏 {hr}次/分, 呼吸 {rr}次/分, 血壓 {sbp}mmHg
3. 預警指標運算：{score_display} / 休克指數 (SI) {shock_index}
4. 關鍵檢驗數值：{lab_record_text}
5. 系統判定風險：{risk_level}
6. 建議動向處置：{disposition}"""
            st.code(nursing_note, language="text")

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_record = {
                "評估時間": current_time,
                "類別": log_score_name,
                "分數": total_score,
                "休克指數": shock_index,
                "檢驗項目": lab_record_text,
                "系統判定": risk_level
            }
            df_new = pd.DataFrame([new_record])
            if not os.path.exists(LOG_FILE):
                df_new.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
            else:
                df_new.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

# ==========================================
# 模組 2：生命徵象趨勢 (HIS 批次解析)
# ==========================================
elif page == "📈 趨勢分析 (查房專用)":
    st.title("📈 留觀生命徵象趨勢分析")
    st.markdown("將資訊系統 (HIS) 內的歷史生理數值批次貼上，系統將自動解析並繪製趨勢圖與顏色分級表。")
    
    batch_vitals = st.text_area("📋 請貼上 HIS 系統的多筆生命徵象表格 (直接複製貼上即可)：", height=200, 
                                placeholder="範例：\n1150315 1400 96 20 171/91\n1150315 1430 35.9 ▽ 100 20 161/85...")

    if st.button("📊 解析與繪製趨勢", type="primary"):
        if batch_vitals.strip() != "":
            # 呼叫我們頂部的神經中樞函數
            df = parse_his_vitals(batch_vitals)
            
            if not df.empty:
                st.success(f"✅ 成功解析 {len(df)} 筆生命徵象紀錄！")
                
                tab1, tab2, tab3 = st.tabs(["🗂️ 解析後數據表 (自動上色)", "📉 休克指數趨勢圖", "💓 血液動力學交叉圖"])
                
                with tab1:
                    st.markdown("#### 依休克指數 (SI) 風險自動分色")
                    st.caption("🔴 紅區: SI ≥ 1.0 ｜ 🟡 黃區: SI 0.8~0.99 ｜ 🟢 綠區: SI < 0.8")
                    
                    def highlight_risk(row):
                        si = row['休克指數 (SI)']
                        if pd.isna(si): bg_color = ''
                        elif si >= 1.0: bg_color = 'background-color: #ffcccc; color: #900000; font-weight: bold;'
                        elif si >= 0.8: bg_color = 'background-color: #fff2cc; color: #8a6d3b;'
                        else: bg_color = 'background-color: #e6ffe6; color: #2b542c;'
                        return [bg_color] * len(row)

                    styled_df = df.style.apply(highlight_risk, axis=1)
                    st.dataframe(styled_df, use_container_width=True)
                    
                with tab2:
                    st.markdown("#### ⚠️ 休克指數 (SI) 趨勢變化")
                    st.line_chart(df.set_index("時間")[["休克指數 (SI)"]], color="#FF4B4B")
                    
                with tab3:
                    st.markdown("#### 💓 心跳 vs. 收縮壓")
                    st.caption("注意：當心跳線條向上交叉穿越收縮壓線條時，即代表 SI > 1.0，進入隱性休克危險期。")
                    st.line_chart(df.set_index("時間")[["心跳 (HR)", "收縮壓 (SBP)"]])
            else:
                st.error("❌ 無法解析資料，請確認貼上的格式是否正確。")

# ==========================================
# 模組 3：管理員後台
# ==========================================
elif page == "🔒 管理員後台":
    st.title("🔒 系統品管與稽核後台")
    st.info("此區域僅供專案管理員與護理長進行資料稽核與品質管理 (QA/QC) 使用。")
    
    admin_password = st.text_input("🔑 請輸入管理員密碼", type="password")
    
    if admin_password == "alex":
        st.success("✅ 登入成功")
        
        if os.path.exists(LOG_FILE):
            df_log = pd.read_csv(LOG_FILE)
            st.markdown(f"### 🗂️ 系統使用紀錄 (共 {len(df_log)} 筆)")
            st.dataframe(df_log, use_container_width=True)
            
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                csv = df_log.to_csv(index=False, encoding='utf-8-sig')
                st.download_button("📥 下載完整紀錄 (CSV)", data=csv, file_name="ed_obs_log.csv", mime="text/csv")
            with col_a2:
                if st.button("🗑️ 清空所有紀錄", type="primary"):
                    os.remove(LOG_FILE)
                    st.rerun() 
        else:
            st.info("目前尚無任何評估紀錄。")
    elif admin_password != "":
        st.error("❌ 密碼錯誤")

# ==========================================
# 全域頁尾：版權與免責聲明 (專屬客製化版)
# ==========================================
st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown("""
<div style="text-align: center; color: gray; font-size: 0.85em;">
    <p><strong>© 2026 急診留觀風險自動評估系統</strong> | 臨床決策輔助工具</p>
    <p>💡 <b>System Design & Clinical Logic by：</b>花蓮慈濟醫學中心 急診護理師 [吳智弘] (D-MAT / BLS Instructor)</p>
    <p>⚠️ <b>免責聲明：</b>本系統基於臨床實證醫學 (EBP) 開發，主要作為急診護理人員之交班與風險分層輔助，評估結果不可替代臨床醫師之專業診斷。</p>
    <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">
        <img alt="創用 CC 授權條款" style="border-width:0; margin-bottom: 5px;" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" />
    </a>
    <br />本專案採用<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" style="color: gray; text-decoration: underline;">創用 CC 姓名標示-非商業性-相同方式分享 4.0 國際 授權條款</a>授權。
</div>
""", unsafe_allow_html=True)
