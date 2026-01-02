import streamlit as st
from renderer import render_impact_menu_png, PARISH_LIST

st.set_page_config(page_title="Impact Menu", layout="centered")

# Simple styling
st.markdown(
    """
    <style>
    .block-container { max-width: 980px; padding-top: 2rem; padding-bottom: 3rem; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("See the impact of your donation")

st.write(
    "Choose a tier or enter another amount. This generates a live impact menu based on your donation."
)

# Preset buttons
tiers = [10_000, 20_000, 50_000, 100_000]
cols = st.columns(len(tiers))
if "amount" not in st.session_state:
    st.session_state.amount = 10_000

for i, amt in enumerate(tiers):
    if cols[i].button(f"£{amt//1000}k", use_container_width=True):
        st.session_state.amount = amt

# Numeric input
amount = st.number_input(
    "Enter an amount in GBP (£)",
    min_value=1,
    max_value=5_000_000,
    value=int(st.session_state.amount),
    step=100,
)

st.session_state.amount = int(amount)

# Optional parish selector (auto by default)
with st.expander("Optional: choose a parish"):
    parish_mode = st.radio("Parish selection", ["Auto", "Choose"], horizontal=True)
    parish = None
    if parish_mode == "Choose":
        parish = st.selectbox("Parish", PARISH_LIST, index=0)

# Generate
st.divider()
if st.button("Generate impact menu", type="primary", use_container_width=True):
    try:
        png_bytes, imp = render_impact_menu_png(float(st.session_state.amount), parish=parish)

        st.success(f"Generated for {imp.parish} • {st.session_state.amount:,} GBP")
        st.image(png_bytes, caption="Impact Menu", use_container_width=True)

        st.download_button(
            "Download PNG",
            data=png_bytes,
            file_name=f"impact_menu_{imp.parish.replace(' ','_').lower()}_{st.session_state.amount}.png",
            mime="image/png",
            use_container_width=True
        )
    except Exception as e:
        st.error("Generation failed. Check your assets/fonts and assets images.")
        st.exception(e)

st.caption("Tip: Add farmer photos in assets/farmers and crop photos in assets/crops for the best look.")