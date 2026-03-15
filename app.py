import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re
st.subheader("1. 臨床徵象與病患類別")

# 新增一個並排的切換按鈕
patient_type = st.radio("👥 請選擇病患評估類別：", ["🧑 成人 (MEWS)", "👶 兒科 (PEWS)"], horizontal=True)

if patient_type == "🧑 成人 (MEWS)":
    st.info("目前使用：成人 MEWS 評分標準")
    vitals_input = st.text_area("📋 請貼上生命徵象...")
    gcs_input = st.number_input("🧠 意識狀態 (GCS)...")
    # (執行原本成人的判斷邏輯)

elif patient_type == "👶 兒科 (PEWS)":
    st.info("目前使用：兒科 PEWS 評分標準")
    
    # 兒科需要先選年齡，因為 Vital signs 標準不同
    age_group = st.selectbox("請選擇病童年齡：", ["嬰兒 (< 1歲)", "幼兒 (1-3歲)", "學齡前 (4-11歲)", "青少年 (≥ 12歲)"])
    
    # 兒科特有的評估項目
    behavior = st.radio("行為狀態 (Behavior)：", ["正常玩耍/清醒 (0分)", "焦躁/安撫無效/嗜睡 (1分)", "對痛無反應 (2分)"])
    crt = st.radio("微血管充填時間 (CRT)：", ["< 2秒 (0分)", "2-3秒 (1分)", "> 3秒 (2分)"])
    
    vitals_input = st.text_area("📋 請貼上生命徵象 (將依據所選年齡判斷)...")
    # (執行兒科的判斷邏輯)

# --- 設定資料紀錄檔案名稱 ---
LOG_FILE = "assessment_log.csv"

# --- 側邊欄：管理員專區 ---
st.sidebar.title("🔒 管理員專區")
admin_password = st.sidebar.text_input("請輸入管理員密碼", type="password")

if admin_password == "alex":
    st.sidebar.success("✅ 登入成功")
    st.sidebar.markdown("### 🗂️ 系統使用紀錄")
    
    # 讀取並顯示紀錄檔
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        st.sidebar.dataframe(df) # 在側邊欄顯示表格
        
        # 提供下載按鈕
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.sidebar.download_button(
            label="📥 下載完整紀錄 (CSV)",
            data=csv,
            file_name="ed_obs_log.csv",
            mime="text/csv"
        )
        
        # 提供清空紀錄按鈕
        if st.sidebar.button("🗑️ 清空所有紀錄"):
            os.remove(LOG_FILE)
            st.sidebar.warning("紀錄已清空，請重新整理網頁。")
    else:
        st.sidebar.info("目前尚無任何評估紀錄。")
elif admin_password != "":
    st.sidebar.error("❌ 密碼錯誤")


# --- 網頁主畫面 (給一般使用者) ---
st.title("🚨 急診留觀風險自動評估系統")
st.markdown("快速計算 MEWS、休克指數，並整合危險檢驗值 (K, Hs-TnI, CRP, Lactate)。")
st.divider() 

st.subheader("1. 臨床徵象與意識評估")
vitals_input = st.text_area("📋 請貼上生命徵象 (例如：體溫：36.0 ℃；脈搏：85 次...)", height=100)
gcs_input = st.number_input("🧠 意識狀態 (GCS 分數, 3-15) ⚠️必填", min_value=3, max_value=15, value=None, step=1)

st.subheader("2. 補充檢驗報告 (若無則留白)")
col1, col2 = st.columns(2)
with col1:
    k_input = st.text_input("➤ 鉀離子 (K) 數值：")
    crp_input = st.text_input("➤ CRP (發炎指標)：")
with col2:
    tni_input = st.text_input("➤ Hs-TnI 數值：")
    lactate_input = st.text_input("➤ Lactate (乳酸) 數值：")
import streamlit as st
import pandas as pd
import re

# --- 隱藏在背後的解析神經中樞 ---
def parse_his_vitals(raw_text):
    parsed_data = []
    # 將貼上的文字一行一行切開
    for line in raw_text.strip().split('\n'):
        tokens = line.split() # 將每一行用空白或 Tab 切成一個個單字
        if not tokens: continue
        
        # 尋找血壓的位置 (特徵：字串裡面有 '/' 且前後是數字)
        bp_idx = -1
        for i, t in enumerate(tokens):
            if '/' in t and len(t.split('/')) == 2 and t.split('/')[0].isdigit():
                bp_idx = i
                break
                
        # 如果有找到血壓，就開始往前抓數值
        if bp_idx >= 2:
            try:
                sbp = int(tokens[bp_idx].split('/')[0]) # 收縮壓 (斜線前面的數字)
                hr = int(tokens[bp_idx-2])              # 心跳 (血壓往前數兩個欄位)
                
                # 抓取日期與時間
                date_str = tokens[0] 
                time_str = tokens[1] 
                
                # 自動把民國年轉換為西元年 (例如 115 轉為 2026)，並組合成標準時間格式
                if len(date_str) == 7 and date_str.startswith('1'):
                    greg_year = int(date_str[:3]) + 1911
                    dt_str = f"{date_str[3:5]}/{date_str[5:7]} {time_str[:2]}:{time_str[2:]}"
                else:
                    dt_str = f"{date_str} {time_str}" 
                    
                parsed_data.append({
                    "時間": dt_str,
                    "心跳 (HR)": hr,
                    "收縮壓 (SBP)": sbp,
                    "休克指數 (SI)": round(hr / sbp, 2)
                })
            except Exception as e:
                pass # 如果遇到亂碼或無法解析的行，就安靜地跳過，程式不會崩潰
                
    return pd.DataFrame(parsed_data)


