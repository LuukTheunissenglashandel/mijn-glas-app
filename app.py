import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & STYLING ---
st.set_page_config(layout="wide", page_title="Glas Voorraad")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Maak alle knoppen consistent */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        height: 3em;
    }
    
    /* Specifieke kleur voor de rode knoppen */
    div.stButton > button[key^="delete_btn"], 
    div.stButton > button[key^="confirm_delete"],
    div.stButton > button[key="logout_btn"] {
        background-color: #ff4b4b;
        color: white;
    }
    
    /* Verwijder witruimte bij widgets */
    .stSelectbox label { display:none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE & DATA FUNCTIES ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def laad_data():
    res = get_supabase().table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
    df["Selecteren"] = False
    return df

# --- 3. AUTHENTICATIE (Persistent via URL) ---
if "ingelogd" not in st.session_state:
    if st.query_params.get("auth") == "true":
        st.session_state.ingelogd = True
    else:
        st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    _, col2, _ = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.query_params["auth"] = "true"
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    st.stop()

# --- 4. DATA LADEN ---
if 'mijn_data' not in st.session_state: 
    st.session_state.mijn_data = laad_data()
df = st.session_state.mijn_data

# --- 5. DASHBOARD TITEL & ZOEKEN ---
st.title("🏭 Glas Voorraad Dashboard")

if "zoek_query" not in st.session_state:
    st.session_state.zoek_query = ""

c1, c2, c3 = st.columns([6, 1, 1])
with c1:
    zoekterm_input = st.text_input("Zoeken", value=st.session_state.zoek_query, placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed")
with c2:
    if st.button("ZOEKEN", use_container_width=True):
        st.session_state.zoek_query = zoekterm_input
        st.rerun()
with c3:
    if st.button("WISSEN", use_container_width=True):
        st.session_state.zoek_query = ""
        st.rerun()

view_df = df.copy()
if st.session_state.zoek_query:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_query, case=False)).any(axis=1)
    view_df = view_df[mask]

actie_placeholder = st.empty()

# --- 6. TABEL ---
edited_df = st.data_editor(
    view_df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]],
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Kies", width="small"),
        "id": None,
        "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
        "breedte": st.column_config.NumberColumn("Br.", width="small"),
        "hoogte": st.column_config.NumberColumn("Hg.", width="small"),
    },
    hide_index=True, use_container_width=True, key="editor", height=500
)

# --- 7. ACTIEBALK (Verplaatsen / Verwijderen) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]
if not geselecteerd.empty:
    with actie_placeholder.container(border=True):
        col_info, col_sel, col_b1, col_b2 = st.columns([1.5, 1.5, 2.5, 2.5], vertical_alignment="center")
        with col_info: st.markdown(f"**{len(geselecteerd)} items gekozen**")
        with col_sel: nieuwe_loc = st.selectbox("Naar:", LOCATIE_OPTIES, key="bulk_loc")
        with col_b1:
            if st.button(f"📍 VERPLAATS NAAR {nieuwe_loc}", type="primary", use_container_width=True):
                get_supabase().table("glas_voorraad").update({"locatie": nieuwe_loc}).in_("id", geselecteerd["id"].tolist()).execute()
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
        with col_b2:
            if f"confirm_delete" not in st.session_state: st.session_state.confirm_delete = False
            if not st.session_state.confirm_delete:
                if st.button(f"🗑️ MEEGENOMEN / WISSEN", key="delete_btn", use_container_width=True):
                    st.session_state.confirm_delete = True; st.rerun()
            else:
                st.warning("Zeker weten?")
                c_yes, c_no = st.columns(2)
                if c_yes.button("JA, VERWIJDER", key="confirm_delete_yes", use_container_width=True):
                    get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
                    st.session_state.confirm_delete = False; st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                if c_no.button("ANNULEER", use_container_width=True):
                    st.session_state.confirm_delete = False; st.rerun()

# --- 8. BEHEER SECTIE (Onder de tabel) ---
st.divider()
st.subheader("⚙️ Beheer & Toevoegen")
exp_col1, exp_col2 = st.columns(2)

with exp_col1:
    with st.expander("➕ Nieuwe Ruit Handmatig Toevoegen", expanded=False):
        with st.form("handmatige_toevoeging", clear_on_submit=True):
            n_loc = st.selectbox("Locatie", LOCATIE_OPTIES)
            n_order = st.text_input("Ordernummer")
            n_aantal = st.number_input("Aantal", min_value=1, value=1)
            n_br = st.number_input("Breedte (mm)", min_value=0)
            n_hg = st.number_input("Hoogte (mm)", min_value=0)
            n_oms = st.text_input("Omschrijving")
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                if n_order:
                    nieuwe_data = {"locatie": n_loc, "order_nummer": n_order, "aantal": n_aantal, "breedte": n_br, "hoogte": n_hg, "omschrijving": n_oms, "uit_voorraad": "Nee"}
                    get_supabase().table("glas_voorraad").insert(nieuwe_data).execute()
                    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                else: st.error("Ordernummer is verplicht!")

with exp_col2:
    with st.expander("📥 Excel Import", expanded=False):
        uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
        if uploaded_file and st.button("UPLOADEN", use_container_width=True):
            try:
                raw = pd.read_excel(uploaded_file)
                raw.columns = [str(c).strip().lower() for c in raw.columns]
                mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
                raw = raw.rename(columns=mapping)
                import_df = raw.dropna(subset=["order_nummer"])
                import_df["uit_voorraad"] = "Nee"
                data_dict = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")
                get_supabase().table("glas_voorraad").insert(data_dict).execute()
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")

# Knoppen voor Verversen en Uitloggen onderaan
footer_col1, footer_col2, footer_col3 = st.columns([2, 4, 2])
with footer_col1:
    if st.button("🔄 DATA VERVERSEN", use_container_width=True):
        st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
with footer_col3:
    if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
        st.session_state.ingelogd = False
        st.query_params.clear()
        st.rerun()

# --- 9. HANDMATIGE WIJZIGINGEN OPSLAAN ---
if not edited_df.drop(columns=["Selecteren"]).equals(view_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]):
    for i in range(len(edited_df)):
        orig_row = view_df[view_df["id"] == edited_df.iloc[i]["id"]].iloc[0]
        curr_row = edited_df.iloc[i]
        if not curr_row.drop("Selecteren").equals(orig_row[curr_row.drop("Selecteren").index]):
            update_data = {"locatie": str(curr_row["locatie"]), "aantal": int(curr_row["aantal"]), "breedte": int(curr_row["breedte"]), "hoogte": int(curr_row["hoogte"]), "omschrijving": str(curr_row["omschrijving"]), "order_nummer": str(curr_row["order_nummer"])}
            get_supabase().table("glas_voorraad").update(update_data).eq("id", curr_row["id"]).execute()
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
