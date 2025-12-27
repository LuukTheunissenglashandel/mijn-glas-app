import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

# --- 2. CSS STYLING ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    div.stButton > button { border-radius: 8px; height: 50px; font-weight: 600; }
    [data-testid="stDataEditor"] { border: 1px solid #e0e0e0; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE FUNCTIES ---
def get_supabase():
    return st.connection("supabase", type=SupabaseConnection)

@st.cache_data(ttl=60) # Buffer data voor 60 seconden voor snelheid
def laad_data():
    supabase = get_supabase()
    res = supabase.table("glas_voorraad").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def update_rij(row_id, updates):
    supabase = get_supabase()
    supabase.table("glas_voorraad").update(updates).eq("id", row_id).execute()
    st.cache_data.clear()

def voeg_data_toe(df_nieuw):
    supabase = get_supabase()
    data_dict = df_nieuw.to_dict(orient="records")
    supabase.table("glas_voorraad").insert(data_dict).execute()
    st.cache_data.clear()

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.subheader("🔒 Inloggen")
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    st.stop()

# --- 5. DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- 6. SIDEBAR: IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel bestand", type=["xlsx"])
    if uploaded_file and st.button("📤 Upload naar Database", use_container_width=True):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            mapping = {
                "Locatie": "locatie", "Aantal": "aantal", 
                "Breedte": "breedte", "Hoogte": "hoogte", 
                "Order": "order_nummer", "Omschrijving": "omschrijving"
            }
            nieuwe_data = nieuwe_data.rename(columns=mapping)
            nieuwe_data["uit_voorraad"] = "Nee"
            
            # Selecteer alleen de kolommen die echt in de DB zitten
            final_upload = nieuwe_data[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]]
            voeg_data_toe(final_upload)
            st.success("Succesvol toegevoegd!")
            st.session_state.mijn_data = laad_data()
            st.rerun()
        except Exception as e:
            st.error(f"Fout bij uploaden: {e}")
    
    if st.button("🔄 Ververs Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- 7. KPI'S & ZOEKBALK ---
st.title("🏭 Glas Voorraad Dashboard")

# KPI's
active_df = df[df["uit_voorraad"] == "Nee"]
k1, k2 = st.columns(2)
with k1:
    totaal_stuks = pd.to_numeric(active_df["aantal"], errors='coerce').sum()
    st.metric("In Voorraad (stuks)", int(totaal_stuks))
with k2:
    st.metric("Openstaande Orders", active_df["order_nummer"].nunique())

# Zoeken
zoekterm = st.text_input("🔍 Zoeken", placeholder="Type ordernummer, locatie of maat...")
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 8. DATA EDITOR ---
# We configureren de editor zodat alleen Locatie en Status aanpasbaar zijn
edited_df = st.data_editor(
    view_df,
    column_config={
        "id": None, # Verberg ID
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
    height=500,
    key="editor"
)

# --- 9. OPSLAAN LOGICA ---
if not edited_df.equals(view_df):
    for i in range(len(edited_df)):
        # Vergelijk de rij met de originele view_df
        if not edited_df.iloc[i].equals(view_df.iloc[i]):
            row = edited_df.iloc[i]
            updates = {
                "locatie": row["locatie"],
                "uit_voorraad": row["uit_voorraad"]
            }
            update_rij(row["id"], updates)
    
    st.session_state.mijn_data = laad_data()
    st.rerun()
