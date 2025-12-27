import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- 2. DATA FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

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
            df[col] = "Nee" if col == "Uit voorraad" else ""
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df.astype(str))
    st.cache_data.clear()

# --- 3. AUTHENTICATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    st.title("🔒 Inloggen")
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

# --- 4. INITIALISATIE DATA ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- 5. CONTROLE PANEEL (BOVENAAN VOOR TABLET/DESKTOP) ---
st.title("🏭 Glas Voorraad")

# We gebruiken kolommen om alles netjes naast elkaar te zetten
col_zoek, col_locatie, col_knop = st.columns([3, 1, 1])

with col_zoek:
    zoekterm = st.text_input("🔍 Zoeken", placeholder="Zoek op order, maat...", label_visibility="collapsed")

with col_locatie:
    nieuwe_locatie_keuze = st.selectbox("Nieuwe Locatie", LOCATIE_OPTIES, label_visibility="collapsed", key="bulk_loc_sb")

with col_knop:
    # Deze knop voert de actie uit
    verplaats_knop = st.button("📍 Verplaats Selectie", type="primary", use_container_width=True)

st.divider()

# --- 6. DATA VOORBEREIDEN ---
df_view = st.session_state.mijn_data.copy()

if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# Selectiekolom en boolean kolom toevoegen
df_view.insert(0, "Kies", False)
df_view["Uit voorraad_bool"] = df_view["Uit voorraad"] == "Ja"

# --- 7. DE TABEL (EDITOR) ---
edited_df = st.data_editor(
    df_view,
    column_config={
        "Kies": st.column_config.CheckboxColumn("S", width="small"),
        "Locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("✅ Uit"),
        "ID": None, 
        "Uit voorraad": None
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=600,
    key="main_editor"
)

# --- 8. LOGICA VERWERKING ---

# A. BULK ACTIE (De knop bovenaan)
if verplaats_knop:
    # 1. Haal de aangevinkte rijen op uit de bewerkte tabel
    geselecteerde_rijen = edited_df[edited_df["Kies"] == True]
    
    if not geselecteerde_rijen.empty:
        ids_to_update = geselecteerde_rijen["ID"].tolist()
        
        # 2. Update de echte data in de sessie
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids_to_update), "Locatie"] = nieuwe_locatie_keuze
        
        # 3. Opslaan en herladen
        sla_op(st.session_state.mijn_data)
        st.success(f"✅ {len(ids_to_update)} rijen verplaatst naar {nieuwe_locatie_keuze}")
        st.rerun()
    else:
        st.error("⚠️ Vink eerst rijen aan in de kolom 'S'!")

# B. INDIVIDUELE WIJZIGINGEN (Direct in de tabel typen)
# We vergelijken de tabel ZONDER de kolom 'Kies', want die gebruiken we alleen voor de knop
elif not edited_df.drop(columns=["Kies"]).equals(df_view.drop(columns=["Kies"])):
    
    # Zet boolean terug naar tekst
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Zoek de verschillen en update de sessie data
    # (We itereren over edited_df omdat daar de wijzigingen in staan)
    for index, row in edited_df.iterrows():
        # Update locatie en voorraad status op basis van ID
        st.session_state.mijn_data.loc[
            st.session_state.mijn_data["ID"] == row["ID"], 
            ["Locatie", "Uit voorraad"]
        ] = [row["Locatie"], row["Uit voorraad"]]
    
    sla_op(st.session_state.mijn_data)
    st.rerun()
