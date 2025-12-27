import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE & SETUP ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad Beheer", initial_sidebar_state="expanded")

# --- 2. CSS VOOR DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)  # Cache voor 10 minuten om Quota te sparen
def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        
        # Zorg voor unieke ID's en juiste kolommen
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        
        for col in DATAKOLOMMEN:
            if col not in df.columns:
                df[col] = "Nee" if col == "Uit voorraad" else ""
        
        return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_data_op(df):
    """Slaat data op naar Google Sheets en werkt de lokale staat bij."""
    conn = get_connection()
    try:
        # Update naar cloud
        conn.update(worksheet="Blad1", data=df)
        # Update lokale session state zodat we niet opnieuw hoeven te downloaden
        st.session_state.mijn_data = df
        st.toast("✅ Wijzigingen opgeslagen in Google Sheets!")
    except Exception as e:
        if "429" in str(e):
            st.error("Google Sheets is even overbelast. Wacht 10 seconden.")
        else:
            st.error(f"Fout bij opslaan: {e}")

def clear_search():
    st.session_state.zoek_input = ""

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad Inloggen</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Voer wachtwoord in...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    st.stop()

# --- 5. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 6. SIDEBAR: IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies een Excel bestand", type=["xlsx"])
    if uploaded_file and st.button("📤 Toevoegen aan voorraad"):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
            nieuwe_data["Uit voorraad"] = "Nee"
            # Zorg dat alle kolommen kloppen
            for col in DATAKOLOMMEN:
                if col not in nieuwe_data.columns: nieuwe_data[col] = ""
            
            gecombineerde_data = pd.concat([st.session_state.mijn_data, nieuwe_data[["ID"] + DATAKOLOMMEN]], ignore_index=True)
            sla_data_op(gecombineerde_data)
            st.rerun()
        except Exception as e:
            st.error(f"Import fout: {e}")
    
    st.divider()
    if st.button("🔄 Data vernieuwen uit Cloud"):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data_van_cloud()
        st.rerun()

# --- 7. HOOFDSCHERM: KPI'S & ZOEKEN ---
st.title("🏭 Glas Voorraad Systeem")

# KPI's
active_df = st.session_state.mijn_data[st.session_state.mijn_data["Uit voorraad"] == "Nee"]
k1, k2 = st.columns(2)
with k1:
    st.metric("Totaal in voorraad (items)", len(active_df))
with k2:
    unieke_orders = active_df["Order"].nunique()
    st.metric("Aantal actieve orders", unieke_orders)

# Zoekbalk
c_in, c_zo, c_wi = st.columns([7, 1, 1], gap="small", vertical_alignment="bottom")
with c_in:
    zoekterm = st.text_input("Zoeken", placeholder="Zoek op locatie, order, afmeting...", label_visibility="collapsed", key="zoek_input")
with c_zo:
    st.button("🔍", use_container_width=True)
with c_wi:
    st.button("❌", on_click=clear_search, use_container_width=True)

# --- 8. TABEL MET DATA EDITOR ---
# Voorbereiden view
view_df = st.session_state.mijn_data.copy()
if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

# Hulpmiddel voor checkbox (Streamlit data_editor heeft boolean nodig)
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

edited_df = st.data_editor(
    view_df,
    column_config={
        "Locatie": st.column_config.TextColumn("Locatie ✏️", width="medium"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad?", width="small"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="large"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "ID": None,
        "Uit voorraad": None 
    },
    # BELANGRIJK: Locatie is hier uit 'disabled', dus aanpasbaar!
    disabled=["ID", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=500,
    key="voorraad_editor"
)

# --- 9. OPSLAG LOGICA ---
if not edited_df.equals(view_df):
    # 1. Synchroniseer status
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # 2. Update de hoofd-dataset op basis van ID
    temp_df = st.session_state.mijn_data.copy()
    
    for _, row in edited_df.iterrows():
        # Zoek de specifieke rij op ID
        mask = temp_df['ID'] == row['ID']
        # Update alleen de kolommen die aangepast mogen zijn
        temp_df.loc[mask, "Locatie"] = row["Locatie"]
        temp_df.loc[mask, "Uit voorraad"] = row["Uit voorraad"]
    
    # 3. Opslaan
    sla_data_op(temp_df)
    # Geen st.rerun() nodig; de editor behoudt de staat en de toast bevestigt de actie.
