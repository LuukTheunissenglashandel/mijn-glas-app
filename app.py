import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- CSS: Layout & Styling ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* Gekleurde knoppen */
    div.stButton > button[key="real_del_btn"] { background-color: #28a745; color: white; border-radius: 8px; height: 50px; width: 100%; font-weight: bold;}
    div.stButton > button[key="cancel_del_btn"] { background-color: #dc3545; color: white; border-radius: 8px; height: 50px; width: 100%; font-weight: bold;}
    
    /* Zoek en Wis knoppen styling */
    div.stButton > button[key="search_btn"] { border-radius: 5px; height: 42px; width: 100%; }
    div.stButton > button[key="clear_btn"] { background-color: #f0f2f6; border-radius: 5px; height: 42px; width: 100%; color: #ff4b4b; border: 1px solid #ff4b4b;}

    input[type=checkbox] { transform: scale(1.5); }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    try:
        if val is None or str(val).strip() == "": return ""
        s_val = str(val).replace(',', '.').strip()
        return str(int(float(s_val)))
    except:
        return str(val)

def laad_data():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    for col in DATAKOLOMMEN:
        if col not in df.columns:
            df[col] = ""

    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_int)
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

def clear_search():
    """Callback om zoekveld leeg te maken"""
    st.session_state.zoek_input = ""

# --- AUTH ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.header("🔒 Inloggen")
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Starten"):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- MAIN APP ---
st.title("🏭 Glas Voorraad")

if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()
    if "Selecteer" not in st.session_state.mijn_data.columns:
        st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# 2. Sidebar Import
with st.sidebar:
    st.header("📥 Import")
    uploaded_file = st.file_uploader("Excel bestand (.xlsx)", type=["xlsx"])
    if uploaded_file:
        if st.button("Bevestig Upload"):
            try:
                nieuwe_data = pd.read_excel(uploaded_file)
                nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
                
                mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                nieuwe_data = nieuwe_data.rename(columns=mapping)
                nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                if "Locatie" not in nieuwe_data.columns: nieuwe_data["Locatie"] = ""

                for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                    if col in nieuwe_data.columns: nieuwe_data[col] = nieuwe_data[col].apply(clean_int)

                for c in DATAKOLOMMEN:
                    if c not in nieuwe_data.columns: nieuwe_data[c] = ""
                
                final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
                huidig_uit_cloud = laad_data()
                totaal = pd.concat([huidig_uit_cloud, final_upload], ignore_index=True)
                sla_data_op(totaal)
                del st.session_state.mijn_data
                st.rerun()
            except Exception as e:
                st.error(f"Fout: {e}")

# 3. Zoekbalk Sectie (AANGEPAST)
# We gebruiken kolommen om Input, Zoekknop en Wisknop naast elkaar te zetten
col_input, col_zoek, col_wis = st.columns([5, 1, 1], gap="small")

with col_input:
    # We koppelen de input aan sessie state 'zoek_input' zodat we hem kunnen wissen
    zoekterm = st.text_input("🔍", placeholder="Typ order, maat of locatie...", label_visibility="collapsed", key="zoek_input")

with col_zoek:
    # Deze knop doet technisch niks anders dan de pagina herladen (wat het zoeken triggert), maar is duidelijk voor gebruiker
    st.button("🔍 Zoek", key="search_btn")

with col_wis:
    # Deze knop roept de 'clear_search' functie aan
    st.button("❌ Wis", on_click=clear_search, key="clear_btn")

# Verwijder knop placeholder
btn_place = st.empty()

# Filter logic
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# 4. TABEL
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
        "Locatie": st.column_config.TextColumn("Locatie", width="small"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"), 
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "ID": None
    },
    disabled=["ID"], 
    hide_index=True,
    num_rows="fixed",
    height=750, 
    use_container_width=False, 
    key="editor"
)

# 5. Opslaan Logica
if not edited_df.drop(columns=["Selecteer"]).equals(df.loc[edited_df.index].drop(columns=["Selecteer"])):
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)

# 6. Verwijder Logica
try:
    geselecteerd = edited_df[edited_df["Selecteer"] == True]
except:
    geselecteerd = []

if len(geselecteerd) > 0:
    with btn_place.container():
        # Een witregel voor layout
        st.write("") 
        if st.button(f"🗑️ Verwijder ({len(geselecteerd)})", type="primary"):
            st.session_state.ask_del = True
            
        if st.session_state.get('ask_del'):
            st.warning("Definitief verwijderen?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("JA", key="real_del_btn"):
                    ids_weg = geselecteerd["ID"].tolist()
                    st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
                    sla_data_op(st.session_state.mijn_data)
                    st.session_state.ask_del = False
                    st.rerun()
            with c2:
                if st.button("NEE", key="cancel_del_btn"):
                    st.session_state.ask_del = False
                    st.rerun()
