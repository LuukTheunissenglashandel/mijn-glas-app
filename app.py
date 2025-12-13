import streamlit as st
import pandas as pd
import uuid
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE & STYLING ---
WACHTWOORD = "glas123"
BESTANDSNAAM = "voorraad.csv"

# Volgorde aangepast: Locatie als eerste
ZICHTBARE_KOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(
    layout="wide", 
    page_title="Glas Voorraad",
    initial_sidebar_state="collapsed" # Sidebar standaard dicht voor meer ruimte
)

# CSS om knoppen kleur te geven en Streamlit menu's te verbergen
st.markdown("""
    <style>
    /* Verberg de 'Manage app' knop en het rode lijntje bovenin */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Gekleurde knoppen voor bevestiging */
    div.stButton > button:first-child[key*="bevestig_ja"] {
        background-color: #28a745;
        color: white;
        border: None;
    }
    div.stButton > button:first-child[key*="bevestig_nee"] {
        background-color: #dc3545;
        color: white;
        border: None;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---

def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
    except:
        df = pd.DataFrame(columns=["ID"] + ZICHTBARE_KOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        
    for kolom in ZICHTBARE_KOLOMMEN:
        if kolom not in df.columns:
            df[kolom] = ""
    
    return df.fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df)
    st.cache_data.clear()

def check_wachtwoord():
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
        return False
    return True

# --- MAIN ---

def main():
    if not check_wachtwoord():
        return

    st.title("🏭 Glas Voorraad")

    df = laad_data()

    # 2. Sidebar (voor import)
    with st.sidebar:
        st.header("📥 Import")
        uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
        if uploaded_file:
            if st.button("Toevoegen"):
                nieuwe_data = pd.read_excel(uploaded_file)
                nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns] 
                nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                nieuwe_data["Locatie"] = nieuwe_data.get("Locatie", "")
                df = pd.concat([df, nieuwe_data], ignore_index=True)
                df = df[["ID"] + ZICHTBARE_KOLOMMEN]
                sla_data_op(df)
                st.success("✅ Opgeslagen!")
                st.rerun()

    # 3. LAYOUT BOVEN TABEL
    col_search, col_buttons = st.columns([3, 1]) 
    with col_search:
        zoekterm = st.text_input("🔍 Zoeken", placeholder="Typ order, afmeting of locatie...")
    button_placeholder = col_buttons.empty()

    # 4. TABEL INSTELLINGEN
    gb = GridOptionsBuilder.from_dataframe(df[["ID"] + ZICHTBARE_KOLOMMEN])
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    if zoekterm:
        gb.configure_grid_options(quickFilterText=zoekterm)

    # Basis instellingen: wrapText zorgt dat volledige tekst zichtbaar is
    gb.configure_default_column(
        editable=False, filterable=True, sortable=True, resizable=True, 
        wrapText=True, autoHeight=True
    )
    
    # Kolom breedtes instellen
    gb.configure_column("Locatie", editable=True, checkboxSelection=True, headerCheckboxSelection=True, width=120, cellStyle={'backgroundColor': '#e6f3ff'})
    
    # Smalle kolommen (autoSize)
    for col in ["Aantal", "Breedte", "Hoogte", "Spouw"]:
        gb.configure_column(col, width=80) 
        
    gb.configure_column("Omschrijving", width=300)
    gb.configure_column("Order", width=120)
    gb.configure_column("ID", hide=True)

    gridOptions = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MODEL_CHANGED, 
        fit_columns_on_grid_load=True, # Alles proberen te passen op scherm
        theme='alpine',
        height=500,
        allow_unsafe_jscode=True
    )

    updated_df = grid_response['data']
    selected_rows = grid_response['selected_rows']
    
    # Opslaan bij wijziging
    if not df.astype(str).equals(updated_df.astype(str)):
        sla_data_op(updated_df)
        st.toast("Wijziging opgeslagen!", icon="✅")

    # 5. VERWIJDEREN (RECHTSBOVEN)
    if isinstance(selected_rows, pd.DataFrame):
        selected_rows = selected_rows.to_dict('records')
    elif selected_rows is None:
        selected_rows = []

    if len(selected_rows) > 0:
        with button_placeholder.container():
            st.write("")
            if st.button(f"🗑️ Verwijder ({len(selected_rows)})", type="primary"):
                st.session_state['confirm_del'] = True

            if st.session_state.get('confirm_del'):
                st.write("Zeker weten?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("JA", key="bevestig_ja"):
                        ids = [rij['ID'] for rij in selected_rows]
                        full_df = laad_data()
                        new_df = full_df[~full_df['ID'].isin(ids)]
                        sla_data_op(new_df)
                        st.session_state['confirm_del'] = False
                        st.rerun()
                with c2:
                    if st.button("NEE", key="bevestig_nee"):
                        st.session_state['confirm_del'] = False
                        st.rerun()

if __name__ == "__main__":
    main()
