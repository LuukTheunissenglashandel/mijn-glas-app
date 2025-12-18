import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE (MOET ALS ALLEREERSTE) ---
st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# --- 2. VEILIGE INITIALISATIE (ANTI-FLASH ERROR) ---
# We maken alle variabelen aan voordat we ook maar iets anders doen.
# Dit voorkomt de "AttributeError" en flitsen.

if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if "zoek_input" not in st.session_state:
    st.session_state.zoek_input = ""

if "mijn_data" not in st.session_state:
    # Begin met een leeg dataframe structuur, data laden we pas na login
    st.session_state.mijn_data = pd.DataFrame(columns=["ID", "Selecteer"] + DATAKOLOMMEN)

if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""

if "ask_del" not in st.session_state:
    st.session_state.ask_del = False

# --- 3. CSS: DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Actie Container */
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }

    /* Knoppen */
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; border: none; }
    div.stButton > button[key="search_btn"], div.stButton > button[key="bulk_update_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="clear_btn"], div.stButton > button[key="deselect_btn"], div.stButton > button[key="cancel_del_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }
    div.stButton > button[key="header_del_btn"] { background-color: #dc3545; color: white; }
    div.stButton > button[key="real_del_btn"] { background-color: #198754; color: white; }

    /* KPI Cards */
    div[data-testid="stMetric"] { background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    
    /* Checkbox vergroten */
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }

    @media only screen and (max-width: 1024px) {
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCTIES ---
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
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        # Als de sheet leeg is, geef lege tabel terug met juiste kolommen
        if df is None or df.empty: 
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    # Zorg dat alle kolommen bestaan en IDs uniek zijn
    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
    
    # Zorg dat Selecteer kolom bestaat en boolean is
    result = df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)
    result["Selecteer"] = False
    return result

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: 
        save_df = save_df.drop(columns=["Selecteer"])
    
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

def bereken_unieke_orders(df):
    try:
        return df[df["Order"] != ""]["Order"].apply(lambda x: x.split('-')[0].strip()).nunique()
    except: return 0

def clear_search():
    # Reset zoekterm
    st.session_state.zoek_input = ""
    # Reset selecties ook om verwarring te voorkomen
    if not st.session_state.mijn_data.empty:
        st.session_state.mijn_data["Selecteer"] = False

# --- 5. AUTHENTICATIE ---
if not st.session_state.ingelogd:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
            submit = st.form_submit_button("Inloggen", use_container_width=True)
            if submit:
                if ww == WACHTWOORD:
                    st.session_state.ingelogd = True
                    st.rerun()
                else:
                    st.error("Fout wachtwoord")
    st.stop() # Stop hier als niet ingelogd

# --- 6. DATA LADEN (ALLEEN ALS HET NOG NIET GELADEN IS) ---
# We checken of 'ID' in de kolommen zit. Zo niet, dan is het nog de lege placeholder.
if "ID" not in st.session_state.mijn_data.columns or st.session_state.mijn_data.empty:
    with st.spinner("Data ophalen..."):
        st.session_state.mijn_data = laad_data_van_cloud()

# Koppel aan lokale variabele voor makkelijker typen
df = st.session_state.mijn_data

# --- 7. SIDEBAR ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file:
        if st.button("📤 Toevoegen", key="upload_btn"):
            try:
                nieuwe = pd.read_excel(uploaded_file)
                nieuwe.columns = [c.strip().capitalize() for c in nieuwe.columns]
                mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                nieuwe = nieuwe.rename(columns=mapping)
                nieuwe["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe))]
                if "Locatie" not in nieuwe.columns: nieuwe["Locatie"] = ""
                for c in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                    if c in nieuwe.columns: nieuwe[c] = nieuwe[c].apply(clean_int)
                for c in DATAKOLOMMEN:
                    if c not in nieuwe.columns: nieuwe[c] = ""
                
                final = nieuwe[["ID"] + DATAKOLOMMEN].astype(str)
                final["Selecteer"] = False # Direct goed zetten
                
                # Samenvoegen
                st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final], ignore_index=True)
                sla_data_op(st.session_state.mijn_data)
                
                st.session_state.success_msg = f"{len(final)} regels toegevoegd!"
                time.sleep(1)
                st.rerun()
            except Exception as e: st.error(f"Fout: {e}")
    st.markdown("---")
    if st.button("🔄 Data Herladen"):
        st.session_state.mijn_data = laad_data_van_cloud()
        st.rerun()

# --- 8. HEADER ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df["Aantal"].replace('', '0').astype(int).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", tot)
with c3: st.metric("Unieke Orders", bereken_unieke_orders(df))

if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = "" 

# --- 9. STATUS BEPALEN (Aantal Geselecteerd) ---
try:
    geselecteerd_df = df[df["Selecteer"] == True]
    aantal_geselecteerd = len(geselecteerd_df)
except:
    aantal_geselecteerd = 0

# --- 10. ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)

if st.session_state.ask_del:
    # FASE 3: BEVESTIGING
    st.markdown(f"**⚠️ Weet je zeker dat je {aantal_geselecteerd} regels uit voorraad wilt melden?**")
    
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("✅ JA, Melden", key="real_del_btn", use_container_width=True):
            # 1. Haal ID's op van ALLES wat aangevinkt staat
            ids_weg = df[df["Selecteer"] == True]["ID"].tolist()
            
            # 2. Filter de dataset: Behoud alles wat NIET in 'ids_weg' zit
            st.session_state.mijn_data = df[~df["ID"].isin(ids_weg)]
            
            # 3. Opslaan
            sla_data_op(st.session_state.mijn_data)
            
            # 4. Reset UI
            st.session_state.ask_del = False
            st.session_state.zoek_input = "" # Zoekbalk leegmaken
            st.session_state.success_msg = f"✅ {len(ids_weg)} regels verwijderd!"
            st.rerun()

    with col_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    # FASE 2: ACTIEMODUS
    col_sel, col_loc, col_out = st.columns([1.5, 3, 1.5], gap="large", vertical_alignment="bottom")
    with col_sel:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Wissen", key="deselect_btn", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
    with col_loc:
        c_inp, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_inp:
            nieuwe_loc = st.text_input("Nieuwe Locatie", placeholder="Naar locatie...")
        with c_btn:
            if st.button("📍 Wijzig", key="bulk_update_btn", use_container_width=True):
                if nieuwe_loc:
                    ids = geselecteerd_df["ID"].tolist()
                    mask = st.session_state.mijn_data["ID"].isin(ids)
                    st.session_state.mijn_data.loc[mask, "Locatie"] = nieuwe_loc
                    st.session_state.mijn_data.loc[mask, "Selecteer"] = False
                    sla_data_op(st.session_state.mijn_data)
                    st.session_state.success_msg = f"📍 {len(ids)} verplaatst naar '{nieuwe_loc}'"
                    st.session_state.zoek_input = "" 
                    st.rerun()
    with col_out:
        st.write("") 
        if st.button("📦 Uit voorraad", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()

else:
    # FASE 1: ZOEKEN
    c_in, c_zo, c_wi = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
    with c_in:
        # We gebruiken hier st.session_state.zoek_input direct
        st.text_input("Zoeken", placeholder="🔍 Order, afmeting, locatie...", key="zoek_input")
    with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# --- 11. TABEL & FILTEREN VOOR WEERGAVE ---
view_df = df.copy()
# Haal zoekterm veilig op
actieve_zoekterm = st.session_state.get("zoek_input", "")

# Pas filter toe als er een zoekterm is
if actieve_zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(actieve_zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Toon alleen selectie als optie gekozen is
if aantal_geselecteerd > 0:
    st.caption("Weergave opties:")
    mode = st.radio("Toon:", ["Alles (gefilterd)", f"Alleen Selectie ({aantal_geselecteerd})"], horizontal=True, label_visibility="collapsed")
    if "Alleen Selectie" in mode:
        view_df = view_df[view_df["Selecteer"] == True]

# De Editor
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

# --- 12. SYNC LOGICA ---
if not edited_df.equals(view_df):
    st.session_state.mijn_data.update(edited_df)
    st.rerun()