# --- 網頁畫面：批次趨勢圖區塊 ---
st.subheader("📈 留觀生命徵象趨勢圖 (批次匯入)")
batch_vitals = st.text_area("📋 請貼上 HIS 系統的多筆生命徵象表格 (直接複製貼上即可)：", height=150, placeholder="1150315 1400 96 20 171/91 92 simple Mask 6L...")

if st.button("📊 繪製趨勢圖", type="secondary"):
    if batch_vitals.strip() != "":
        # 呼叫上面的神經中樞來處理資料
        df = parse_his_vitals(batch_vitals)
        
        if not df.empty:
            st.success(f"✅ 成功解析 {len(df)} 筆生命徵象紀錄！")
            
            # 使用 Tabs 把圖表跟原始數據分開，畫面更簡潔
            tab1, tab2, tab3 = st.tabs(["📉 休克指數趨勢", "💓 心跳與血壓趨勢", "🗂️ 解析後數據表"])
            
            with tab1:
                st.markdown("#### ⚠️ 休克指數 (SI) 趨勢")
                st.caption("提示：當數值接近或大於 1.0 時，可能有潛在血流動力學不穩定風險。")
                # 畫出紅色的折線圖
                st.line_chart(df.set_index("時間")[["休克指數 (SI)"]], color="#FF4B4B")
                
            with tab2:
                st.markdown("#### 💓 心跳 vs. 收縮壓")
                # 同時畫出兩條線，方便看出交叉點
                st.line_chart(df.set_index("時間")[["心跳 (HR)", "收縮壓 (SBP)"]])
                
            with tab3:
                st.markdown("#### 整理後的乾淨表格")
                st.dataframe(df, use_container_width=True)
        else:
            st.error("❌ 無法解析資料，請確認貼上的格式是否包含日期、時間、心跳與血壓。")
st.divider()
# --- 學理依據與評分標準 (折疊面板) ---
with st.expander("📚 點此查看系統評分標準與學理依據 (Evidence-Based Practice)"):
    st.markdown("""
    ### 1. MEWS (Modified Early Warning Score) 早期預警分數
    * **臨床目的**：用於早期發現潛在的病情惡化，降低院內心跳停止 (IHCA) 的發生率。
    * **評估項目**：體溫、脈搏、呼吸、收縮壓、意識狀態 (GCS)。
    * **風險分層**：
        * **0 - 2 分**：穩定狀態，維持常規留觀 (綠區)。
        * **3 - 4 分**：中度風險，需增加 Vital signs 監測頻率 (黃區)。
        * **≥ 5 分**：高度惡化風險，需立即醫療介入或考慮收治 (紅區)。

    ### 2. 休克指數 (Shock Index, SI)
    * **計算公式**：`心率 (HR) / 收縮壓 (SBP)`
    * **學理依據**：急診常面臨**「隱性休克 (Occult Shock)」**的挑戰。當有效循環血量減少時，身體會先以心跳加快來代償，此時血壓可能仍看似正常。SI 能在血壓崩盤前，提早揪出潛在的血流動力學不穩定。
    * **判斷標準**：
        * **0.5 - 0.7**：正常範圍。
        * **> 0.8**：警戒邊緣，潛在發病率開始上升。
        * **≥ 1.0**：危險值，死亡率與需急救介入的機率大幅提升，直接列為高度風險 (紅區)。

    ### 3. 危險檢驗數值 (Critical Labs)
    留觀期間的動態抽血變化，往往是決定動向的鐵律：
    * **Lactate (乳酸) ≥ 4.0 mmol/L**：代表組織嚴重缺氧，為敗血性休克 (Septic Shock) 等重症的黃金指標，直接觸發紅區警告。
    * **Hs-TnI > 17.5 ng/L**：高敏感度心肌酵素異常，提示急性心肌損傷 (如 ACS)。
    * **K (鉀離子) < 3.0 或 > 6.0 mEq/L**：極端值極易引發致命性心律不整 (致命性 Tachycardia 或 Bradycardia)。
    """)
    
st.divider() # 在折疊面板下方再加一條分隔線，讓排版更乾淨

