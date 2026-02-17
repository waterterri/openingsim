import streamlit as st
import math
import pandas as pd

# --- COPY YOUR OpeningSim AND FindMinAttack CLASSES/FUNCTIONS HERE ---
# (Keep the classes exactly as you wrote them)

st.set_page_config(page_title="Game Simulation Optimizer", layout="wide")

st.title("🎮 Opening Simulation Optimizer")

# Sidebar: Base Configuration
st.sidebar.header("Base Attacks")
base_data = pd.DataFrame([
    [64, 15.33], [81, 15.53], [91, 35.55], 
    [164, 0.10], [172, 22.17], [181, 31.35], [191, 76.27]
], columns=["Tick", "Percent"])

edited_base = st.sidebar.data_editor(base_data, num_rows="dynamic")

# Main UI: Chain Optimization
col1, col2 = st.columns(2)

with col1:
    st.subheader("Chain Optimizer")
    ticks_input = st.text_input("Ticks to optimize (comma separated)", "462, 471, 481, 491")
    
    if st.button("Run Optimizer"):
        test_ticks = [int(t.strip()) for t in ticks_input.split(",")]
        base_list = edited_base.values.tolist()
        
        with st.spinner("Optimizing..."):
            optimized = OptimizeChain(base_list, test_ticks)
            
        if optimized:
            st.success("Optimization Complete!")
            st.dataframe(pd.DataFrame(optimized, columns=["Tick", "Percent"]))
            
            # Verification Run
            st.subheader("Simulation Log")
            sim = OpeningSim(optimized, verbosity=1)
            # Capture stdout to show in web app
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                sim.Run(505)
            st.code(f.getvalue())

with col2:
    st.subheader("Manual Test")
    single_tick = st.number_input("Test Tick", value=462)
    single_percent = st.slider("Test Percentage", 0.0, 100.0, 15.0)
    
    if st.button("Test Single Run"):
        manual_attacks = edited_base.values.tolist() + [[single_tick, single_percent]]
        sim = OpeningSim(manual_attacks, verbosity=2)
        f = io.StringIO()
        with redirect_stdout(f):
            land, success = sim.Run(505)
        st.write(f"**Success:** {success} | **Final Land:** {land}")
        st.code(f.getvalue())
