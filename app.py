import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; }
    div.stButton > button[key="header_del_btn"] { background-color: #dc3545; color: white; }
    div.stButton > button[key="real_del_btn"] { background-color: #198754; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data_van_cloud():
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
        if col not in df.columns: df[col] = ""
    
    if "Status" not in df.columns:
        df["Status"] = "In Voorraad"
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df_to_save):
    conn = get_connection()
    # Verwijder hulpkolom voor opslag
    output_df = df_to_save.copy()
    if "Selecteer" in output_df.columns:
        output_df = output_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=output_df)
    st.cache_data.clear()

# --- INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    if "Selecteer" not in st.session_state.mijn_data.columns:
        st.session_state.mijn_data.insert(0, "Selecteer", False)

# --- SIDEBAR ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_excel = st.file_uploader("Kies Excel", type=["xlsx"])
    if uploaded_excel and st.button("📤 Toevoegen"):
        nieuwe_data = pd.read_excel(uploaded_excel)
        nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
        nieuwe_data["Status"] = "In Voorraad"
        nieuwe_data["Selecteer"] = False
        # Zorg dat kolommen matchen
        for c in DATAKOLOMMEN:
            if c not in nieuwe_data.columns: nieuwe_data[c] = ""
        
        st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, nieuwe_data], ignore_index=True)
        sla_data_op(st.session_state.mijn_data)
        st.rerun()

# --- KPI'S ---
df = st.session_state.mijn_data
c1, c2 = st.columns(2)
in_voorraad_count = len(df[df["Status"] != "Uit Voorraad"])
c1.metric("Items In Voorraad", in_voorraad_count)
c2.metric("Items Uit Voorraad", len(df[df["Status"] == "Uit Voorraad"]))

# --- ACTIES ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
geselecteerd = df[df["Selecteer"] == True]

if st.session_state.get('ask_del'):
    if st.button(f"⚠️ Bevestig: {len(geselecteerd)} items naar 'Uit Voorraad'", key="real_del_btn"):
        indices = geselecteerd.index
        st.session_state.mijn_data.loc[indices, "Status"] = "Uit Voorraad"
        st.session_state.mijn_data.loc[indices, "Selecteer"] = False
        sla_data_op(st.session_state.mijn_data)
        st.session_state.ask_del = False
        st.rerun()
    if st.button("Annuleren"):
        st.session_state.ask_del = False
        st.rerun()
elif len(geselecteerd) > 0:
    if st.button("📦 Meld geselecteerde items UIT VOORRAAD", key="header_del_btn"):
        st.session_state.ask_del = True
        st.rerun()
else:
    zoekterm = st.text_input("Zoeken", placeholder="Typ om te filteren...")
st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
view_df = df.copy()
show_all = st.checkbox("Toon ook items die al uit voorraad zijn", value=False)

if not show_all:
    view_df = view_df[view_df["Status"] != "Uit Voorraad"]

if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# De eigenlijke editor
edited_output = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", width="small"),
        "Status": st.column_config.SelectboxColumn("Status", options=["In Voorraad", "Uit Voorraad"]),
        "ID": None
    },
    hide_index=True,
    use_container_width=True,
    key="hoofd_editor"
)

# Synchronisatie met session_state (beveiligd tegen massa-update)
if not edited_output.equals(view_df):
    for idx, row in edited_output.iterrows():
        orig_id = row["ID"]
        # Update alleen de specifieke rij in de hoofd-dataset op basis van ID
        for col in view_df.columns:
            if col != "ID":
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == orig_id, col] = row[col]
    
    sla_data_op(st.session_state.mijn_state)
    st.rerun()
