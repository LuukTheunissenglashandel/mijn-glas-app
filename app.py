import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE & LOCATIES ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- 2. CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    div.stButton > button { border-radius: 8px; height: 50px; font-weight: 600; border: none; }
    [data-testid="stDataEditor"] div { line-height: 1.8 !important; }
    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    try:
        if val is None or str(val).strip() == "": return ""
        return str(int(float(str(val).replace(',', '.'))))
    except: return str(val)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    # Cruciaal: Zorg dat de data schoon is voor de dropdown
    df["Locatie"] = df["Locatie"].astype(str).str.strip()
    
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = "Nee" if col == "Uit voorraad" else ""

    if "Uit voorraad" in df.columns:
        df["Uit voorraad"] = df["Uit voorraad"].astype(str).apply(
            lambda x: "Ja" if x.lower() in ["true", "ja", "1", "yes"] else "Nee"
        )
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    if df.empty: return
    conn = get_connection()
    save_df = df.copy().astype(str)
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e: st.error(f"Fout: {e}")

def clear_search():
    st.session_state.zoek_input = ""

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

# --- 5. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 6. KPI'S & ZOEKEN ---
active_df = st.session_state.mijn_data[st.session_state.mijn_data["Uit voorraad"] == "Nee"]
st.title("🏭 Glas Voorraad")

c_in, c_zo, c_wi = st.columns([7, 1, 1], gap="small", vertical_alignment="bottom")
with c_in: st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed", key="zoek_input")
with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

# --- 9. TABEL & EDITOR ---
view_df = st.session_state.mijn_data.copy()

# Fix voor dropdown: alleen waardes toelaten die in de lijst staan
view_df["Locatie"] = view_df["Locatie"].str.strip()
view_df.loc[~view_df["Locatie"].isin(LOCATIE_OPTIES), "Locatie"] = ""

# Filteren
if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"
volgorde = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad_bool", "Omschrijving", "Spouw", "ID", "Uit voorraad"]
view_df = view_df[volgorde]

def highlight_stock(s):
    return ['background-color: #ff4b4b; color: white' if s["Uit voorraad_bool"] else '' for _ in s]

styled_view = view_df.style.apply(highlight_stock, axis=1)

edited_df = st.data_editor(
    styled_view,
    column_config={
        "Locatie": st.column_config.SelectboxColumn("📍 Loc", width="small", options=LOCATIE_OPTIES, required=True),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("✅ Uit voorraad", width="small"),
        "ID": None, "Uit voorraad": None
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# --- 10. OPSLAGLOGICA (DE REPARATIE) ---
if not edited_df.equals(view_df):
    # Vertaal bool naar tekst
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # REPARATIE: Gebruik ID als index voor de update zodat filters de boel niet in de war schoppen
    master_df = st.session_state.mijn_data.set_index("ID")
    update_df = edited_df[["ID", "Locatie", "Uit voorraad"]].set_index("ID")
    
    master_df.update(update_df)
    
    # Zet index weer terug naar kolom en sla op
    st.session_state.mijn_data = master_df.reset_index()
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
