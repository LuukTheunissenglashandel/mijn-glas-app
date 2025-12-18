import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Beheer")

WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# Initialiseer session state
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "data" not in st.session_state: st.session_state.data = pd.DataFrame()

# --- 2. FUNCTIES ---
def laad_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        return df.fillna("").astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Alleen de echte datakolommen opslaan
    save_df = df[["ID"] + DATAKOLOMMEN]
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- 3. LOGIN ---
if not st.session_state.ingelogd:
    st.title("🔒 Glas Voorraad")
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.session_state.data = laad_data()
            st.rerun()
        else:
            st.error("Fout wachtwoord")
    st.stop()

# --- 4. DATA LADEN ---
if st.session_state.data.empty:
    st.session_state.data = laad_data()

df_master = st.session_state.data

# --- 5. INTERFACE ---
st.title("🏭 Glas Voorraad")

# Zoeksectie
zoekterm = st.text_input("🔍 Zoeken", placeholder="Typ ordernummer, maat of locatie...")

# Filter de data voor weergave
df_view = df_master.copy()
if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# Toon de tabel (Puur weergave, dit kan niet crashen)
st.dataframe(
    df_view.drop(columns=["ID"]), 
    hide_index=True, 
    use_container_width=True,
    height=400
)

# --- 6. HET UIT VOORRAAD MELDEN (DE FIX) ---
st.markdown("---")
st.subheader("📦 Uit voorraad melden")

if not df_view.empty:
    # Maak een lijst van ruiten die de gebruiker nu ziet
    # We maken een tekstlabel zodat de gebruiker weet wat hij kiest
    opties = {}
    for _, row in df_view.iterrows():
        label = f"Order: {row['Order']} | Maat: {row['Breedte']}x{row['Hoogte']} | Locatie: {row['Locatie']}"
        opties[label] = row["ID"]

    selected_label = st.selectbox(
        "Welke ruit moet uit de voorraad?",
        options=["-- Maak een keuze --"] + list(opties.keys()),
        help="Alleen ruiten uit je zoekresultaat worden hier getoond."
    )

    if selected_label != "-- Maak een keuze --":
        ruit_id = opties[selected_label]
        
        if st.button("✅ Bevestig: Verwijder uit voorraad", type="primary"):
            # Verwijder de ruit op basis van het unieke ID uit de hoofdlijst
            nieuwe_data = df_master[df_master["ID"] != ruit_id].copy()
            
            # Opslaan en sessie bijwerken
            st.session_state.data = nieuwe_data
            sla_op(nieuwe_data)
            
            st.success(f"Verwijderd: {selected_label}")
            time.sleep(1)
            st.rerun()
else:
    st.info("Geen ruiten gevonden om te selecteren.")

# --- 7. TOEVOEGEN ---
with st.expander("➕ Nieuwe voorraad toevoegen"):
    up = st.file_uploader("Upload Excel", type=["xlsx"])
    if up and st.button("Excel Verwerken"):
        nieuwe_ruiten = pd.read_excel(up).astype(str)
        nieuwe_ruiten["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_ruiten))]
        for col in DATAKOLOMMEN:
            if col not in nieuwe_ruiten.columns: nieuwe_ruiten[col] = ""
        
        updated_df = pd.concat([df_master, nieuwe_ruiten], ignore_index=True)
        st.session_state.data = updated_df
        sla_op(updated_df)
        st.success("Voorraad bijgewerkt!")
        time.sleep(1)
        st.rerun()

if st.button("🔄 Lijst volledig verversen"):
    st.session_state.data = laad_data()
    st.rerun()
