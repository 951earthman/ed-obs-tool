import streamlit as st
import re

# --- 網頁標題與說明 ---
st.title("🚨 急診留觀風險自動評估系統")
st.markdown("快速計算 MEWS、休克指數，並整合危險檢驗值 (K, Hs-TnI)，自動生成護理交班紀錄。")
st.divider() # 畫一條分隔線

# --- 第一區塊：輸入生命徵象 ---
st.subheader("1. 貼上生命徵象")
vitals_input = st.text_area("📋 請直接從系統複製貼上 (例如：體溫：36.0 ℃；脈搏：85 次...)", height=100)

# --- 第二區塊：輸入檢驗報告 (選填) ---
st.subheader("2. 補充檢驗報告 (若無則留白)")
# 把畫面分成左右兩半，排版比較好看
col1, col2 = st.columns(2)

with col1:
    k_input = st.text_input("➤ 鉀離子 (K) 數值：", placeholder="例如：2.5")
with col2:
    tni_input = st.text_input("➤ Hs-TnI 數值：", placeholder="例如：18.2")

st.divider()

# --- 按下按鈕後開始運算 ---
if st.button("🚀 開始評估並生成紀錄", type="primary"):
    if vitals_input.strip() == "":
        st.error("⚠️ 請先貼上生命徵象！")
    else:
        # (這裡放的是我們剛剛寫好的計算邏輯)
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

        shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

        lab_alert = False
        lab_records_list = []
        
        if k_input.strip() != "":
            k_val = float(k_input)
            if k_val < 3.0 or k_val > 6.0:
                lab_alert = True
                lab_records_list.append(f"鉀離子 {k_val} mEq/L (Critical)")
            else:
                lab_records_list.append(f"鉀離子 {k_val} mEq/L")
                
        if tni_input.strip() != "":
            tni_val = float(tni_input)
            if tni_val > 17.5:
                lab_alert = True
                lab_records_list.append(f"Hs-TnI {tni_val} (異常大於17.5！)")
            else:
                lab_records_list.append(f"Hs-TnI {tni_val} (正常)")

        if len(lab_records_list) > 0:
            lab_record_text = " / ".join(lab_records_list)
        else:
            lab_record_text = "無特殊異常或未驗"

        risk_level = ""
        disposition = ""
        if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0):
            risk_level = "🔴 高度風險 (紅區)"
            disposition = "立即通知醫師評估處置，建議收治或轉急救區。"
            st.error(f"判定結果：{risk_level}") # 網頁上的紅色警告框
        elif total_score >= 3:
            risk_level = "🟡 中度風險 (黃區)"
            disposition = "需密切觀察，增加 Vital signs 監測頻率。"
            st.warning(f"判定結果：{risk_level}") # 網頁上的黃色警告框
        else:
            risk_level = "🟢 穩定狀態 (綠區)"
            disposition = "生命徵象穩定，持續常規留觀或提醒醫師評估 MBD。"
            st.success(f"判定結果：{risk_level}") # 網頁上的綠色成功框

        # --- 產生護理紀錄 ---
        st.subheader("📋 護理交班紀錄 (請直接複製)")
        nursing_note = f"""[留觀風險自動評估紀錄]
1. 當下生理數值：體溫 {temp}℃, 脈搏 {hr}次/分, 呼吸 {rr}次/分, 血壓 {sbp}mmHg (預設GCS 15分)
2. 預警指標運算：MEWS 總分 {total_score} 分 / 休克指數 (SI) {shock_index}
3. 關鍵檢驗數值：{lab_record_text}
4. 系統判定風險：{risk_level}
5. 建議動向處置：{disposition}"""
        
        # st.code 會產生一個帶有一鍵複製按鈕的漂亮區塊
        st.code(nursing_note, language="text")
