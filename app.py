import streamlit as st

import pandas as pd

import uuid

import time

from streamlit_gsheets import GSheetsConnection



# --- CONFIGURATIE ---

WACHTWOORD = "glas123"

# Volgorde: Locatie, Aantal, Breedte, Hoogte, Order, Uit voorraad, Omschrijving, Spouw

DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]



st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")



# --- CSS: PROFESSIONAL DESIGN ---

st.markdown("""

    <style>

    .block-container { padding-top: 1rem; padding-bottom: 5rem; }

    #MainMenu, footer, header {visibility: hidden;}

    [data-testid="stToolbar"] {visibility: hidden !important;}



    div.stButton > button { 

        border-radius: 8px; height: 45px; font-weight: 600; border: none; 

    }

    

    div.stButton > button[key="search_btn"] { background-color: #0d6efd; color: white; }

    div.stButton > button[key="clear_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }



    div[data-testid="stMetric"] {

        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px;

    }



    /* Checkbox groter voor makkelijker klikken */

    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }



    @media only screen and (max-width: 1024px) {

        section[data-testid="stSidebar"] { display: none !important; }

        [data-testid="collapsedControl"] { display: none !important; }

    }

    </style>

    """, unsafe_allow_html=True)



# --- FUNCTIES ---

def get_connection():

    return st.connection("gsheets", type=GSheetsConnection)



def clean_int(val):

    try:

        if val is None or str(val).strip() == "": return ""

        return str(int(float(str(val).replace(',', '.'))))

    except:

        return str(val)



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

        if col not in df.columns: 

            df[col] = "Nee" if col == "Uit voorraad" else ""



    # Forceer "Uit voorraad" naar Ja/Nee tekst voor stabiliteit

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

    # Maak een kopie en zorg dat alles platte tekst is voor de cloud

    save_df = df.copy().astype(str)

    try:

        conn.update(worksheet="Blad1", data=save_df)

        st.cache_data.clear()

    except Exception as e:

        st.error(f"Fout bij opslaan: {e}")



def clear_search():

    st.session_state.zoek_input = ""



# --- AUTH ---

if "ingelogd" not in st.session_state: st.session_state.ingelogd = False

if not st.session_state.ingelogd:

    col1, col2, col3 = st.columns([1,2,1])

    with col2:

        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)

        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed", placeholder="Wachtwoord...")

        if st.button("Inloggen", use_container_width=True):

            if ww == WACHTWOORD:

                st.session_state.ingelogd = True

                st.rerun()

            else: st.error("Fout wachtwoord")

    st.stop()



# --- DATA INITIALISATIE ---

if 'mijn_data' not in st.session_state:

    st.session_state.mijn_data = laad_data_van_cloud()



df = st.session_state.mijn_data



# --- SIDEBAR ---

with st.sidebar:

    st.subheader("📥 Excel Import")

    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file and st.button("📤 Toevoegen", key="upload_btn"):

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



# --- KPI's ---

active_df = df[df["Uit voorraad"] == "Nee"]

c1, c2, c3 = st.columns([2, 1, 1])

with c1: st.title("🏭 Glas Voorraad")

with c2: 

    aantal_num = pd.to_numeric(active_df["Aantal"], errors='coerce').fillna(0)

    st.metric("In Voorraad (stuks)", int(aantal_num.sum()))

with c3: 

    orders = active_df[active_df["Order"] != ""]["Order"].apply(lambda x: str(x).split('-')[0].strip())

    st.metric("Unieke Orders", orders.nunique())



# --- ZOEKBALK ---

c_in, c_zo, c_wi = st.columns([7, 1, 1], gap="small", vertical_alignment="bottom")

with c_in: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed", key="zoek_input")

with c_zo: st.button("🔍", key="search_btn", use_container_width=True)

with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)



st.write("") 



# --- TABEL ---

view_df = df.copy()

if st.session_state.get("zoek_input"):

    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)

    view_df = view_df[mask]



# BELANGRIJK: Omzetten naar echte booleans ALLEEN voor het tonen van de checkbox

view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"



def highlight_stock(s):

    return ['background-color: #ff4b4b; color: white' if s["Uit voorraad_bool"] else '' for _ in s]



styled_view = view_df.style.apply(highlight_stock, axis=1)



edited_df = st.data_editor(

    styled_view,

    column_config={

        "Locatie": st.column_config.TextColumn("Locatie", width="small"),

        "Aantal": st.column_config.TextColumn("Aant.", width="small"),

        "Breedte": st.column_config.TextColumn("Br.", width="small"),

        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),

        "Order": st.column_config.TextColumn("Order", width="medium"),

        # Hier is het vinkje terug voor 1-klik actie

        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad\nmelden", width="small", default=False),

        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"),

        "Spouw": st.column_config.TextColumn("Sp.", width="small"),

        "ID": None,

        "Uit voorraad": None # Verberg de tekst kolom

    },

    disabled=["ID", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"], # Alleen checkbox klikbaar maken voor snelheid

    hide_index=True,

    use_container_width=True,

    height=700,

    key="editor"

)



# VERWERKING VAN DE KLIK

if not edited_df.equals(view_df):

    # Vertaal de checkbox-klik direct terug naar Ja/Nee tekst

    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")

    

    # Update de hoofd-dataset

    st.session_state.mijn_data.update(edited_df[["ID", "Uit voorraad"]])

    

    # Sla op naar Google Sheets

    sla_data_op(st.session_state.mijn_data)

    st.rerun()
