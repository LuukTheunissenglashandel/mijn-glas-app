import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

# --- 2. CSS (STYLING) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Knoppen algemeen */
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; color: white; border: none; }
    
    /* Blauwe Verplaats-knop */
    button[key="verplaats_btn_key"] { background-color: #007bff !important; }
    
    /* Rode Meegenomen-knop */
    button[key="meegenomen_btn_key"] { background-color: #ff4b4b !important; }
    
    /* Grijze ververs-knop */
    button[key="ververs_btn_key"] { background-color: #6c757d !important; }

    /* Actie balk styling */
    .action-container {
        background-color: #f1f3f5;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE VERBINDING ---
@st.cache_resource
def get_supabase() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Configuratie-fout: {e}")
        st.stop()

# --- 4. DATA FUNCTIES ---
@st.cache_data(ttl=60)
def laad_data():
    client = get_supabase()
    res = client.table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
    df["Selecteren"] = False
    return df

def update_bulk(ids, updates):
    client = get_supabase()
    client.table("glas_voorraad").update(updates).in_("id", ids).execute()
    st.cache_data.clear()

def verwijder_bulk(ids):
    client = get_supabase()
    client.table("glas_voorraad").delete().in_("id", ids).execute()
    st.cache_data.clear()

# --- 5. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Inloggen</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True, key="login_btn"):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else: st.error("Onjuist")
    st.stop()

# --- 6. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- 7. SIDEBAR (IMPORT) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Upload naar Database", use_container_width=True, key="upload_btn"):
        try:
            raw = pd.read_excel(uploaded_file)
            raw.columns = [str(c).strip().lower() for c in raw.columns]
            mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
            raw = raw.rename(columns=mapping)
            import_df = raw.dropna(subset=["order_nummer"])
            import_df["uit_voorraad"] = "Nee"
            for c in ["aantal", "breedte", "hoogte"]:
                import_df[c] = pd.to_numeric(import_df[c], errors='coerce').fillna(0).astype(int)
            
            data_dict = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")
            get_supabase().table("glas_voorraad").insert(data_dict).execute()
            st.cache_data.clear()
            st.session_state.mijn_data = laad_data()
            st.success("Gelukt!")
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    
    st.divider()
    if st.button("🔄 Verversen", use_container_width=True, key="ververs_btn_key"):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- 8. DASHBOARD KPI'S ---
st.title("🏭 Glas Voorraad")
active_df = df[df["uit_voorraad"] == "Nee"]
c1, c2 = st.columns(2)
with c1: st.metric("In Voorraad", f"{int(pd.to_numeric(active_df['aantal'], errors='coerce').sum())} stuks")
with c2: st.metric("Open Orders", active_df["order_nummer"].nunique())

# --- 9. ZOEKBALK & ACTIE CONTAINER ---
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of locatie...", label_visibility="collapsed")
actie_placeholder = st.empty() # Hier komen de knoppen

# Data filteren voor weergave
view_df = df.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Kolomvolgorde
cols = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
view_df = view_df[cols]

# --- 10. TABEL EDITOR ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Kies", width="small", default=False),
        "id": None, 
        "locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aantal", disabled=True),
        "breedte": st.column_config.NumberColumn("Br.", disabled=True),
        "hoogte": st.column_config.NumberColumn("Hg.", disabled=True),
        "order_nummer": st.column_config.TextColumn("Order", disabled=True),
        "omschrijving": st.column_config.TextColumn("Omschrijving", width="large", disabled=True),
    },
    hide_index=True,
    use_container_width=True,
    height=500,
    key="editor_key"
)

# --- 11. ACTIE LOGICA (DYNAMISCHE BUTTONS) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]

if not geselecteerd.empty:
    with actie_placeholder.container():
        st.markdown('<div class="action-container">', unsafe_allow_html=True)
        col_txt, col_sel, col_btn1, col_btn2 = st.columns([1.5, 2, 2.5, 2.5])
        
        with col_txt:
            st.write(f"**{len(geselecteerd)} ruiten gekozen:**")
            
        with col_sel:
            nieuwe_loc = st.selectbox("Naar locatie:", LOCATIE_OPTIES, key="bulk_loc_choice", label_visibility="collapsed")
            
        with col_btn1:
            if st.button(f"📍 Verplaats naar {nieuwe_loc}", key="verplaats_btn_key", use_container_width=True):
                update_bulk(geselecteerd["id"].tolist(), {"locatie": nieuwe_loc})
                st.session_state.mijn_data = laad_data()
                st.rerun()
                
        with col_btn2:
            if st.button(f"🗑️ Meegenomen (Wissen)", key="meegenomen_btn_key", use_container_width=True):
                verwijder_bulk(geselecteerd["id"].tolist())
                st.session_state.mijn_data = laad_data()
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 12. HANDMATIGE INDIVIDUELE WIJZIGING (LOCATIE) ---
if not edited_df.drop(columns=["Selecteren"]).equals(view_df.drop(columns=["Selecteren"])):
    # Zoek welke specifieke rij is veranderd
    for i in range(len(edited_df)):
        if edited_df.iloc[i]["locatie"] != view_df.iloc[i]["locatie"]:
            get_supabase().table("glas_voorraad").update({"locatie": str(edited_df.iloc[i]["locatie"])}).eq("id", edited_df.iloc[i]["id"]).execute()
    st.cache_data.clear()
    st.session_state.mijn_data = laad_data()
    st.rerun()
