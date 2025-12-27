import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

# --- 2. CSS (GEGARANDEERDE KLEUREN & STIJL) ---
st.markdown("""
    <style>
    /* Algemene layout */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* ACTIEBALK CONTAINER */
    .action-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 25px;
    }

    /* KNOP STYLING */
    div.stButton > button {
        border-radius: 50px !important; /* Pilvormig */
        height: 48px !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        text-transform: uppercase;
        border: none !important;
        color: white !important;
        transition: transform 0.1s ease;
    }
    
    div.stButton > button:active { transform: scale(0.98); }

    /* Forceer witte tekst voor alle browsers */
    div.stButton > button p { color: white !important; }

    /* BLAUWE VERPLAATS KNOP */
    div.stButton > button[key="verplaats_actie_btn"] {
        background-color: #007bff !important;
    }

    /* RODE MEEGENOMEN KNOP */
    div.stButton > button[key="wissen_actie_btn"] {
        background-color: #e63946 !important;
    }

    /* ZWARTE KNOPPEN (Sidebar & Login) */
    div.stButton > button[key^="black_btn"] {
        background-color: #262730 !important;
    }

    /* Tabel styling */
    [data-testid="stDataEditor"] { border-radius: 10px; overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE CONNECTIE ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# --- 4. DATA FUNCTIES ---
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

# --- 5. LOGIN ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    _, col2, _ = st.columns([1,1.5,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Inloggen</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed", placeholder="Wachtwoord...")
        if st.button("INLOGGEN", use_container_width=True, key="black_btn_login"):
            if ww == WACHTWOORD: st.session_state.ingelogd = True; st.rerun()
    st.stop()

# --- 6. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state: st.session_state.mijn_data = laad_data()
df = st.session_state.mijn_data

# --- 7. SIDEBAR (IMPORT) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 UPLOADEN", use_container_width=True, key="black_btn_up"):
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
    if st.button("🔄 VERVERSEN", use_container_width=True, key="black_btn_ref"):
        st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 8. DASHBOARD KPI'S ---
st.title("🏭 Glas Voorraad Dashboard")
active_df = df[df["uit_voorraad"] == "Nee"]
c1, c2 = st.columns(2)
with c1: st.metric("In Voorraad (stuks)", int(pd.to_numeric(active_df["aantal"], errors='coerce').sum()))
with c2: st.metric("Unieke Orders", active_df["order_nummer"].nunique())

# --- 9. ZOEKBALK & ACTIE BALK ---
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed")
actie_placeholder = st.empty()

view_df = df.copy()
if zoekterm:
    mask = view_df.drop(columns=["Kies"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 10. DATA EDITOR ---
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
    hide_index=True, use_container_width=True, height=500, key="editor"
)

# --- 11. DE ACTIEBALK LOGICA ---
geselecteerd = edited_df[edited_df["Kies"] == True]

if not geselecteerd.empty:
    with actie_placeholder.container():
        st.markdown('<div class="action-card">', unsafe_allow_html=True)
        col_t, col_s, col_b1, col_b2 = st.columns([1, 1.5, 2, 2])
        with col_t:
            st.write("") # Uitlijning
            st.markdown(f"**{len(geselecteerd)} gekozen**")
        with col_s:
            nieuwe_loc = st.selectbox("Naar:", LOCATIE_OPTIES, key="bulk_loc_val", label_visibility="collapsed")
        with col_b1:
            if st.button(f"📍 VERPLAATS NAAR {nieuwe_loc}", key="verplaats_actie_btn", use_container_width=True):
                update_bulk(geselecteerd["id"].tolist(), {"locatie": nieuwe_loc})
                st.session_state.mijn_data = laad_data(); st.rerun()
        with col_b2:
            if st.button(f"🗑️ MEEGENOMEN / WISSEN", key="wissen_actie_btn", use_container_width=True):
                verwijder_bulk(geselecteerd["id"].tolist())
                st.session_state.mijn_data = laad_data(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 12. HANDMATIGE WIJZIGING ---
if not edited_df.drop(columns=["Kies"]).equals(view_df.drop(columns=["Kies"])):
    for i in range(len(edited_df)):
        if edited_df.iloc[i]["locatie"] != view_df.iloc[i]["locatie"]:
            get_supabase().table("glas_voorraad").update({"locatie": str(edited_df.iloc[i]["locatie"])}).eq("id", edited_df.iloc[i]["id"]).execute()
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
