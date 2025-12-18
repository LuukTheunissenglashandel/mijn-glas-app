import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- INITIALISATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "zoek_input" not in st.session_state: st.session_state.zoek_input = ""

# --- CSS: HET MOOIE DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    div[data-testid="stMetric"] { background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    
    /* Styling voor de actieknop in de tabel */
    button[kind="secondary"] { border-radius: 6px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
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
    save_df = df[["ID"] + DATAKOLOMMEN]
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- AUTH ---
if not st.session_state.ingelogd:
    c1, c2, c3 = st.columns([1,2,1])
    with col2 := c2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- HEADER & KPI'S ---
df_master = st.session_state.mijn_data
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df_master["Aantal"].astype(int).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", tot)
with c3: 
    st.metric("Unieke Orders", df_master["Order"].nunique())

# --- ACTIEBALK (ZOEKEN) ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
with c1: zoekterm = st.text_input("Zoeken", placeholder="Zoek op order, maat of locatie...", value=st.session_state.zoek_input)
with c2: st.button("🔍", use_container_width=True)
with c3: 
    if st.button("❌", use_container_width=True):
        st.session_state.zoek_input = ""
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- FILTEREN ---
df_view = df_master.copy()
if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# --- DE TABEL MET DIRECTE KNOPPEN ---
# We voegen een tijdelijke kolom toe voor de knop
df_view["Meld"] = False 

# Gebruik data_editor met ButtonColumn (Dit is de moderne Streamlit manier)
# Let op: dit vereist een recente Streamlit versie. 
# Als dit een AttributeError geeft, gebruik dan de versie met de selectbox hieronder.
try:
    event = st.data_editor(
        df_view,
        column_config={
            "ID": None,
            "Meld": st.column_config.ButtonColumn(
                "Meld uit",
                help="Klik om deze ruit direct te verwijderen",
                width="small",
                default_value=False
            ),
            "Locatie": st.column_config.TextColumn(width="small"),
            "Order": st.column_config.TextColumn(width="medium"),
        },
        disabled=DATAKOLOMMEN,
        hide_index=True,
        use_container_width=True,
        height=600,
        key="editor_clean"
    )

    # Check of er op een knop is geklikt
    # In de nieuwste Streamlit versies geeft de editor een 'event' terug
    if any(event["edited_rows"].values()):
        for row_idx, changes in event["edited_rows"].items():
            if "Meld" in changes:
                # Pak de juiste ruit op basis van ID
                ruit_id = df_view.iloc[row_idx]["ID"]
                ruit_order = df_view.iloc[row_idx]["Order"]
                
                # Verwijder uit master
                st.session_state.mijn_data = df_master[df_master["ID"] != ruit_id]
                sla_op(st.session_state.mijn_data)
                st.toast(f"✅ Order {ruit_order} verwijderd!")
                time.sleep(0.5)
                st.rerun()

except Exception:
    # FALLBACK: Als ButtonColumn niet werkt op jouw server, gebruiken we een veilige selectie
    st.info("Selecteer een ruit uit de lijst om deze te verwijderen:")
    keuze_lijst = {f"Order: {r['Order']} | Maat: {r['Breedte']}x{r['Hoogte']}": r['ID'] for _, r in df_view.iterrows()}
    gekozen = st.selectbox("Direct uit voorraad melden:", ["-- Geen selectie --"] + list(keuze_lijst.keys()))
    
    if gekozen != "-- Geen selectie --":
        if st.button(f"🗑️ Verwijder {gekozen}", type="primary"):
            id_weg = keuze_lijst[gekozen]
            st.session_state.mijn_data = df_master[df_master["ID"] != id_weg]
            sla_op(st.session_state.mijn_data)
            st.rerun()

# --- SIDEBAR IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    up = st.file_uploader("Bestand", type=["xlsx"])
    if up and st.button("Uploaden"):
        new = pd.read_excel(up).astype(str)
        new["ID"] = [str(uuid.uuid4()) for _ in range(len(new))]
        st.session_state.mijn_data = pd.concat([df_master, new], ignore_index=True)
        sla_op(st.session_state.mijn_data)
        st.rerun()
