# app.py
# --- Booking System Shortlist Tool (Streamlit Version) ---
# Added per-vendor matched/unmet requirement lists and overall requirement coverage summary.

import pandas as pd
import streamlit as st
from io import StringIO

# --- Page setup ---
st.set_page_config(page_title="Booking System Shortlist Tool", layout="wide")
st.title("🧩 Booking System Shortlist Tool")
st.write(
    "Upload your **vendor list** and **requirements checklist** CSV files. "
    "The app will compare them and generate a ranked shortlist. "
    "New: view which specific requirements were met / not met per vendor and overall coverage."
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

# --- Simple token-match function (existing behavior) ---
def req_matches_text(req_lower, text_lower):
    tokens = [t for t in req_lower.replace("/", " ").replace("-", " ").split() if len(t) >= 3]
    return any(tok in text_lower for tok in tokens)

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

    # --- Filter requirements if there's a 'required' column ---
    if req_required_col:
        def is_required(val):
            s = str(val).strip().lower()
            return s in ("yes", "y", "true", "1", "required", "must")
        req_df = req_df[req_df[req_required_col].apply(is_required)]

    # Keep original requirement titles for display, but also prepare lower-cased values for matching
    requirements_original = req_df[req_title_col].dropna().astype(str).tolist()
    req_pairs = [(orig, orig.lower()) for orig in requirements_original]
    total_requirements = len(req_pairs)
    st.write(f"Total requirements evaluated: **{total_requirements}**")

    # --- Normalize vendor text for matching ---
    vendor_df = vendor_df.fillna("").astype(str)
    vendor_df_lower = vendor_df.applymap(lambda x: x.lower())

    def vendor_text(row):
        return " ".join(row.values)

    vendor_texts = vendor_df_lower.apply(vendor_text, axis=1)  # series of lower-cased concatenated text

    # --- Matching logic: compute matched/unmet lists per vendor ---
    matched_counts = []
    matched_lists = []
    unmet_lists = []

    for text_lower in vendor_texts:
        matched = [orig for orig, req_lower in req_pairs if req_matches_text(req_lower, text_lower)]
        matched_set = set(matched)
        unmet = [orig for orig, _ in req_pairs if orig not in matched_set]
        matched_counts.append(len(matched))
        matched_lists.append(matched)
        unmet_lists.append(unmet)

    # --- Attach results to vendor_df ---
    vendor_df = vendor_df.reset_index(drop=True)
    vendor_df["Matched_Count"] = matched_counts
    vendor_df["Total_Req"] = total_requirements
    vendor_df["Match %"] = (vendor_df["Matched_Count"] / vendor_df["Total_Req"]) * 100
    # Store lists as actual lists (useful in-app). Also create safe string columns for CSV export.
    vendor_df["Matched_List"] = matched_lists
    vendor_df["Unmet_List"] = unmet_lists
    vendor_df["Matched_List_Str"] = ["; ".join(lst) if lst else "" for lst in matched_lists]
    vendor_df["Unmet_List_Str"] = ["; ".join(lst) if lst else "" for lst in unmet_lists]
    vendor_df["Summary"] = vendor_df.apply(
        lambda x: f"Matched {int(x['Matched_Count'])}/{int(x['Total_Req'])} ({x['Match %']:.1f}%) - e.g. {', '.join(x['Matched_List'][:3]) if x['Matched_List'] else 'None'}",
        axis=1
    )

    # --- Filter & show shortlist ---
    shortlist = vendor_df[vendor_df["Match %"] >= threshold].copy()
    shortlist = shortlist.sort_values(by="Match %", ascending=False)
    st.write("### 🏆 Shortlist Results")
    st.dataframe(shortlist[[vendor_name_col, "Match %", "Matched_Count", "Total_Req", "Summary"]].reset_index(drop=True))

    # --- Optional: show per-vendor detailed matched/unmet lists (expanders) ---
    if st.checkbox("Show per-vendor requirement details for shortlist"):
        st.write("Expand a vendor to see exact matched and unmet requirements.")
        for _, row in shortlist.iterrows():
            name = row[vendor_name_col] if vendor_name_col in row else f"Vendor {row.name}"
            with st.expander(f"{name} — {row['Match %']:.1f}% ({int(row['Matched_Count'])}/{int(row['Total_Req'])})"):
                st.write("Matched requirements:")
                if row["Matched_List"]:
                    for m in row["Matched_List"]:
                        st.write(f"- {m}")
                else:
                    st.write("- None")

                st.write("Not met requirements:")
                if row["Unmet_List"]:
                    for m in row["Unmet_List"]:
                        st.write(f"- {m}")
                else:
                    st.write("- None")

    # --- Overall requirement coverage (how many vendors meet each requirement) ---
    req_coverage = []
    total_vendors = len(vendor_df)
    for orig, req_lower in req_pairs:
        # count vendors (across all uploaded vendors) that match this requirement
        count = sum(1 for text_lower in vendor_texts if req_matches_text(req_lower, text_lower))
        pct = 0 if total_vendors == 0 else round((count / total_vendors) * 100, 1)
        req_coverage.append({"Requirement": orig, "Met_By_Count": count, "Met_By_%": pct})

    req_summary_df = pd.DataFrame(req_coverage).sort_values(by="Met_By_%", ascending=False).reset_index(drop=True)
    st.write("### 📊 Requirement Coverage Across All Vendors")
    st.dataframe(req_summary_df)

    # --- Download CSVs: shortlist and requirement coverage ---
    csv_shortlist = shortlist.drop(columns=["Matched_List", "Unmet_List"]).to_csv(index=False).encode('utf-8')
    st.download_button(
        "💾 Download Shortlist CSV (includes Matched_List_Str / Unmet_List_Str)",
        csv_shortlist,
        "Shortlist_Results.csv",
        "text/csv",
        key='download-shortlist-csv'
    )

    csv_req_cov = req_summary_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "💾 Download Requirement Coverage CSV",
        csv_req_cov,
        "Requirement_Coverage.csv",
        "text/csv",
        key='download-reqcov-csv'
    )

else:
    st.info("👆 Upload both files above to begin.")
