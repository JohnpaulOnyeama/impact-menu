import time
import streamlit as st
from renderer import render_impact_menu_png, PARISH_LIST, fmt_gbp

st.set_page_config(page_title="Impact Menu", page_icon="🌱", layout="centered")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 920px;}

/* Buttons */
.stButton>button {
    border-radius: 12px !important;
    padding: 0.75rem 1rem !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
}

/* Selected tier button style */
.tier-selected button {
    background: #1e5a3f !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# Session state
# --------------------------
if "amount" not in st.session_state:
    st.session_state.amount = 10000.0
if "tier" not in st.session_state:
    st.session_state.tier = 10000

# --------------------------
# Header
# --------------------------
st.title("See the impact of your donation")
st.write("Choose a tier or enter another amount. This generates a live impact menu based on your donation.")

# --------------------------
# Tier buttons (highlight stays)
# --------------------------
tiers = [10000, 20000, 50000, 100000]
labels = ["£10k", "£20k", "£50k", "£100k"]

cols = st.columns(4)
for c, t, lab in zip(cols, tiers, labels):
    cls = "tier-selected" if st.session_state.tier == t else ""
    with c:
        st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
        if st.button(lab, use_container_width=True):
            st.session_state.tier = t
            st.session_state.amount = float(t)
        st.markdown("</div>", unsafe_allow_html=True)

# --------------------------
# Numeric input
# --------------------------
amount = st.number_input(
    "Enter an amount in GBP (£)",
    min_value=1.0,
    value=float(st.session_state.amount),
    step=100.0
)
st.session_state.amount = float(amount)

# If user types custom number, unselect the tier highlight
if int(st.session_state.amount) not in tiers:
    st.session_state.tier = -1

# --------------------------
# Optional parish selector
# --------------------------
with st.expander("Optional: choose a parish"):
    parish_choice = st.selectbox("Parish", ["Auto-pick"] + PARISH_LIST, index=0)

parish = None if parish_choice == "Auto-pick" else parish_choice

st.divider()

# --------------------------
# Generate
# --------------------------
if st.button("Generate impact menu", type="primary", use_container_width=True):
    with st.spinner("Generating your impact menu..."):
        prog = st.progress(0)

        # Smooth "perceived loading"
        for i in range(1, 6):
            time.sleep(0.07)
            prog.progress(i * 14)

        png_bytes, imp = render_impact_menu_png(float(st.session_state.amount), parish=parish)

        for i in range(6, 8):
            time.sleep(0.05)
            prog.progress(70 + (i - 6) * 15)

        prog.progress(100)

    st.success(f"Impact summary for {fmt_gbp(imp.donation_gbp)} in {imp.parish}")
    st.image(png_bytes, use_container_width=True)

    st.download_button(
        "Download PNG",
        data=png_bytes,
        file_name=f"impact_menu_{imp.parish.replace(' ','_').lower()}_{int(imp.donation_gbp)}.png",
        mime="image/png",
        use_container_width=True
    )

st.caption("Tip: Add strong farmer and crop photos in assets/ for the best look.")