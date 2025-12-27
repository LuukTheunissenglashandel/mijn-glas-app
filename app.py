import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & STYLING ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Dashboard", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    /* Algemene UI opschonen */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Sidebar knoppen */
    section[data-testid="stSidebar"] div.stButton > button {
        background-color: #262730;
        color: white;
        border-radius: 8px;
    }

    /* DE ZWEVENDE ACTIEBALK */
    .action-container {
        background-color: white;
        padding: 15px;
        border-radius: 15px;
        border: 2px solid #007bff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        display: flex;
        align-items: center;
    }

    /* Knoppen binnen de actiebalk forceren */
    div.stButton > button {
        border-radius: 50px !important; /* Mooie ronde knoppen zoals op je tekening */
        height: 45px;
        font-weight: 700;
        border: none;
    }

    /* BLAUWE VERPLAATS KNOP */
    div.stButton > button[key^="bulk_update"] {
        background-color: #007bff !important;
        color: white !important;
    }

    /* RODE MEEGENOMEN KNOP */
    div.stButton > button[key^="bulk_delete"] {
        background-color: #e63946 !important;
        color: white !important;
    }
    
    /* Forceer witte tekst in buttons */
    div.stButton > button p { color: white !important; }

    /* KPI styling */
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE VERBINDING ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# --- 3. DATA FUNCTIES ---
@st.cache_data(ttl=60)
def laad_data():
    client = get_supabase()
    res = client.table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
    df["Kies"] = False
    return df

def update_bulk(ids, updates):
    get_supabase().table("glas_voorraad").update(updates).in_("id", ids).execute()
    st.cache_data.clear()

def verwijder_bulk(ids):
    get_supabase().table("glas_voorraad").delete().in_("id", ids).execute()
    st.cache_data.clear()

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    _, col2, _ = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD: st.session_state.ingelogd = True; st.rerun()
    st.stop()

# --- 5. DATA LADEN ---
if 'mijn_data' not in st.session_state: st.session_state.mijn_data = laad_data()
df = st.session_state.mijn_data

# --- 6. SIDEBAR ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 UPLOADEN", use_container_width=True):
        try:
            raw = pd.read_excel(uploaded_file)
            raw.columns = [str(c).strip().lower() for c in raw.columns]
            mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
            raw = raw.rename(columns=mapping)
            import_df = raw.dropna(subset=["order_nummer"])
            import_df["uit_voorraad"] = "Nee"
            for c in ["aantal", "breedte", "hoogte"]:
                import_df[c] = pd.to_numeric(import_df[c], errors='coerce').fillna(0).astype(int)
            get_supabase().table("glas_voorraad").insert(import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")).execute()
            st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    
    st.divider()
    if st.button("🔄 DATA VERVERSEN", use_container_width=True):
        st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 7. DASHBOARD & ZOEKFUNCTIE ---
st.title("🏭 Glas Voorraad Dashboard")
active_df = df[df["uit_voorraad"] == "Nee"]
c1, c2 = st.columns(2)
with c1: st.metric("In Voorraad (stuks)", int(pd.to_numeric(active_df["aantal"], errors='coerce').sum()))
with c2: st.metric("Unieke Orders", active_df["order_nummer"].nunique())

zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed")
actie_placeholder = st.empty()

view_df = df.copy()
if zoekterm:
    mask = view_df.drop(columns=["Kies"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 8. TABEL EDITOR ---
view_df = view_df[["Kies", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]
edited_df = st.data_editor(
    view_df,
    column_config={
        "Kies": st.column_config.CheckboxColumn("", width="small"),
        "id": None, 
        "locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aantal", disabled=True),
        "breedte": st.column_config.NumberColumn("Breedte", disabled=True),
        "hoogte": st.column_config.NumberColumn("Hoogte", disabled=True),
    },
    hide_index=True, use_container_width=True, height=500, key="main_editor"
)

# --- 9. DE ZWEVENDE ACTIEBALK LOGICA ---
geselecteerd = edited_df[edited_df["Kies"] == True]

if not geselecteerd.empty:
    with actie_placeholder.container():
        st.markdown(f'<div class="action-container">', unsafe_allow_html=True)
        col_t, col_s, col_b1, col_b2 = st.columns([1, 1.5, 2, 2])
        with col_t:
            st.markdown(f"**{len(geselecteerd)} gekozen**")
        with col_s:
            nieuwe_loc = st.selectbox("Naar:", LOCATIE_OPTIES, key="bulk_loc", label_visibility="collapsed")
        with col_b1:
            if st.button(f"📍 VERPLAATS NAAR {nieuwe_loc}", key="bulk_update_btn", use_container_width=True):
                update_bulk(geselecteerd["id"].tolist(), {"locatie": nieuwe_loc})
                st.session_state.mijn_data = laad_data(); st.rerun()
        with col_b2:
            if st.button(f"🗑️ MEEGENOMEN / WISSEN", key="bulk_delete_btn", use_container_width=True):
                verwijder_bulk(geselecteerd["id"].tolist())
                st.session_state.mijn_data = laad_data(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 10. HANDMATIGE LOCATIE WIJZIGING ---
if not edited_df.drop(columns=["Kies"]).equals(view_df.drop(columns=["Kies"])):
    for i in range(len(edited_df)):
        if edited_df.iloc[i]["locatie"] != view_df.iloc[i]["locatie"]:
            get_supabase().table("glas_voorraad").update({"locatie": str(edited_df.iloc[i]["locatie"])}).eq("id", edited_df.iloc[i]["id"]).execute()
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
