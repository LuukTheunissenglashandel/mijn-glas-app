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
    
    # Zorg dat alle kolommen bestaan
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df.astype(str))
    st.cache_data.clear()

# --- 3. INITIALISATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- 4. BULK ACTIE PANEL ---
st.title("🏭 Glas Voorraad Beheer")

# We maken een container voor de bulk acties
with st.container(border=True):
    st.subheader("📦 Bulk Bewerking")
    col_sel, col_loc, col_btn = st.columns([2, 2, 2])
    
    with col_loc:
        nieuwe_bulk_locatie = st.selectbox("Kies nieuwe locatie", LOCATIE_OPTIES, key="bulk_loc_choice")
    
    with col_btn:
        st.write(" ") # Padding
        bulk_knop = st.button("📍 Pas toe op geselecteerde rijen", use_container_width=True, type="primary")

# --- 5. ZOEKFUNCTIE ---
zoekterm = st.text_input("🔍 Zoeken op order, maat of locatie...", key="search_bar")

# --- 6. TABEL VOORBEREIDEN ---
df_display = st.session_state.mijn_data.copy()

# Filteren
if zoekterm:
    mask = df_display.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_display = df_display[mask]

# Voeg de checkbox kolom toe (deze staat NIET in de database, alleen in de UI)
if "geselecteerde_ids" not in st.session_state:
    st.session_state.geselecteerde_ids = []

df_display["Selecteer"] = df_display["ID"].apply(lambda x: x in st.session_state.geselecteerde_ids)
df_display["Uit voorraad_bool"] = df_display["Uit voorraad"] == "Ja"

# Zet de kolommen in de juiste visuele volgorde
kolom_volgorde = ["Selecteer", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad_bool", "Omschrijving", "Spouw", "ID"]
df_display = df_display[kolom_volgorde]

# --- 7. DE DATA EDITOR ---
edited_df = st.data_editor(
    df_display,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("Kies", width="small"),
        "Locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES, width="medium"),
        "Aantal": st.column_config.TextColumn("Aant.", disabled=True),
        "Breedte": st.column_config.TextColumn("Breedte", disabled=True),
        "Hoogte": st.column_config.TextColumn("Hoogte", disabled=True),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("✅ Uit voorraad"),
        "ID": None, # Verberg ID
    },
    hide_index=True,
    use_container_width=True,
    key="hoofd_editor"
)

# --- 8. LOGICA VOOR WIJZIGINGEN ---

# Stap A: Bulk Locatie Wijzigen
if bulk_knop:
    # We kijken in de edited_df welke rijen zijn aangevinkt
    ids_om_te_wijzigen = edited_df[edited_df["Selecteer"] == True]["ID"].tolist()
    
    if ids_om_te_wijzigen:
        # Update de hoofd-dataframe in session_state
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids_om_te_wijzigen), "Locatie"] = nieuwe_bulk_locatie
        
        # Opslaan naar Google Sheets
        sla_op(st.session_state.mijn_data)
        st.success(f"✅ {len(ids_om_te_wijzigen)} rijen verplaatst naar {nieuwe_bulk_locatie}")
        st.rerun()
    else:
        st.warning("Selecteer eerst rijen door het vinkje in de kolom 'Kies' aan te zetten.")

# Stap B: Handmatige wijzigingen in de tabel (vinkje 'Uit voorraad' of 1 locatie aanpassen)
# We vergelijken de edited_df met de df_display (zonder de 'Selecteer' kolom)
elif not edited_df.drop(columns=["Selecteer"]).equals(df_display.drop(columns=["Selecteer"])):
    # Update de 'Uit voorraad' tekst op basis van de boolean
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Werk de hoofd-data bij voor de rijen die veranderd zijn
    for idx, row in edited_df.iterrows():
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == row["ID"], ["Locatie", "Uit voorraad"]] = [row["Locatie"], row["Uit voorraad"]]
    
    sla_op(st.session_state.mijn_data)
    st.rerun()
