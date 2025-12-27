import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE & LOCATIES ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- 2. CSS: HEADER WRAPPING & UI ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Zorg dat headers tekst afbreken naar 2 regels */
    [data-testid="stDataEditor"] div[role="columnheader"] p {
        white-space: normal !important;
        line-height: 1.1 !important;
        word-break: break-word !important;
        text-align: center;
    }

    div.stButton > button { border-radius: 8px; height: 50px; font-weight: 600; }
    [data-testid="stDataEditor"] div { line-height: 1.8 !important; }
    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }

    @media only screen and (max-width: 1024px) {
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
    }
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
    
    for col in DATAKOLOMMEN:
        if col not in df.columns: 
            df[col] = "Nee" if col == "Uit voorraad" else ""

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
    try:
        conn.update(worksheet="Blad1", data=df.astype(str))
        st.cache_data.clear()
    except Exception as e: st.error(f"Fout bij opslaan: {e}")

def clear_search():
    st.session_state.zoek_input = ""

# --- 4. AUTHENTICATIE (ONTHOUDT LOGIN) ---
if "logged_in" in st.query_params:
    st.session_state.ingelogd = True

if "ingelogd" not in st.session_state: st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.query_params["logged_in"] = "true"
                st.rerun()
            else: st.error("Fout wachtwoord")
    st.stop()

# --- 5. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 6. SIDEBAR: IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Toevoegen"):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
            mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
            nieuwe_data = nieuwe_data.rename(columns=mapping)
            nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
            nieuwe_data["Uit voorraad"] = "Nee"
            for col in DATAKOLOMMEN:
                if col not in nieuwe_data.columns: nieuwe_data[col] = ""
            final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")

# --- 7. DASHBOARD (KPI'S & UITLOGGEN) ---
active_df = st.session_state.mijn_data[st.session_state.mijn_data["Uit voorraad"] == "Nee"]
c1, c2, c3, c4 = st.columns([2, 1, 1, 0.6])
with c1: st.title("🏭 Glas Voorraad")
with c2: st.metric("In Voorraad", int(pd.to_numeric(active_df["Aantal"], errors='coerce').sum()))
with c3: 
    unique_orders = active_df[active_df["Order"] != ""]["Order"].nunique()
    st.metric("Unieke Orders", unique_orders)
with c4:
    st.write("") 
    if st.button("🚪 Uit", help="Uitloggen"):
        st.session_state.ingelogd = False
        st.query_params.clear()
        st.rerun()

# --- 8. ZOEKFUNCTIE ---
c_in, c_zo, c_wi = st.columns([7, 1, 1], gap="small", vertical_alignment="bottom")
with c_in: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed", key="zoek_input")
with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

# --- 9. TABEL VOORBEREIDEN ---
view_df = st.session_state.mijn_data.copy()

if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

# Kolomvolgorde: Uit voorraad melden als eerste
volgorde = ["Uit voorraad_bool", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw", "ID", "Uit voorraad"]
view_df = view_df[volgorde]

edited_df = st.data_editor(
    view_df,
    column_config={
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad melden", width="small"),
        "Locatie": st.column_config.SelectboxColumn("📍 Loc", width="small", options=LOCATIE_OPTIES, required=True),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "ID": None,            
        "Uit voorraad": None   
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# --- 10. OPSLAGLOGICA (DE FIX VOOR KEYERROR) ---
if not edited_df.equals(view_df):
    # Converteer checkbox terug naar tekst
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Maak een kopie van de masterdata
    main_df = st.session_state.mijn_data.copy()
    
    # Voer de update uit op basis van ID zonder de master-index permanent te veranderen
    main_df = main_df.set_index("ID")
    edited_updates = edited_df.set_index("ID")[["Locatie", "Uit voorraad"]]
    
    main_df.update(edited_updates)
    
    # Zet ID weer terug als kolom en sla op
    st.session_state.mijn_data = main_df.reset_index()
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
