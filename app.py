import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- 2. DATA FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data_van_cloud():
    conn = get_connection()
    df = conn.read(worksheet="Blad1", ttl=0)
    if df is None or df.empty:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df.fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df.astype(str))
    st.cache_data.clear()

# --- 3. INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 4. ZOEKEN ---
st.title("🏭 Glas Voorraad")
zoekterm = st.text_input("Zoeken", key="zoek_input")

# Maak een kopie voor de weergave
view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Hulpmiddel voor checkbox
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

# --- 5. DE EDITOR (Met unieke key) ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Locatie": st.column_config.TextColumn("📍 Locatie"), # Handmatig typen om blokkade te voorkomen
        "Uit voorraad_bool": st.column_config.CheckboxColumn("✅ Uit voorraad"),
        "ID": None, 
        "Uit voorraad": None
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    key="mijn_editor" # Deze key is cruciaal!
)

# --- 6. DE CRUCIALE FIX: UPDATE ALLEEN DE SPECIFIEKE CEL ---
# We kijken in de 'edited_rows' dictionary van de editor state
updates = st.session_state.mijn_editor.get("edited_rows", {})

if updates:
    for row_index_str, changed_cols in updates.items():
        # 1. Vind het unieke ID van de rij die je hebt aangepast (op basis van de weergave)
        row_idx = int(row_index_str)
        rij_id = view_df.iloc[row_idx]["ID"]
        
        # 2. Loop door de kolommen die in deze specifieke rij zijn aangepast
        for col_name, new_val in changed_cols.items():
            
            # Als de checkbox is veranderd, vertaal dit naar de tekst-kolom "Uit voorraad"
            if col_name == "Uit voorraad_bool":
                status = "Ja" if new_val else "Nee"
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == rij_id, "Uit voorraad"] = status
            
            # Als de locatie is veranderd, update alleen de locatie voor dit ID
            elif col_name == "Locatie":
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == rij_id, "Locatie"] = str(new_val)

    # Sla op en ververs de app
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
