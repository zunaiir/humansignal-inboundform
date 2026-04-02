import streamlit as st
from inbound_qualifier import process_lead_submission

st.set_page_config(layout="wide", page_title="HumanSignal Contact Sales")

st.markdown("""
<style>
    .stApp {
        background-color: #000000;
    }

    .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    footer, header {
        visibility: hidden;
    }

    .stMarkdown, .stMarkdown p, .stMarkdown span, p, span, div {
        color: white !important;
    }

    label {
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }

    .stTextInput input {
        background: #F5F5F5 !important;
        color: black !important;
        border-radius: 8px !important;
        border: none !important;
        box-shadow: none !important;
    }

    .stTextArea textarea {
        background: #F5F5F5 !important;
        color: black !important;
        border-radius: 8px !important;
        border: none !important;
        box-shadow: none !important;
        min-height: 140px;
    }

    div[data-baseweb="select"] {
        background: #F5F5F5 !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="select"] > div {
        background: #F5F5F5 !important;
        border-radius: 8px !important;
        border: none !important;
        box-shadow: none !important;
        min-height: 44px !important;
    }

    div[data-baseweb="select"] div {
        background: #F5F5F5 !important;
        color: black !important;
    }

    div[data-baseweb="select"] span {
        color: black !important;
    }

    div[data-baseweb="select"] div[data-testid="stMarkdownContainer"] p {
        color: black !important;
    }

    div[data-baseweb="select"] [data-testid="stMarkdownContainer"] {
        color: black !important;
    }

    div[data-baseweb="select"] svg {
        fill: black !important;
    }

    ul[role="listbox"] li {
        color: black !important;
        background: white !important;
    }

    ul[role="listbox"] li:hover {
        background: #EAEAEA !important;
        color: black !important;
    }

    .stButton > button {
        background-color: #E8604C !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100%;
        border: none !important;
        min-height: 46px;
    }

    .stButton > button:hover {
        background-color: #D04E3A !important;
        color: white !important;
    }

    .gradient-text {
        background: linear-gradient(90deg, #ff7a18, #ff4d6d);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .left-wrap {
        padding-top: 2rem;
        padding-right: 2rem;
    }

    .eyebrow {
        color: #ff6a3d !important;
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin-bottom: 1.25rem;
    }

    .hero-title {
        font-size: 64px;
        line-height: 1.05;
        font-weight: 700;
        margin: 0 0 1.25rem 0;
        color: white !important;
    }

    .hero-copy {
        max-width: 560px;
        color: #CFCFCF !important;
        font-size: 17px;
        line-height: 1.6;
        margin-bottom: 3rem;
    }

    .trusted {
        color: #FFFFFF !important;
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin-top: 2rem;
    }

    .form-title {
        color: white !important;
        font-size: 1.9rem;
        font-weight: 700;
        margin-bottom: 0.75rem;
    }

    .internal-card {
        background: #111111;
        border: 1px solid #2A2A2A;
        border-radius: 16px;
        padding: 1.2rem 1.2rem;
        margin-top: 1rem;
    }

    .pill {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 700;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }

    .pill-green {
        background: rgba(34, 197, 94, 0.15);
        color: #86EFAC !important;
        border: 1px solid rgba(34, 197, 94, 0.35);
    }

    .pill-yellow {
        background: rgba(245, 158, 11, 0.15);
        color: #FCD34D !important;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }

    .section-title {
        font-size: 0.9rem;
        font-weight: 700;
        color: white !important;
        margin-top: 0.4rem;
        margin-bottom: 0.45rem;
    }

    .reason-box {
        background: #171717;
        border-radius: 12px;
        padding: 0.9rem 1rem;
        border: 1px solid #2D2D2D;
    }

    .small-muted {
        color: #BDBDBD !important;
        font-size: 0.92rem;
    }
</style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1.15, 1], gap="large")

with col1:
    st.markdown('<div class="left-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">• CONTACT SALES</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-title">
            Chat with one <br>
            of our <span class="gradient-text">humans</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div class="hero-copy">
            Get pricing, have your technical questions answered, and learn more
            about how HumanSignal can help you create differentiated models
            quickly and efficiently. Our experts are here to help.
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="trusted">TRUSTED BY 350,000+ USERS ACROSS ALL INDUSTRIES</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="form-title">Talk to Sales</div>', unsafe_allow_html=True)

    first_name = st.text_input("First name")
    last_name = st.text_input("Last name")
    company_email = st.text_input("Company email")
    company = st.text_input("Company")

    using_label_studio_oss = st.selectbox(
        "Are you currently using the Label Studio open source project?",
        ["Please Select", "Yes", "No"]
    )

    reason_for_reaching_out = st.text_area(
        "Tell us a little bit about why you're reaching out today."
    )

    submitted = st.button("Submit")

    if submitted:
        if (
            not first_name.strip()
            or not last_name.strip()
            or not company_email.strip()
            or not company.strip()
            or using_label_studio_oss == "Please Select"
            or not reason_for_reaching_out.strip()
        ):
            st.error("Please complete all fields.")
        else:
            payload = {
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "company_email": company_email.strip(),
                "company": company.strip(),
                "using_label_studio_oss": using_label_studio_oss.strip(),
                "reason_for_reaching_out": reason_for_reaching_out.strip(),
            }

            with st.spinner("Sending this over to the team..."):
                try:
                    result = process_lead_submission(payload)
                except Exception as e:
                    st.error(f"Qualification failed: {e}")
                    st.stop()

            st.success("Thanks — our team will review your request and follow up shortly.")
