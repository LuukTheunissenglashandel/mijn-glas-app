import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

# We gebruiken een TTL van 300 seconden (5 min) om de API rust te geven.
# Alleen bij een handmatige refresh of opstart halen we nieuwe data.
@st.cache_data(ttl=300)
def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1")
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        
        # Basis opschoning
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        
        # Zorg dat alle kolommen bestaan en tekst zijn
        for col in DATAKOLOMMEN:
            if col not in df.columns: df[col] = ""
        
        return df[["ID"] + DATAKOLOMMEN].astype(str)
    except Exception as e:
        st.error(f"Fout bij laden: {e}")
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_data_op(df):
    conn = get_connection()
    try:
        # Schrijf naar Google Sheets
        conn.update(worksheet="Blad1", data=df)
        # We updaten ALLEEN de session_state, we wissen de cache NIET 
        # om te voorkomen dat er direct weer een 'Read' verzoek wordt gedaan.
        st.session_state.mijn_data = df
        st.success("Opgeslagen!")
    except Exception as e:
        if "429" in str(e):
            st.error("Google is even overbelast. Wacht 10 seconden en probeer het opnieuw.")
        else:
            st.error(f"Fout bij opslaan: {e}")

# --- INITIALISATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    # (Inlogscherm weggelaten voor de leesbaarheid, blijft gelijk aan jouw code)
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

# Belangrijk: Laad de data één keer in de sessie
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- INTERFACE ---
st.title("🏭 Glas Voorraad")

# Handmatige verversknop (om de cache te omzeilen als dat echt nodig is)
if st.sidebar.button("🔄 Forceer Vernieuwen"):
    st.cache_data.clear()
    st.session_state.mijn_data = laad_data_van_cloud()
    st.rerun()

# Tabel tonen
view_df = st.session_state.mijn_data.copy()
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

edited_df = st.data_editor(
    view_df,
    column_config={
        "Locatie": st.column_config.TextColumn("Locatie", width="medium"),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad", width="small"),
        "ID": None, "Uit voorraad": None 
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    key="editor"
)

# --- VERWERKING (Zonder st.rerun indien mogelijk) ---
if not edited_df.equals(view_df):
    # Synchroniseer de status
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Maak een kopie van de huidige data en update deze
    nieuwe_dataset = st.session_state.mijn_data.copy()
    
    for _, row in edited_df.iterrows():
        # Zoek rij op basis van ID en update Locatie + Voorraad
        mask = nieuwe_dataset['ID'] == row['ID']
        nieuwe_dataset.loc[mask, "Locatie"] = row["Locatie"]
        nieuwe_dataset.loc[mask, "Uit voorraad"] = row["Uit voorraad"]

    # Opslaan
    sla_data_op(nieuwe_dataset)
    # Geen st.rerun() hier! Streamlit onthoudt de staat van de editor al.
