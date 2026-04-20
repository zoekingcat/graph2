import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import re
import io

# 최신 Pandas 경고 완전 차단
pd.set_option('future.no_silent_downcasting', True)

st.set_page_config(page_title="배터리 성능 평가 대시보드", page_icon="🔋", layout="wide")

st.title("🔋 종합 데이터 시각화 대시보드")
st.markdown("배터리 표준 평가(RPT/두께)와 범용 데이터 시각화를 모두 지원합니다.")

# --- 유틸리티 함수 ---
def normalize_string(s):
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', str(s)).lower()

def read_file_safely(f):
    bytes_data = f.getvalue() 
    if f.name.lower().endswith('.csv'):
        sheet_name = re.sub(r'\.csv$', '', f.name, flags=re.IGNORECASE)
        try:
            return {sheet_name: pd.read_csv(io.BytesIO(bytes_data), header=None, encoding='utf-8')}
        except Exception:
            try:
                return {sheet_name: pd.read_csv(io.BytesIO(bytes_data), header=None, encoding='cp949')}
            except Exception:
                return {sheet_name: pd.read_csv(io.BytesIO(bytes_data), header=None, encoding='euc-kr')}
    else:
        return pd.read_excel(io.BytesIO(bytes_data), sheet_name=None, header=None)

def read_custom_file_safely(f):
    bytes_data = f.getvalue() 
    if f.name.lower().endswith('.csv'):
        sheet_name = re.sub(r'\.csv$', '', f.name, flags=re.IGNORECASE)
        try:
            return {sheet_name: pd.read_csv(io.BytesIO(bytes_data), encoding='utf-8')}
        except Exception:
            try:
                return {sheet_name: pd.read_csv(io.BytesIO(bytes_data), encoding='cp949')}
            except Exception:
                return {sheet_name: pd.read_csv(io.BytesIO(bytes_data), encoding='euc-kr')}
    else:
        return pd.read_excel(io.BytesIO(bytes_data), sheet_name=None)

def clean_col_name(c):
    norm = normalize_string(c)
    if 'testnumber' in norm: return 'Test_Number'
    if 'samplenumber' in norm: return 'Sample_Number'
    if 'point' in norm: return 'Point'
    if 'retention' in norm: return 'Retention'
    if 'soc' in norm: return 'SOC' 
    if 'testdegree' in norm or 'testtemp' in norm or 'temperature' in norm: return 'Test_Temp'
    return str(c).strip()

def deduplicate_columns(columns):
    seen = {}
    new_cols = []
    for c in columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    return new_cols

