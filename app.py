import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
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
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; border: none; }
    div[data-testid="stMetric"] { background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
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

# --- 4. AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...", label_visibility="collapsed")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else: st.error("Fout")
    st.stop()

# --- 5. INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 6. SIDEBAR (IMPORT) ---
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
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")

# --- 7. KPI's ---
df_master = st.session_state.mijn_data
active_df = df_master[df_master["Uit voorraad"] == "Nee"]
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: st.metric("In Voorraad", int(pd.to_numeric(active_df["Aantal"], errors='coerce').sum()))
with c3: st.metric("Unieke Orders", active_df[active_df["Order"] != ""]["Order"].nunique())

# --- 8. ZOEKBALK ---
c_in, c_zo, c_wi = st.columns([7, 1, 1], gap="small", vertical_alignment="bottom")
with c_in: st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed", key="zoek_input")
with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

# --- 9. TABEL ---
view_df = df_master.copy()
if st.session_state.zoek_input:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

# Helper voor checkbox
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

def highlight_stock(s):
    return ['background-color: #ff4b4b; color: white' if s["Uit voorraad_bool"] else '' for _ in s]

styled_view = view_df.style.apply(highlight_stock, axis=1)

edited_df = st.data_editor(
    styled_view,
    column_config={
        "Locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad", width="small"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "ID": None,
        "Uit voorraad": None
    },
    # BELANGRIJK: Locatie is NIET meer disabled!
    disabled=["ID", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# --- 10. VERWERKING (VEILIG GECOMBINEERD) ---
if not edited_df.equals(view_df):
    # 1. Update de status op basis van de checkbox
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # 2. Update alleen de rijen die in de editor zichtbaar waren (op basis van ID)
    # We gebruiken de ID als anker zodat filters geen invloed hebben op andere rijen
    new_master = st.session_state.mijn_data.copy()
    
    # We mappen de wijzigingen van Locatie en Uit voorraad terug naar de master
    for _, row in edited_df.iterrows():
        new_master.loc[new_master["ID"] == row["ID"], ["Locatie", "Uit voorraad"]] = [row["Locatie"], row["Uit voorraad"]]
    
    st.session_state.mijn_data = new_master
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