if st.button("🚀 開始評估並生成紀錄", type="primary"):
    if vitals_input.strip() == "":
        st.error("⚠️ 請先貼上生命徵象！")
    elif gcs_input is None:
        st.error("⚠️ 請輸入 GCS 意識分數！")
    else:
        total_score = 0
        temp = hr = rr = sbp = None 
        
        temp_match = re.search(r'體溫：([\d.]+)', vitals_input)
        if temp_match:
            temp = float(temp_match.group(1))
            total_score += (2 if temp < 35 or temp >= 38.5 else 1 if temp < 36 else 0)

        hr_match = re.search(r'脈搏：(\d+)', vitals_input)
        if hr_match:
            hr = int(hr_match.group(1))
            total_score += (3 if hr <= 40 or hr >= 130 else 2 if 111 <= hr <= 129 else 1 if 41 <= hr <= 50 or 101 <= hr <= 110 else 0)

        rr_match = re.search(r'呼吸：(\d+)', vitals_input)
        if rr_match:
            rr = int(rr_match.group(1))
            total_score += (3 if rr >= 30 else 2 if rr <= 8 or 21 <= rr <= 29 else 1 if 15 <= rr <= 20 else 0)

        sbp_match = re.search(r'血壓：(\d+)/', vitals_input)
        if sbp_match:
            sbp = int(sbp_match.group(1))
            total_score += (3 if sbp <= 70 else 2 if sbp <= 80 or sbp >= 200 else 1 if sbp <= 100 else 0)

        gcs_score = 0
        if gcs_input == 15: gcs_score = 0
        elif 13 <= gcs_input <= 14: gcs_score = 1
        elif 9 <= gcs_input <= 12: gcs_score = 2
        elif gcs_input <= 8: gcs_score = 3
        total_score += gcs_score

        shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

        lab_alert = False
        lab_records_list = []
        
        if k_input.strip() != "":
            k_val = float(k_input)
            if k_val < 3.0 or k_val > 6.0:
                lab_alert = True
            lab_records_list.append(f"K {k_val}")
                
        if tni_input.strip() != "":
            tni_val = float(tni_input)
            if tni_val > 17.5:
                lab_alert = True
            lab_records_list.append(f"TnI {tni_val}")

        if crp_input.strip() != "":
            lab_records_list.append(f"CRP {crp_input}")

        if lactate_input.strip() != "":
            lac_val = float(lactate_input)
            if lac_val >= 4.0:
                lab_alert = True 
            lab_records_list.append(f"Lac {lac_val}")

        risk_level = ""
        if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0):
            risk_level = "🔴 紅區"
            st.error(f"判定結果：{risk_level}") 
        elif total_score >= 3:
            risk_level = "🟡 黃區"
            st.warning(f"判定結果：{risk_level}") 
        else:
            risk_level = "🟢 綠區"
            st.success(f"判定結果：{risk_level}") 

        # --- 產生護理紀錄 (給使用者複製) ---
        st.subheader("📋 護理交班紀錄")
        nursing_note = f"[留觀風險自動評估紀錄]\nMEWS: {total_score}分 (GCS {gcs_input}), SI: {shock_index}\n風險: {risk_level}"
        st.code(nursing_note, language="text")

        # ==========================================
        # 隱藏的後台動作：將這筆資料寫入 CSV 檔案
        # ==========================================
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 準備要存進表格的一筆資料
        new_record = {
            "評估時間": current_time,
            "MEWS分數": total_score,
            "GCS": gcs_input,
            "休克指數": shock_index,
            "檢驗項目": " / ".join(lab_records_list) if lab_records_list else "無",
            "系統判定": risk_level
        }
        
        # 轉換成表格格式並儲存
        df_new = pd.DataFrame([new_record])
        if not os.path.exists(LOG_FILE):
            df_new.to_csv(LOG_FILE, index=False, encoding='utf-8-sig') # 第一次建立檔案
        else:
            df_new.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig') # 之後附加在原本檔案後面
# --- 網頁頁尾：版權與免責聲明 ---
st.divider() # 畫一條底線把主要內容隔開

# 使用 HTML 語法讓文字置中、變小、變灰色，看起來更像專業的網頁頁尾
st.markdown("""
<div style="text-align: center; color: gray; font-size: 0.85em;">
    <p><strong>© 2026 急診留觀風險自動評估系統</strong> | Designed by [護理師 吳智弘]</p>
    <p>⚠️ <b>免責聲明：</b>本系統基於臨床實證醫學 (EBP) 開發，主要作為急診護理人員之交班與風險分層輔助工具，評估結果不可替代臨床醫師之專業診斷與決策。</p>
    <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">
        <img alt="創用 CC 授權條款" style="border-width:0; margin-bottom: 5px;" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" />
    </a>
    <br />本專案採用<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" style="color: gray; text-decoration: underline;">創用 CC 姓名標示-非商業性-相同方式分享 4.0 國際 授權條款</a>授權。
</div>
""", unsafe_allow_html=True)
