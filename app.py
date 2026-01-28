import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Engineering Playground", layout="wide")
st.title("Engineering Playground ")
st.write("시장 분석 자동화 결과를 대시보드로 확인합니다.")

# CSV 경로 (snapshots 폴더 기준)
daily_path = os.path.join("snapshots", "daily_interest_metrics.csv")
graph_path = os.path.join("snapshots", "graph_edges_snapshot.csv")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Daily Interest Metrics")
    if os.path.exists(daily_path):
        df = pd.read_csv(daily_path)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("snapshots/daily_interest_metrics.csv 파일이 없습니다. run_daily.bat 또는 수집 스크립트를 먼저 실행하세요.")

with col2:
    st.subheader("Graph Edges Snapshot")
    if os.path.exists(graph_path):
        df2 = pd.read_csv(graph_path)
        st.dataframe(df2, use_container_width=True)
    else:
        st.info("snapshots/graph_edges_snapshot.csv 파일이 없습니다. 먼저 생성해 주세요.")