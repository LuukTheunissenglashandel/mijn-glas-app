import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(layout="wide", page_title="Glas Voorraad")
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "zoek_input" not in st.session_state: st.session_state.zoek_input = ""

# --- 2. CSS: HET MOOIE DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    div[data-testid="stMetric"] { background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCTIES ---
def laad_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        return df.fillna("").astype(str)
    except: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Blad1", data=df[["ID"] + DATAKOLOMMEN])
    st.cache_data.clear()

# --- 4. AUTH ---
if not st.session_state.ingelogd:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔒 Login")
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Start", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- 5. DASHBOARD ---
df_master = st.session_state.mijn_data
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: st.metric("Totaal Ruiten", len(df_master))
with c3: st.metric("Unieke Orders", df_master["Order"].nunique())

# --- 6. ZOEKEN ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
c1, c2 = st.columns([6, 1])
with c1: 
    zoekterm = st.text_input("Zoek ruit...", value=st.session_state.zoek_input, label_visibility="collapsed")
with c2: 
    if st.button("Wis Zoekopdracht", use_container_width=True):
        st.session_state.zoek_input = ""
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- 7. TABEL WEERGAVE ---
df_view = df_master.copy()
if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# We voegen een tijdelijk rij-nummer toe dat je kunt typen
df_view.insert(0, "NR", range(1, len(df_view) + 1))

st.dataframe(df_view.drop(columns=["ID"]), hide_index=True, use_container_width=True, height=400)

# --- 8. UIT VOORRAAD MELDEN (DE NUMMER METHODE) ---
st.markdown("---")
if not df_view.empty:
    st.subheader("🗑️ Uit voorraad melden")
    col_a, col_b = st.columns([1, 2])
    with col_a:
        nr_to_del = st.number_input("Typ het NR uit de tabel:", min_value=0, max_value=len(df_view), step=1, value=0)
    with col_b:
        st.write("") # uitlijning
        if nr_to_del > 0:
            # Pak de data van die specifieke rij uit de VIEW
            target_row = df_view.iloc[nr_to_del - 1]
            if st.button(f"Meld Order {target_row['Order']} uit voorraad", type="primary"):
                # Verwijder op basis van ID uit de MASTER
                st.session_state.mijn_data = df_master[df_master["ID"] != target_row["ID"]]
                sla_op(st.session_state.mijn_data)
                st.success("Verwijderd!")
                time.sleep(1)
                st.rerun()
else:
    st.info("Geen resultaten gevonden.")

# --- 9. IMPORT ---
with st.sidebar:
    st.subheader("📥 Import")
    up = st.file_uploader("Excel", type=["xlsx"])
    if up and st.button("Upload"):
        new = pd.read_excel(up).astype(str)
        new["ID"] = [str(uuid.uuid4()) for _ in range(len(new))]
        st.session_state.mijn_data = pd.concat([df_master, new], ignore_index=True)
        sla_op(st.session_state.mijn_data)
        st.rerun()