def format_sample_number(df):
    if 'Sample_Number' in df.columns:
        s_num = df['Sample_Number'].astype(str).str.replace('#', '').str.replace(r'\.0$', '', regex=True).str.strip()
        if 'Test_Temp' in df.columns:
            temp = df['Test_Temp'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            mask = (temp.str.lower() != 'nan') & (temp != '')
            temp = temp.str.replace('degree', '℃', flags=re.IGNORECASE)
            temp = temp.apply(lambda x: x + '℃' if x.replace('.', '').isdigit() else x)
            s_num = np.where(mask, temp + "_#" + s_num, "#" + s_num)
        else:
            s_num = "#" + s_num
            
        if 'SOC' in df.columns:
            soc = df['SOC'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            mask = (soc.str.lower() != 'nan') & (soc != '')
            s_num = np.where(mask, "SOC" + soc + "_" + s_num, s_num)
            
        df['Sample_Number'] = s_num
    return df

def get_cycle(c):
    c_low = str(c).lower()
    if 'bol' in c_low: return 0
    if '1st' in c_low or '1차' in c_low: return 1
    if '2nd' in c_low or '2차' in c_low: return 2
    if '3rd' in c_low or '3차' in c_low: return 3
    if '4th' in c_low or '4차' in c_low: return 4
    if '5th' in c_low or '5차' in c_low: return 5
    if '6th' in c_low or '6차' in c_low: return 6
    if '7th' in c_low or '7차' in c_low: return 7
    if '8th' in c_low or '8차' in c_low: return 8
    if '9th' in c_low or '9차' in c_low: return 9
    if '10th' in c_low or '10차' in c_low: return 10
    
    m = re.search(r'(\d+)', c_low)
    return int(m.group(1)) if m else None

# --- 사이드바 ---
with st.sidebar:
    st.header("📂 표준 배터리 데이터 업로드")
    st.caption("기존 RPT 및 두께 데이터를 여기에 업로드하세요.")
    cap_files = st.file_uploader("1. 용량(Capacity) 데이터", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key='cap')
    thick_files = st.file_uploader("2. 두께(Thickness) 데이터", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key='thick')

# --- 파싱 로직 (기존 배터리용) ---
def parse_capacity_files(files):
    dfs = []
    for f in files:
        file_dfs = read_file_safely(f)
        for sheet_name, df in file_dfs.items(): 
            if 'sheet1' in sheet_name.lower().replace(" ", ""): continue
            if df.empty: continue
            h_idx = -1
            for i in range(min(20, len(df))):
                row_str = "".join([normalize_string(v) for v in df.iloc[i].fillna('')])
                if 'testnumber' in row_str or 'samplenumber' in row_str:
                    h_idx = i
                    break
            if h_idx == -1: continue 
                
            df.columns = [str(x).strip() for x in df.iloc[h_idx].values]
            df = df.iloc[h_idx + 1:].copy()
            df = df.replace(r'^\s*$', np.nan, regex=True).infer_objects(copy=False)
            df.columns = [clean_col_name(c) for c in df.columns]
            df.columns = deduplicate_columns(df.columns)
            
            if 'Test_Number' not in df.columns:
                df['Test_Number'] = sheet_name.split('(')[0].strip() if '(' in sheet_name else sheet_name
            
            norm_cols = [normalize_string(c) for c in df.columns]
            cap_cols = [c for c, nc in zip(df.columns, norm_cols) if 'capacity' in nc or '용량' in nc or 'discharge' in nc]
            cycle_col = next((c for c, nc in zip(df.columns, norm_cols) if '차수' in nc or 'cycle' in nc or '주기' in nc or 'step' in nc), None)
            
            id_cands = ['testnumber', 'samplenumber', 'testdegree', 'testtemp', 'soc', 'retention', '차수', '파일명', 'sample', '비고']
            id_cols = [c for c in df.columns if any(ic in normalize_string(c) for ic in id_cands) or c in ['Test_Number', 'Test_Temp', 'SOC']]
            
            if id_cols: df[id_cols] = df[id_cols].ffill()
            df = format_sample_number(df)
                
            if cycle_col and cap_cols:
                primary_cap = cap_cols[0]
                temp1 = df.copy()
                temp1['Raw_Col'] = temp1[cycle_col]
                temp1['Capacity'] = temp1[primary_cap]
                temp1['Capacity'] = pd.to_numeric(temp1['Capacity'].astype(str).str.replace(',', ''), errors='coerce')
                temp1 = temp1.dropna(subset=['Capacity'])
                dfs.append(temp1)
                
                for oc in cap_cols[1:]:
                    temp2 = df.copy()
                    temp2['Raw_Col'] = oc
                    temp2['Capacity'] = temp2[oc]
                    temp2['Capacity'] = pd.to_numeric(temp2['Capacity'].astype(str).str.replace(',', ''), errors='coerce')
                    temp2 = temp2.dropna(subset=['Capacity'])
                    dfs.append(temp2)
            else:
                val_cols = [c for c in df.columns if c not in id_cols and str(c).lower() != 'nan' and c]
                melted = df.melt(id_vars=id_cols, value_vars=val_cols, var_name='_Temp_Raw_', value_name='_Temp_Val_')
                melted = melted.rename(columns={'_Temp_Raw_': 'Raw_Col', '_Temp_Val_': 'Capacity'})
                melted['Capacity'] = pd.to_numeric(melted['Capacity'].astype(str).str.replace(',', ''), errors='coerce')
                melted = melted.dropna(subset=['Capacity'])
                dfs.append(melted)
        
    if not dfs: return pd.DataFrame()
    final_df = pd.concat(dfs, ignore_index=True)
    final_df['Cycle'] = final_df['Raw_Col'].apply(get_cycle)
    final_df = final_df.dropna(subset=['Cycle']).sort_values('Cycle')
    
    if 'Test_Number' in final_df.columns:
        final_df['Test_Number'] = final_df['Test_Number'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        final_df = final_df[final_df['Test_Number'].str.lower() != 'nan']
    if 'Sample_Number' in final_df.columns:
        final_df['Sample_Number'] = final_df['Sample_Number'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        final_df = final_df[final_df['Sample_Number'].str.lower() != 'nan']
    return final_df

def parse_thickness_files(files):
    dfs = []
    for f in files:
        file_dfs = read_file_safely(f)
        for sheet_name, df in file_dfs.items(): 
            if 'sheet1' in sheet_name.lower().replace(" ", ""): continue
            if df.empty: continue
            h_idx = -1
            for i in range(min(20, len(df))):
                row_str = "".join([normalize_string(v) for v in df.iloc[i].fillna('')])
                if 'testnumber' in row_str or 'samplenumber' in row_str:
                    h_idx = i
                    break
            if h_idx == -1: continue 
                
            if h_idx > 0:
                row_above = pd.Series(df.iloc[h_idx - 1].values).ffill() 
                row_curr = df.iloc[h_idx].fillna('')
                cols = []
                for a, b in zip(row_above, row_curr):
                    a_s, b_s = str(a).strip(), str(b).strip()
                    if 'cycle' in a_s.lower(): cols.append(f"{a_s}_{b_s}" if b_s else a_s)
                    else: cols.append(b_s if b_s else (a_s if a_s.lower() != 'nan' else 'Unknown'))
            else:
                cols = [str(x).strip() for x in df.iloc[h_idx].values]
                
            df.columns = cols
            df = df.iloc[h_idx + 1:].copy()
            df = df.replace(r'^\s*$', np.nan, regex=True).infer_objects(copy=False)
            df.columns = [clean_col_name(c) for c in df.columns]
            df.columns = deduplicate_columns(df.columns)
            
            if 'Test_Number' not in df.columns:
                df['Test_Number'] = sheet_name.split('(')[0].strip() if '(' in sheet_name else sheet_name
                
            id_cands = ['testnumber', 'samplenumber', 'point', 'testtemp', 'testdegree', '두께확인', 'soc']
            id_cols = [c for c in df.columns if any(ic in normalize_string(c) for ic in id_cands) or c in ['Test_Number', 'Test_Temp', 'SOC']]
            
            if id_cols: df[id_cols] = df[id_cols].ffill()
            df = format_sample_number(df)
                
            val_cols = [c for c in df.columns if c not in id_cols and c != 'Unknown' and str(c).lower() != 'nan' and c]
            melted = df.melt(id_vars=id_cols, value_vars=val_cols, var_name='_Temp_Raw_', value_name='_Temp_Val_')
            melted = melted.rename(columns={'_Temp_Raw_': 'Raw_Col', '_Temp_Val_': 'Thickness'})
            melted['Thickness'] = pd.to_numeric(melted['Thickness'].astype(str).str.replace(',', ''), errors='coerce')
            melted = melted.dropna(subset=['Thickness'])
            dfs.append(melted)
            
    if not dfs: return pd.DataFrame()
    final_df = pd.concat(dfs, ignore_index=True)
    
    def get_cond(c):
        if '완충' in c: return '완충후'
        if '2시간' in c: return '2시간후'
        if 'rpt' in c.lower(): return 'RPT이후'
        return '기본측정'
        
    def get_cond_order(c):
        if c == '완충후': return 1
        if c == '2시간후': return 2
        if c == 'RPT이후': return 3
        return 4

    final_df['Cycle'] = final_df['Raw_Col'].apply(get_cycle)
    final_df['Condition'] = final_df['Raw_Col'].apply(get_cond)
    final_df['Cond_Order'] = final_df['Condition'].apply(get_cond_order)
    final_df = final_df.dropna(subset=['Cycle']).sort_values(['Cycle', 'Cond_Order'])
    
    if 'Test_Number' in final_df.columns:
        final_df['Test_Number'] = final_df['Test_Number'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        final_df = final_df[final_df['Test_Number'].str.lower() != 'nan']
    if 'Sample_Number' in final_df.columns:
        final_df['Sample_Number'] = final_df['Sample_Number'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        final_df = final_df[final_df['Sample_Number'].str.lower() != 'nan']
    
    return final_df

with st.spinner('데이터를 분석하고 변환하는 중입니다...'):
    df_cap = parse_capacity_files(cap_files) if cap_files else pd.DataFrame()
    df_thick = parse_thickness_files(thick_files) if thick_files else pd.DataFrame()

# 💡 상단 탭 구성
tab_std, tab_custom = st.tabs(["🔋 1. 표준 배터리 분석 (RPT/두께)", "📈 2. 범용 데이터 시각화 (자유형식)"])

# ==========================================
# 탭 1: 기존 표준 배터리 분석
# ==========================================
with tab_std:
    if df_cap.empty and df_thick.empty:
        st.info("👈 왼쪽 사이드바에서 엑셀 또는 CSV 파일을 하나 이상 업로드해주세요.")
    else:
        st.header("📊 배터리 데이터 시각화 설정")
        
        st.write("📈 **그래프 표시 옵션**")
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            graph_style = st.radio("그래프 마커 스타일", ["선 + 점 표시", "점만 표시"], horizontal=True)
            draw_mode = 'lines+markers' if '선' in graph_style else 'markers'
        with col_opt2:
            thick_line_mode = st.radio("두께 그래프 선 연결 방식", ["조건별 분리 (완충끼리, 2시간끼리)", "시간순 지그재그 연결 (완충→2시간→RPT)"], horizontal=True)
        
        st.divider()

        all_tests = set()
        if not df_cap.empty and 'Test_Number' in df_cap.columns: all_tests.update(df_cap['Test_Number'].dropna().unique())
        if not df_thick.empty and 'Test_Number' in df_thick.columns: all_tests.update(df_thick['Test_Number'].dropna().unique())
        all_tests = sorted([str(x) for x in all_tests if str(x).lower() != 'nan' and x])
        
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            selected_tests = st.multiselect("Test Number 선택 (다중 선택 가능)", options=all_tests, default=all_tests[:1] if all_tests else None)
            
        all_samples = set()
        if selected_tests:
            if not df_cap.empty and 'Sample_Number' in df_cap.columns:
                all_samples.update(df_cap[df_cap['Test_Number'].isin(selected_tests)]['Sample_Number'].dropna().unique())
            if not df_thick.empty and 'Sample_Number' in df_thick.columns:
                all_samples.update(df_thick[df_thick['Test_Number'].isin(selected_tests)]['Sample_Number'].dropna().unique())
        all_samples = sorted([str(x) for x in all_samples if str(x).lower() != 'nan' and x])
        
        with col_filter2:
            selected_samples = st.multiselect("Sample Number 선택 (비워두면 전체 표시)", options=all_samples, default=all_samples[:1] if all_samples else None)
            if not selected_samples: selected_samples = all_samples

        st.divider()
        col_graph1, col_graph2 = st.columns(2)
        
        with col_graph1:
            st.subheader("🔵 용량 유지율 (Capacity)")
            if not df_cap.empty and selected_tests:
                plot_df_cap = df_cap[(df_cap['Test_Number'].isin(selected_tests)) & (df_cap['Sample_Number'].isin(selected_samples))]
                if not plot_df_cap.empty:
                    plot_df_cap['Legend'] = plot_df_cap['Test_Number'] + " (" + plot_df_cap['Sample_Number'] + ")"
                    fig_cap = px.line(plot_df_cap, x='Cycle', y='Capacity', color='Legend', markers=True, labels={'Cycle': '주기(Cycle)', 'Capacity': '용량(Ah)'}, template="plotly_white")
                    fig_cap.update_traces(mode=draw_mode, line=dict(width=2), marker=dict(size=7)) 
                    fig_cap.update_layout(xaxis=dict(tickformat="d"))
                    st.plotly_chart(fig_cap, use_container_width=True)
                else:
                    st.warning("선택한 조건에 맞는 용량 데이터가 없습니다.")
            else:
                st.info("용량 데이터를 업로드해주세요.")

        with col_graph2:
            st.subheader("🔴 두께 변화 추이 (Thickness)")
            if not df_thick.empty and selected_tests:
                # 💡 핵심: "특정 포인트 선택" 옵션 추가
                thick_view_mode = st.radio("데이터 계산 방식", ["포인트별 평균 (권장)", "전체 포인트 모두 보기", "특정 포인트 선택"], horizontal=True)
                plot_df_thick = df_thick[(df_thick['Test_Number'].isin(selected_tests)) & (df_thick['Sample_Number'].isin(selected_samples))]
                
                if not plot_df_thick.empty:
                    if 'Point' not in plot_df_thick.columns: plot_df_thick['Point'] = "1"
                    
                    # 💡 "특정 포인트 선택" 모드일 경우 다중 선택 창 활성화
                    if thick_view_mode == "특정 포인트 선택":
                        # 1, 2, 10(전체) 등을 숫자 순서대로 정렬하기 위한 함수
                        def sort_pt(x):
                            nums = re.findall(r'\d+', str(x))
                            return int(nums[0]) if nums else 999
                        
                        avail_pts = sorted(plot_df_thick['Point'].dropna().unique(), key=sort_pt)
                        selected_pts = st.multiselect("📌 조회할 측정 포인트(Point)를 선택하세요", options=avail_pts, default=avail_pts[:1] if avail_pts else None)
                        
                        if selected_pts:
                            plot_df_thick = plot_df_thick[plot_df_thick['Point'].astype(str).isin([str(p) for p in selected_pts])]

                    # 선택된 모드에 따라 데이터 가공
                    if thick_view_mode == "포인트별 평균 (권장)":
                        plot_df_thick = plot_df_thick.groupby(['Test_Number', 'Sample_Number', 'Cycle', 'Condition', 'Cond_Order'])['Thickness'].mean().reset_index()
                        plot_df_thick['Legend'] = plot_df_thick['Test_Number'] + " (" + plot_df_thick['Sample_Number'] + ")"
                    else:
                        plot_df_thick['Legend'] = plot_df_thick['Test_Number'] + " (" + plot_df_thick['Sample_Number'] + "_P" + plot_df_thick['Point'].astype(str) + ")"

                    # 데이터가 비어있지 않은지 한 번 더 체크 후 그래프 그리기
                    if not plot_df_thick.empty:
                        if "지그재그" in thick_line_mode:
                            plot_df_thick = plot_df_thick.sort_values(['Cycle', 'Cond_Order'])
                            plot_df_thick['Timeline'] = plot_df_thick['Cycle'].astype(str) + "C<br>" + plot_df_thick['Condition']
                            fig_thick = px.line(plot_df_thick, x='Timeline', y='Thickness', color='Legend', markers=True, labels={'Timeline': '측정 시점 (주기 및 조건)', 'Thickness': '두께(mm)'}, template="plotly_white")
                        else:
                            fig_thick = px.line(plot_df_thick, x='Cycle', y='Thickness', color='Legend', line_dash='Condition', markers=True, labels={'Cycle': '주기(Cycle)', 'Thickness': '두께(mm)', 'Condition': '측정조건'}, template="plotly_white")
                        
                        fig_thick.update_traces(mode=draw_mode, line=dict(width=2), marker=dict(size=7)) 
                        if "지그재그" in thick_line_mode: fig_thick.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig_thick, use_container_width=True)
                    else:
                        st.warning("선택한 포인트에 해당하는 데이터가 없습니다.")
                else:
                    st.warning("선택한 조건에 맞는 두께 데이터가 없습니다.")
            else:
                st.info("두께 데이터를 업로드해주세요.")

        with st.expander("변환된 원본 데이터 미리보기 (클릭하여 펼치기)"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**용량(Capacity) 파싱 결과**")
                if not df_cap.empty: st.dataframe(df_cap.head(50), use_container_width=True)
            with c2:
                st.markdown("**두께(Thickness) 파싱 결과**")
                if not df_thick.empty: st.dataframe(df_thick.head(50), use_container_width=True)


# ==========================================
# 탭 2: 신규 범용 데이터 시각화 (자유 지정)
# ==========================================
with tab_custom:
    st.header("📈 범용 그래프 생성기")
    st.write("표준 포맷이 아닌 일반적인 엑셀/CSV 파일을 여러 개 업로드하고, 원하는 열(Column)을 직접 선택해 그래프를 그리세요.")
    
    # 여러 파일 업로드 가능하도록 accept_multiple_files=True 옵션
    custom_files = st.file_uploader("📂 데이터 파일 업로드 (여러 파일 선택 가능)", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key='custom')
    
    if custom_files:
        all_custom_dfs = {}
        for f in custom_files:
            file_dfs = read_custom_file_safely(f)
            for sheet_name, df in file_dfs.items():
                # CSV 파일은 이름만, 엑셀은 파일명+시트명으로 깔끔하게 표시
                if sheet_name == re.sub(r'\.csv$', '', f.name, flags=re.IGNORECASE):
                    key_name = f.name
                else:
                    key_name = f"{f.name} - [{sheet_name}]"
                
                # 💡 핵심 추가: 각 데이터 행마다 '파일명' 꼬리표를 달아 출처를 명확히 기록
                df['파일명'] = key_name
                
                all_custom_dfs[key_name] = df
        
        st.write("🛠️ **데이터 선택 옵션**")
        merge_files = st.checkbox("✅ 업로드한 모든 파일/시트 데이터를 하나로 병합하여 한 번에 그리기 (모두 같은 양식일 때 강력 추천)")
        
        if merge_files:
            # 모든 파일의 데이터를 세로로 길게 하나로 합침
            df_custom = pd.concat(list(all_custom_dfs.values()), ignore_index=True)
            st.success(f"성공! 총 {len(all_custom_dfs)}개의 파일(시트) 데이터가 하나로 병합되었습니다.")
        else:
            col_s1, col_s2 = st.columns([1, 3])
            with col_s1:
                # 엑셀에 여러 시트가 있거나 여러 파일일 경우 선택
                sheet_names = list(all_custom_dfs.keys())
                selected_sheet = st.selectbox("분석할 파일/시트 선택", options=sheet_names)
            df_custom = all_custom_dfs[selected_sheet]
        
        if not df_custom.empty:
            st.write("📝 **데이터 미리보기 (상위 5행)**")
            st.dataframe(df_custom.head(5), use_container_width=True)
            
            st.divider()
            st.subheader("⚙️ 그래프 축 설정")
            
            c1, c2, c3, c4 = st.columns(4)
            cols = list(df_custom.columns)
            with c1:
                x_col = st.selectbox("X축 선택 (가로)", options=cols)
            with c2:
                # Y축 다중 선택 (멀티 셀렉트)
                y_cols = st.multiselect("Y축 다중 선택 (세로)", options=cols, default=[cols[1]] if len(cols) > 1 else None)
            with c3:
                color_col = st.selectbox("구분/범례 (선택사항)", options=["(사용 안함)"] + cols)
            with c4:
                chart_type = st.selectbox("그래프 종류", options=["선 그래프 (Line)", "점 그래프 (Scatter)", "막대 그래프 (Bar)"])
                
            if st.button("📊 범용 그래프 그리기", type="primary"):
                if not y_cols:
                    st.warning("Y축을 하나 이상 선택해주세요.")
                else:
                    try:
                        # 💡 핵심 변경: 파일명과 선택한 구분값을 결합하여 '파일명_인자' 형태의 새로운 범례 컬럼 생성
                        legend_col_name = "데이터 구분 (범례)"
                        if color_col != "(사용 안함)":
                            df_custom[legend_col_name] = df_custom['파일명'] + "_" + df_custom[color_col].astype(str)
                        else:
                            # 구분값을 선택하지 않아도 병합 시 파일명으로 색상이 분리되도록 설정
                            df_custom[legend_col_name] = df_custom['파일명']
                            
                        if chart_type == "선 그래프 (Line)":
                            fig_custom = px.line(df_custom, x=x_col, y=y_cols, color=legend_col_name, markers=True, template="plotly_white")
                        elif chart_type == "점 그래프 (Scatter)":
                            fig_custom = px.scatter(df_custom, x=x_col, y=y_cols, color=legend_col_name, template="plotly_white")
                        else:
                            fig_custom = px.bar(df_custom, x=x_col, y=y_cols, color=legend_col_name, barmode='group', template="plotly_white")
                            
                        fig_custom.update_traces(marker=dict(size=7))
                        if chart_type == "선 그래프 (Line)":
                            fig_custom.update_traces(line=dict(width=2))
                            
                        st.plotly_chart(fig_custom, use_container_width=True)
                    except Exception as e:
                        st.error(f"그래프를 그리는 중 오류가 발생했습니다. 선택한 열에 문자가 포함되어 있진 않은지 확인해주세요. (에러내용: {e})")