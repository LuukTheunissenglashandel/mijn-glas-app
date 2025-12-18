import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Beheer")
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "data" not in st.session_state: st.session_state.data = pd.DataFrame()

# --- 2. FUNCTIES ---
def laad_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        # Forceer unieke ID's als ze ontbreken
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        return df.fillna("").astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Alleen de echte data opslaan, geen hulp-kolommen
    save_df = df[["ID"] + DATAKOLOMMEN]
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- 3. LOGIN ---
if not st.session_state.ingelogd:
    st.title("🔒 Login")
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.session_state.data = laad_data()
            st.rerun()
    st.stop()

# --- 4. DATA LADEN ---
if st.session_state.data.empty:
    st.session_state.data = laad_data()

# Master dataset in geheugen
df_master = st.session_state.data

# --- 5. INTERFACE ---
st.title("🏭 Glas Voorraad")

# Zoekveld
zoekterm = st.text_input("🔍 Zoeken", placeholder="Typ order, maat of locatie...")

# Filteren voor de weergave
df_view = df_master.copy()
if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# TABEL: Alleen om te kijken (geen vinkjes, dus geen fouten mogelijk)
st.dataframe(df_view.drop(columns=["ID"]), hide_index=True, use_container_width=True)

# --- 6. HET VERWIJDEREN (DE WATERDICHTE METHODE) ---
st.markdown("---")
st.subheader("📦 Uit voorraad melden")

if not df_view.empty:
    # We maken een keuzelijst van ruiten die de gebruiker NU ziet
    # We gebruiken de kolom-data om een uniek label te maken
    keuzes = {}
    for _, row in df_view.iterrows():
        label = f"ORDER: {row['Order']} | MAAT: {row['Breedte']}x{row['Hoogte']} | LOC: {row['Locatie']}"
        keuzes[label] = row["ID"]

    # De gebruiker moet de ruit expliciet selecteren in dit menu
    geselecteerd_label = st.selectbox(
        "Welke specifieke ruit uit bovenstaande tabel wil je verwijderen?",
        options=["-- Maak een keuze --"] + list(keuzes.keys())
    )

    if geselecteerd_label != "-- Maak een keuze --":
        ruit_id = keuzes[geselecteerd_label]
        
        st.warning(f"Je hebt geselecteerd: **{geselecteerd_label}**")
        
        # De knop voert de verwijdering uit op basis van het unieke ID
        if st.button("🔴 VERWIJDER DEZE RUIT DEFINITIEF", type="primary"):
            # We filteren de master dataset: behoud alles BEHALVE dit specifieke ID
            nieuwe_master = df_master[df_master["ID"] != ruit_id].copy()
            
            # Opslaan en sessie bijwerken
            st.session_state.data = nieuwe_master
            sla_op(nieuwe_master)
            
            st.success("Ruit is succesvol uit de voorraad verwijderd!")
            time.sleep(1)
            st.rerun()
else:
    st.info("Geen ruiten gevonden om te selecteren.")

# --- 7. EXTRA OPTIES ---
with st.expander("➕ Nieuwe ruiten toevoegen"):
    up = st.file_uploader("Kies Excel", type=["xlsx"])
    if up and st.button("Verwerk Excel"):
        nieuwe_ruiten = pd.read_excel(up).astype(str)
        nieuwe_ruiten["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_ruiten))]
        for col in DATAKOLOMMEN:
            if col not in nieuwe_ruiten.columns: nieuwe_ruiten[col] = ""
        
        st.session_state.data = pd.concat([df_master, nieuwe_ruiten], ignore_index=True)
        sla_op(st.session_state.data)
        st.success("Succesvol toegevoegd!")
        time.sleep(1)
        st.rerun()

if st.button("🔄 Volledige lijst herladen"):
    st.session_state.data = laad_data()
    st.rerun()
