import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- 2. INITIALISATIE ---
if "ingelogd" not in st.session_state: 
    st.session_state.ingelogd = False
if "zoek_input" not in st.session_state: 
    st.session_state.zoek_input = ""

# --- 3. CSS: HET MOOIE DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    div[data-testid="stMetric"] { background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCTIES ---
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

# --- 5. AUTH ---
if not st.session_state.ingelogd:
    st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- 6. HEADER & KPI'S ---
df_master = st.session_state.mijn_data
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df_master["Aantal"].astype(float).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", int(tot))
with c3: 
    st.metric("Unieke Orders", df_master["Order"].nunique())

# --- 7. ACTIEBALK (ZOEKEN) ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
with c1: 
    zoekterm = st.text_input("Zoeken", placeholder="Zoek op order, maat of locatie...", value=st.session_state.zoek_input)
with c2: 
    st.button("🔍", use_container_width=True)
with c3: 
    if st.button("❌", use_container_width=True):
        st.session_state.zoek_input = ""
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- 8. FILTEREN & WEERGAVE ---
df_view = df_master.copy()
if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# Tabel tonen (Alleen kijken, geen vinkjes = GEEN BUGS)
st.dataframe(df_view.drop(columns=["ID"]), hide_index=True, use_container_width=True, height=400)

# --- 9. VERWIJDER MODULE (VEILIGSTE METHODE) ---
st.markdown("---")
st.subheader("📦 Uit voorraad melden")

if not df_view.empty:
    # Maak een lijst van ruiten die de gebruiker NU ziet
    opties = {}
    for i, row in df_view.iterrows():
        label = f"ORDER: {row['Order']} | MAAT: {row['Breedte']}x{row['Hoogte']} | LOC: {row['Locatie']}"
        opties[label] = row["ID"]

    # De gebruiker kiest hier specifiek welke ruit weg moet
    gekozen = st.selectbox("Selecteer de ruit die uit voorraad moet:", ["-- Maak een keuze --"] + list(opties.keys()))
    
    if gekozen != "-- Maak een keuze --":
        if st.button(f"🗑️ Verwijder {gekozen}", type="primary", use_container_width=True):
            id_weg = opties[gekozen]
            # Verwijder alleen dit specifieke ID uit de master lijst
            st.session_state.mijn_data = df_master[df_master["ID"] != id_weg]
            sla_op(st.session_state.mijn_data)
            st.success(f"✅ Regel succesvol verwijderd!")
            time.sleep(1)
            st.rerun()
else:
    st.info("Geen ruiten gevonden om te verwijderen.")

# --- 10. SIDEBAR IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    up = st.file_uploader("Bestand", type=["xlsx"])
    if up and st.button("Uploaden"):
        try:
            new = pd.read_excel(up).astype(str)
            new["ID"] = [str(uuid.uuid4()) for _ in range(len(new))]
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, new], ignore_index=True)
            sla_op(st.session_state.mijn_data)
            st.success("Data toegevoegd")
            st.rerun()
        except Exception as e:
            st.error(f"Fout: {e}")
