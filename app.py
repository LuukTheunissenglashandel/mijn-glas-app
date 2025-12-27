import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- 2. CSS VOOR HEADER WRAPPING & STYLING ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Forceert de tekst in de tabelkop om af te breken naar een nieuwe regel */
    [data-testid="stDataEditor"] div[role="columnheader"] p {
        white-space: normal !important;
        word-break: break-word !important;
        line-height: 1.2 !important;
        text-align: center;
    }

    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; }
    input[type=checkbox] { transform: scale(1.3); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        
        # Zorg dat elke rij een uniek ID heeft
        if "ID" not in df.columns or df["ID"].isnull().any():
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        
        return df.fillna("").astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_data_op(df):
    conn = get_connection()
    try:
        conn.update(worksheet="Blad1", data=df.astype(str))
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# --- 4. AUTHENTICATIE (MET URL PERSISTENTIE) ---
if "login" in st.query_params and st.query_params["login"] == "success":
    st.session_state.ingelogd = True

if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.subheader("🔒 Inloggen")
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.query_params["login"] = "success"
                st.rerun()
            else: st.error("Onjuist")
    st.stop()

# --- 5. DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- 6. HEADER & UITLOGGEN ---
c_title, c_logout = st.columns([8, 2])
with c_title: st.title("🏭 Glas Voorraad")
with c_logout:
    if st.button("🚪 Uitloggen", use_container_width=True):
        st.session_state.ingelogd = False
        st.query_params.clear()
        st.rerun()

# --- 7. ZOEKBALK ---
zoek_input = st.text_input("Zoeken", placeholder="Typ ordernummer, breedte of locatie...", key="zoek_veld")

# --- 8. TABEL VOORBEREIDEN ---
main_df = st.session_state.mijn_data.copy()

# Maak een hulp-kolom voor de checkbox
main_df["Uit voorraad_bool"] = main_df["Uit voorraad"].apply(lambda x: x.lower() == "ja")

# Kolomvolgorde bepalen: Checkbox VOORAAN
volgorde = ["Uit voorraad_bool", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw", "ID"]
display_df = main_df[volgorde]

# Filteren op basis van zoekopdracht
if zoek_input:
    mask = display_df.drop(columns=["ID", "Uit voorraad_bool"]).astype(str).apply(
        lambda x: x.str.contains(zoek_input, case=False)
    ).any(axis=1)
    filtered_df = display_df[mask]
else:
    filtered_df = display_df

# --- 9. DE DATA EDITOR ---
edited_df = st.data_editor(
    filtered_df,
    column_config={
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad melden", width="small"),
        "Locatie": st.column_config.SelectboxColumn("Locatie", options=LOCATIE_OPTIES, width="small"),
        "Aantal": st.column_config.TextColumn("Aantal", width="small"),
        "Breedte": st.column_config.TextColumn("Breedte", width="small"),
        "Hoogte": st.column_config.TextColumn("Hoogte", width="small"),
        "ID": None # Verberg ID
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- 10. VEILIGE OPSLAGLOGICA ---
# We vergelijken de gefilterde editor alleen met de gefilterde view
if not edited_df.equals(filtered_df):
    # Maak een kopie van de huidige hoofd-data
    new_main_data = st.session_state.mijn_data.copy()
    
    # Loop ALLEEN door de rijen die in de editor stonden
    for _, row in edited_df.iterrows():
        row_id = row["ID"]
        nieuwe_locatie = row["Locatie"]
        nieuwe_status = "Ja" if row["Uit voorraad_bool"] else "Nee"
        
        # Zoek de rij in de originele dataset op basis van het unieke ID
        idx = new_main_data.index[new_main_data['ID'] == row_id].tolist()
        if idx:
            # Update alleen deze specifieke rij
            new_main_data.at[idx[0], "Locatie"] = nieuwe_locatie
            new_main_data.at[idx[0], "Uit voorraad"] = nieuwe_status

    # Opslaan en sessie bijwerken
    st.session_state.mijn_data = new_main_data
    sla_data_op(new_main_data)
    st.rerun()
