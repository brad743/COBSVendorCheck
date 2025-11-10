# app.py
# --- Booking System Shortlist Tool (Streamlit Version) ---

import pandas as pd
import streamlit as st
from io import StringIO

# --- Page setup ---
st.set_page_config(page_title="Booking System Shortlist Tool", layout="wide")
st.title("🧩 Booking System Shortlist Tool")
st.write(
    "Upload your **vendor list** and **requirements checklist** CSV files. "
    "The app will compare them and generate a ranked shortlist."
)

# --- File uploads ---
vendor_file = st.file_uploader("📁 Upload Vendor List CSV", type=["csv"])
req_file = st.file_uploader("📋 Upload Requirements Checklist CSV", type=["csv"])
threshold = st.slider("Match Threshold (%)", 0, 100, 45)

# --- Utility: find probable column names ---
def find_col(df, candidates):
    cols = [c for c in df.columns]
    lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    for cand in candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None

if vendor_file and req_file:
    vendor_df = pd.read_csv(vendor_file)
    req_df = pd.read_csv(req_file)
    st.success("✅ Files uploaded successfully")

    vendor_name_col = find_col(vendor_df, ["name", "vendor", "vendor name"])
    req_title_col = find_col(req_df, ["essential criteria", "requirement", "criteria", "essential"])
    req_required_col = find_col(req_df, ["required", "must", "mandatory"])

    st.write("**Detected columns:**")
    st.write(f"- Vendor name: `{vendor_name_col}`")
    st.write(f"- Requirement title: `{req_title_col}`")
    st.write(f"- Required flag: `{req_required_col or 'None detected'}`")

    # --- Filter requirements ---
    if req_required_col:
        def is_required(val):
            s = str(val).strip().lower()
            return s in ("yes","y","true","1","required","must")
        req_df = req_df[req_df[req_required_col].apply(is_required)]

    requirements = req_df[req_title_col].dropna().astype(str).str.lower().tolist()
    total_requirements = len(requirements)
    st.write(f"Total requirements evaluated: **{total_requirements}**")

    # --- Normalize vendor text ---
    vendor_df = vendor_df.fillna("").astype(str)
    vendor_df_lower = vendor_df.applymap(lambda x: x.lower())

    def vendor_text(row):
        return " ".join(row.values)
    vendor_texts = vendor_df_lower.apply(vendor_text, axis=1)

    # --- Matching logic ---
    def req_matches_text(req, text):
        tokens = [t for t in req.replace("/", " ").replace("-", " ").split() if len(t) >= 3]
        return any(tok in text for tok in tokens)

    matched_counts, matched_examples = [], []

    for text in vendor_texts:
        matched = [r for r in requirements if req_matches_text(r, text)]
        matched_counts.append(len(matched))
        matched_examples.append(", ".join(matched[:3]))

    vendor_df["Matched_Count"] = matched_counts
    vendor_df["Total_Req"] = total_requirements
    vendor_df["Match %"] = (vendor_df["Matched_Count"] / vendor_df["Total_Req"]) * 100
    vendor_df["Summary"] = vendor_df.apply(
        lambda x: f"Matched {x['Matched_Count']}/{x['Total_Req']} ({x['Match %']:.1f}%) - e.g. {x['Summary'] if 'Summary' in x else matched_examples[vendor_df.index.get_loc(x.name)]}",
        axis=1
    )

    # --- Filter & show results ---
    shortlist = vendor_df[vendor_df["Match %"] >= threshold].copy()
    shortlist = shortlist.sort_values(by="Match %", ascending=False)
    st.write("### 🏆 Shortlist Results")
    st.dataframe(shortlist[[vendor_name_col, "Match %", "Matched_Count", "Total_Req"]].reset_index(drop=True))

    # --- Download CSV ---
    csv = shortlist.to_csv(index=False).encode('utf-8')
    st.download_button(
        "💾 Download Shortlist CSV",
        csv,
        "Shortlist_Results.csv",
        "text/csv",
        key='download-csv'
    )

else:
    st.info("👆 Upload both files above to begin.")
