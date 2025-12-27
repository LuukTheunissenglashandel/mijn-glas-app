import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & STYLING ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Dashboard", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    div.stButton > button { border-radius: 8px; height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE VERBINDING (De officiële client) ---
@st.cache_resource
def get_supabase() -> Client:
    # Haalt gegevens direct uit het [supabase] blok in je secrets
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# --- 3. DATA FUNCTIES ---
@st.cache_data(ttl=60)
def laad_data():
    client = get_supabase()
    # Haal alles op uit de tabel 'glas_voorraad'
    res = client.table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
    return df

def update_rij(row_id, updates):
    client = get_supabase()
    client.table("glas_voorraad").update(updates).eq("id", row_id).execute()
    st.cache_data.clear()

def voeg_data_toe(df_nieuw):
    client = get_supabase()
    data_dict = df_nieuw.to_dict(orient="records")
    client.table("glas_voorraad").insert(data_dict).execute()
    st.cache_data.clear()

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- 5. DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- 6. SIDEBAR: EXCEL IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel bestand", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Upload naar Database", use_container_width=True):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            # Kolommen mappen (Excel -> Database)
            mapping = {
                "Locatie": "locatie", "Aantal": "aantal", 
                "Breedte": "breedte", "Hoogte": "hoogte", 
                "Order": "order_nummer", "Omschrijving": "omschrijving"
            }
            nieuwe_data = nieuwe_data.rename(columns=mapping)
            nieuwe_data["uit_voorraad"] = "Nee"
            
            # Alleen kolommen behouden die echt in de DB zitten (zonder ID, die gaat automatisch)
            cols_to_keep = ["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]
            final_upload = nieuwe_data[cols_to_keep].fillna("")
            
            voeg_data_toe(final_upload)
            st.success("✅ Succesvol toegevoegd!")
            st.session_state.mijn_data = laad_data()
            st.rerun()
        except Exception as e:
            st.error(f"Fout: {e}")
    
    st.divider()
    if st.button("🔄 Data Verversen", use_container_width=True):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- 7. DASHBOARD HEADER & KPI'S ---
st.title("🏭 Glas Voorraad Dashboard")

active_df = df[df["uit_voorraad"] == "Nee"]
k1, k2 = st.columns(2)
with k1:
    totaal = pd.to_numeric(active_df["aantal"], errors='coerce').sum()
    st.metric("In Voorraad (stuks)", int(totaal) if not pd.isna(totaal) else 0)
with k2:
    st.metric("Unieke Orders", active_df["order_nummer"].nunique())

# --- 8. ZOEKFUNCTIE ---
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed")
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 9. DATA EDITOR ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "id": None, # Verberg ID voor de gebruiker
        "uit_voorraad": st.column_config.SelectboxColumn("Op Voorraad?", options=["Ja", "Nee"], width="medium"),
        "locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aantal", disabled=True),
        "breedte": st.column_config.NumberColumn("Breedte (mm)", disabled=True),
        "hoogte": st.column_config.NumberColumn("Hoogte (mm)", disabled=True),
        "order_nummer": st.column_config.TextColumn("Order", disabled=True),
        "omschrijving": st.column_config.TextColumn("Omschrijving", width="large", disabled=True),
        "created_at": None
    },
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- 10. OPSLAAN LOGICA (Update alleen wijzigingen) ---
if not edited_df.equals(view_df):
    for i in range(len(edited_df)):
        # Check welke rij specifiek is aangepast
        if not edited_df.iloc[i].equals(view_df.iloc[i]):
            row = edited_df.iloc[i]
            updates = {
                "locatie": str(row["locatie"]),
                "uit_voorraad": str(row["uit_voorraad"])
            }
            update_rij(row["id"], updates)
    
    # Vernieuw de lokale staat en de pagina
    st.session_state.mijn_data = laad_data()
    st.rerun()
