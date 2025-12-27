import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

# --- 2. CSS (VOOR DE LAYOUT) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* We maken de standaard buttons neutraal en herkenbaar */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE & DATA FUNCTIES ---
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

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    _, col2, _ = st.columns([1,2,1])
    with col2:
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
    if uploaded_file and st.button("UPLOADEN", use_container_width=True):
        raw = pd.read_excel(uploaded_file)
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
        raw = raw.rename(columns=mapping)
        import_df = raw.dropna(subset=["order_nummer"])
        import_df["uit_voorraad"] = "Nee"
        data_dict = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")
        get_supabase().table("glas_voorraad").insert(data_dict).execute()
        st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
    
    if st.button("🔄 VERVERSEN", use_container_width=True):
        st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 7. DASHBOARD ---
st.title("🏭 Glas Voorraad Dashboard")
active_df = df[df["uit_voorraad"] == "Nee"]
c1, c2 = st.columns(2)
c1.metric("In Voorraad", len(active_df))
c2.metric("Orders", active_df["order_nummer"].nunique())

zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed")
actie_placeholder = st.empty()

view_df = df.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 8. TABEL ---
edited_df = st.data_editor(
    view_df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]],
    column_config={"Selecteren": st.column_config.CheckboxColumn("Kies"), "id": None},
    hide_index=True, use_container_width=True, key="editor"
)

# --- 9. DE NIEUWE ACTIEBALK (GEGARANDEERDE KLEUREN) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]

if not geselecteerd.empty:
    with actie_placeholder.container():
        # We gebruiken st.info voor een gekleurde achtergrond die ALTIJD werkt
        st.markdown(f"### 🛠️ Acties voor {len(geselecteerd)} ruiten")
        
        col_sel, col_b1, col_b2 = st.columns([2, 2, 2])
        
        with col_sel:
            nieuwe_loc = st.selectbox("Nieuwe Locatie:", LOCATIE_OPTIES)
            
        with col_b1:
            # We gebruiken de 'primary' status voor kleur
            if st.button(f"📍 VERPLAATS NAAR {nieuwe_loc}", type="primary", use_container_width=True):
                get_supabase().table("glas_voorraad").update({"locatie": nieuwe_loc}).in_("id", geselecteerd["id"].tolist()).execute()
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                
        with col_b2:
            # We maken een waarschuwing en dan de knop
            if st.button(f"🗑️ MEEGENOMEN / WISSEN", use_container_width=True, help="Dit verwijdert de ruiten uit de lijst"):
                get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 10. HANDMATIGE LOCATIE WIJZIGING ---
if not edited_df.drop(columns=["Selecteren"]).equals(view_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]):
    for i in range(len(edited_df)):
        if edited_df.iloc[i]["locatie"] != view_df.iloc[i]["locatie"]:
            get_supabase().table("glas_voorraad").update({"locatie": str(edited_df.iloc[i]["locatie"])}).eq("id", edited_df.iloc[i]["id"]).execute()
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
