import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE & THEMA ---
st.set_page_config(
    layout="wide", 
    page_title="Glas Voorraad Dashboard", 
    initial_sidebar_state="collapsed"
)

# Professionele Styling voor Tablet (Samsung A9)
st.markdown("""
    <style>
    /* Algemene font en achtergrond */
    .main { background-color: #f8f9fa; }
    
    /* Maak metrics groter voor op een tablet */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Zoekbalk styling */
    .stTextInput input {
        height: 60px !important;
        font-size: 20px !important;
        border-radius: 12px !important;
    }
    
    /* Tabel styling */
    .stDataFrame {
        border: 1px solid #dee2e6;
        border-radius: 12px;
        background-color: #ffffff;
    }

    /* Verberg overbodige Streamlit menu's */
    #MainMenu, footer, header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# --- 2. FUNCTIES ---
def laad_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # ttl=0 zorgt dat we altijd de allerlaatste versie uit de sheet zien
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=DATAKOLOMMEN)
        return df.fillna("").astype(str)
    except:
        return pd.DataFrame(columns=DATAKOLOMMEN)

def sla_op(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Blad1", data=df)
    st.cache_data.clear()

# --- 3. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    st.markdown("<h1 style='text-align: center;'>🏭 Glas Voorraad</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            ww = st.text_input("Wachtwoord", type="password")
            if st.form_submit_button("Start Dashboard", use_container_width=True):
                if ww == WACHTWOORD:
                    st.session_state.ingelogd = True
                    st.rerun()
                else:
                    st.error("Wachtwoord onjuist")
    st.stop()

# --- 4. DATA LADEN ---
# We laden de data elke keer opnieuw als de pagina ververst wordt (voor de tablet)
df_master = laad_data()

# --- 5. DASHBOARD HEADER ---
st.title("🏭 Glas Voorraad Dashboard")

# KPI's (Metrics) bovenaan - Groot en duidelijk op tablet
c1, c2, c3 = st.columns(3)
with c1:
    try:
        totaal_ruiten = df_master["Aantal"].astype(float).sum()
        st.metric("Totaal Ruiten", int(totaal_ruiten))
    except:
        st.metric("Totaal Ruiten", "0")

with c2:
    unieke_orders = df_master["Order"].nunique()
    st.metric("Aantal Orders", unieke_orders)

with c3:
    unieke_locaties = df_master["Locatie"].nunique()
    st.metric("Aantal Locaties", unieke_locaties)

st.markdown("---")

# --- 6. ZOEKEN & FILTEREN ---
# Extra grote zoekbalk voor makkelijk typen op een tablet
zoekterm = st.text_input("🔍 Zoek ruit...", placeholder="Typ order, afmeting of locatie...")

df_view = df_master.copy()
if zoekterm:
    # Filtert door alle kolommen heen
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# --- 7. DE VOORRAAD TABEL ---
st.subheader(f"Voorraadlijst ({len(df_view)} resultaten)")

# We tonen de tabel in 'Read Only' modus. 
# Dit is extreem robuust en kan niet crashen of data wissen.
st.dataframe(
    df_view[DATAKOLOMMEN], 
    use_container_width=True, 
    height=600, 
    hide_index=True
)

# --- 8. SIDEBAR (IMPORT & REFRESH) ---
with st.sidebar:
    st.header("⚙️ Beheer")
    
    if st.button("🔄 Ververs Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Upload nieuwe voorraad", type=["xlsx"])
    
    if uploaded_file:
        if st.button("📤 Toevoegen aan Sheets", use_container_width=True):
            try:
                nieuwe_data = pd.read_excel(uploaded_file).astype(str)
                # Alleen kolommen behouden die we nodig hebben
                for col in DATAKOLOMMEN:
                    if col not in nieuwe_data.columns:
                        nieuwe_data[col] = ""
                
                updated_df = pd.concat([df_master, nieuwe_data[DATAKOLOMMEN]], ignore_index=True)
                sla_op(updated_df)
                st.success("Voorraad succesvol bijgewerkt!")
                st.rerun()
            except Exception as e:
                st.error(f"Fout bij upload: {e}")

    st.markdown("---")
    if st.button("Log uit"):
        st.session_state.ingelogd = False
        st.rerun()
