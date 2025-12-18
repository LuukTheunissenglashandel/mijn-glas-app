import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
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
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        return df.fillna("").astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
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

# --- 5. INTERFACE ---
st.title("🏭 Glas Voorraad")

zoekterm = st.text_input("🔍 Zoeken", placeholder="Zoek op order, maat of locatie...")

# Filteren voor weergave
df_view = st.session_state.data.copy()
if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# Toon de tabel (Alleen lezen om bugs te voorkomen)
st.dataframe(df_view.drop(columns=["ID"]), hide_index=True, use_container_width=True)

# --- 6. HET VERWIJDEREN (DE VEILIGE METHODE) ---
st.markdown("---")
st.subheader("🗑️ Uit voorraad melden")

if not df_view.empty:
    # We maken een lijst met alleen de ruiten die je nu op je scherm ziet
    keuzes = {}
    for _, row in df_view.iterrows():
        label = f"ORDER: {row['Order']} | MAAT: {row['Breedte']}x{row['Hoogte']} | LOC: {row['Locatie']}"
        keuzes[label] = row["ID"]

    # De gebruiker moet hier echt een keuze maken uit de lijst
    geselecteerd_label = st.selectbox(
        "Welke specifieke ruit wil je uit voorraad melden?",
        options=["-- Kies een ruit --"] + list(keuzes.keys())
    )

    if geselecteerd_label != "-- Kies een ruit --":
        ruit_id = keuzes[geselecteerd_label]
        
        st.warning(f"Je staat op het punt om te verwijderen: **{geselecteerd_label}**")
        
        if st.button("🔴 BEVESTIG: MELD UIT VOORRAAD", type="primary"):
            # Verwijder EXACT dit ID uit de hoofdlijst
            st.session_state.data = st.session_state.data[st.session_state.data["ID"] != ruit_id]
            sla_op(st.session_state.data)
            
            st.success("Ruit succesvol verwijderd!")
            time.sleep(1)
            st.rerun()
else:
    st.info("Geen ruiten gevonden om te verwijderen.")

# --- 7. EXTRA ---
if st.button("🔄 Ververs Lijst"):
    st.session_state.data = laad_data()
    st.rerun()
