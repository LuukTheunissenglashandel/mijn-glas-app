import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: DESIGN & LAYOUT ---
st.markdown("""
    <style>
    /* Algemeen */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Cards & Balken */
    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px;
    }
    .actie-balk {
        background-color: #f1f3f4; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd;
    }

    /* Knoppen */
    div.stButton > button { border-radius: 6px; height: 42px; font-weight: 600; border: none; }
    
    /* Blauw (Zoek/Upload) */
    div.stButton > button[key="search_btn"], div.stButton > button[key="upload_btn"] { 
        background-color: #0d6efd; color: white; 
    }
    /* Wit/Grijs (Wis) */
    div.stButton > button[key="clear_btn"] { 
        background-color: white; color: #dc3545; border: 1px solid #dc3545; 
    }
    /* Rood (Verwijder Actie) */
    div.stButton > button[key="header_del_btn"], div.stButton > button[key="cancel_del_btn"] {
        background-color: #dc3545; color: white;
    }
    /* Groen (Bevestig) */
    div.stButton > button[key="real_del_btn"] {
        background-color: #198754; color: white;
    }

    /* Checkbox vergroten */
    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }
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

def laad_data_van_cloud():
    """Haalt verse data op van Google Sheets"""
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

    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
            
    # Return schoon dataframe, nog ZONDER 'Selecteer' kolom
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    """Slaat op naar Google Sheets (filtert eerst de 'Selecteer' kolom eruit)"""
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

def clear_search():
    st.session_state.zoek_input = ""

def bereken_unieke_orders(df):
    try:
        orders = df[df["Order"] != ""]["Order"].astype(str)
        basis_orders = orders.apply(lambda x: x.split('-')[0].strip())
        return basis_orders.nunique()
    except:
        return 0

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Inloggen</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed")
        if st.button("Starten", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- INITIALISATIE DATA ---
# We laden data 1 keer in de sessie. Daarna werken we met de sessie-kopie.
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    # Voeg Selecteer kolom toe aan sessie data
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# --- SIDEBAR (IMPORT) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Sleep bestand hierheen", type=["xlsx"], label_visibility="collapsed")
    
    if uploaded_file:
        st.info("Bestand herkend!")
        if st.button("📤 Toevoegen aan voorraad", key="upload_btn"):
            try:
                nieuwe_data = pd.read_excel(uploaded_file)
                # Kolommen netjes maken
                nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
                mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                nieuwe_data = nieuwe_data.rename(columns=mapping)
                
                # Data voorbereiden
                nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                if "Locatie" not in nieuwe_data.columns: nieuwe_data["Locatie"] = ""
                
                # Cijfers opschonen
                for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                    if col in nieuwe_data.columns: nieuwe_data[col] = nieuwe_data[col].apply(clean_int)
                
                # Zorg dat alle kolommen bestaan
                for c in DATAKOLOMMEN:
                    if c not in nieuwe_data.columns: nieuwe_data[c] = ""
                
                final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
                final_upload.insert(0, "Selecteer", False) # Ook nieuwe regels krijgen vinkje-kolom
                
                # 1. Update Sessie (Direct zichtbaar)
                st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
                
                # 2. Update Cloud (Achtergrond)
                sla_data_op(st.session_state.mijn_data)
                
                st.success(f"{len(final_upload)} regels toegevoegd!")
                st.rerun() # Ververs scherm zodat data zichtbaar is
            except Exception as e:
                st.error(f"Fout tijdens upload: {e}")
    
    st.markdown("---")
    if st.button("🔄 Data Herladen van Cloud"):
        del st.session_state.mijn_data
        st.rerun()

# --- HEADER & KPI's ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df["Aantal"].replace('', '0').astype(int).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", tot)
with c3: st.metric("Unieke Orders", bereken_unieke_orders(df))

# --- LOGICA VOOR ACTIEBALK ---
try:
    # Tel hoeveel vinkjes er op 'True' staan in de sessie data
    aantal_geselecteerd = len(df[df["Selecteer"] == True])
except:
    aantal_geselecteerd = 0

# --- DE ACTIEBALK ---
st.markdown('<div class="actie-balk">', unsafe_allow_html=True)

if st.session_state.get('ask_del'):
    # FASE 3: BEVESTIGING
    st.markdown(f"**⚠️ Weet je zeker dat je {aantal_geselecteerd} regels wilt verwijderen?**")
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("✅ JA, Verwijderen", key="real_del_btn", use_container_width=True):
            ids_weg = df[df["Selecteer"] == True]["ID"].tolist()
            # Verwijder uit sessie
            st.session_state.mijn_data = df[~df["ID"].isin(ids_weg)]
            # Opslaan naar cloud
            sla_data_op(st.session_state.mijn_data)
            # Reset states
            st.session_state.ask_del = False
            st.rerun()
    with col_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    # FASE 2: ER IS IETS GESELECTEERD -> TOON VERWIJDER KNOP
    c_txt, c_btn = st.columns([3, 1], vertical_alignment="center")
    with c_txt:
        st.markdown(f"✅ **{aantal_geselecteerd}** geselecteerd")
    with c_btn:
        if st.button(f"🗑️ Verwijder ({aantal_geselecteerd})", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
else:
    # FASE 1: STANDAARD ZOEKBALK
    c_in, c_zo, c_wi = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
    with c_in:
        zoekterm = st.text_input("Zoek", placeholder="🔍 Typ order, maat of locatie...", label_visibility="collapsed", key="zoek_input")
    with c_zo:
        st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi:
        st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# --- FILTER DATA VOOR WEERGAVE ---
view_df = df.copy() # We werken op een kopie voor weergave, zodat index intact blijft
if aantal_geselecteerd == 0 and zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- DE TABEL ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
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
    use_container_width=True,
    height=700,
    key="editor"
)

# --- UPDATE LOGICA ---
# Dit is het belangrijkste deel:
# Als de gebruiker iets aanpast in 'edited_df' (vinkje zetten), moeten we dat terugschrijven naar de hoofdtabel 'df'.
# Omdat 'view_df' soms gefilterd is, gebruiken we de index (of ID) om de juiste regels te updaten.

if not edited_df.equals(view_df):
    # Update de hoofd-dataset met de wijzigingen uit de editor
    st.session_state.mijn_data.update(edited_df)
    
    # Sla direct op naar cloud (achtergrond)
    sla_data_op(st.session_state.mijn_data)
    
    # CRUCIAAL: Herlaad de pagina direct. 
    # Hierdoor ziet de 'Actiebalk' bovenin direct dat er een vinkje staat.
    st.rerun()
