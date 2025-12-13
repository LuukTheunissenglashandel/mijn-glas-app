import streamlit as st
import pandas as pd
import uuid
import traceback # Nodig om de fout te kunnen zien
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
ZICHTBARE_KOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 0.5rem; padding-bottom: 5rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    div.stButton > button[key="real_del_btn"] { background-color: #28a745; color: white; border-radius: 5px; height: 50px; width: 100%; }
    div.stButton > button[key="cancel_del_btn"] { background-color: #dc3545; color: white; border-radius: 5px; height: 50px; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    """Zeer veilige functie om naar hele getallen te converteren"""
    try:
        if val is None:
            return ""
        # Maak er eerst een string van, haal spaties weg
        s_val = str(val).strip()
        if s_val == "" or s_val.lower() == "nan" or s_val.lower() == "none":
            return ""
        # Vervang komma door punt
        s_val = s_val.replace(',', '.')
        # Converteer naar float en dan naar int (bijv 5.0 -> 5)
        return str(int(float(s_val)))
    except:
        # Als het echt niet lukt (bijv tekst "ca"), geef gewoon de tekst terug
        return str(val)

def laad_data():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        # Als sheet leeg is of headers missen
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + ZICHTBARE_KOLOMMEN)
    except Exception:
        return pd.DataFrame(columns=["ID"] + ZICHTBARE_KOLOMMEN)

    # Zorg dat ID kolom bestaat
    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    # Zorg dat alle kolommen bestaan
    for col in ZICHTBARE_KOLOMMEN:
        if col not in df.columns:
            df[col] = ""

    # Pas de clean_int functie toe op cijferkolommen
    for col in ["Aantal", "Spouw"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_int)
            
    # Alles naar string converteren voor AgGrid (voorkomt TypeErrors)
    return df[["ID"] + ZICHTBARE_KOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df)
    st.cache_data.clear()

# --- AUTH ---
def check_login():
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

# --- MAIN APP ---
def main():
    # Wrap alles in een try/except om de echte fout te vangen
    try:
        if not check_login():
            return

        st.title("🏭 Glas Voorraad")

        df = laad_data()

        # 1. Sidebar (Import)
        with st.sidebar:
            st.header("📥 Import")
            uploaded_file = st.file_uploader("Excel bestand (.xlsx)", type=["xlsx"])
            if uploaded_file:
                if st.button("Bevestig Upload"):
                    nieuwe_data = pd.read_excel(uploaded_file)
                    nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
                    
                    mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                    nieuwe_data = nieuwe_data.rename(columns=mapping)
                    
                    nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                    if "Locatie" not in nieuwe_data.columns:
                        nieuwe_data["Locatie"] = ""
                    
                    for col in ["Aantal", "Spouw"]:
                        if col in nieuwe_data.columns:
                            nieuwe_data[col] = nieuwe_data[col].apply(clean_int)

                    for c in ZICHTBARE_KOLOMMEN:
                        if c not in nieuwe_data.columns: nieuwe_data[c] = ""
                    
                    final_upload = nieuwe_data[["ID"] + ZICHTBARE_KOLOMMEN].astype(str)
                    df_combined = pd.concat([df, final_upload], ignore_index=True)
                    sla_data_op(df_combined)
                    st.rerun()

        # 2. Zoeken & Knoppen
        col_search, col_buttons = st.columns([3, 1])
        with col_search:
            zoekterm = st.text_input("🔍", placeholder="Zoek...", label_visibility="collapsed")
        btn_place = col_buttons.empty()

        # 3. Tabel Configuratie
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=50)

        if zoekterm:
            gb.configure_grid_options(quickFilterText=zoekterm)

        gb.configure_default_column(
            editable=False, 
            filterable=True, 
            sortable=True, 
            resizable=True, 
            wrapText=True, 
            autoHeight=True
        )

        # Kolommen
        gb.configure_column("Locatie", 
                            editable=True, 
                            width=130, 
                            checkboxSelection=True,
                            headerCheckboxSelection=True,
                            pinned='left', 
                            cellStyle={'backgroundColor': '#e6f3ff'})

        for col in ["Aantal", "Breedte", "Hoogte", "Spouw"]:
            gb.configure_column(col, width=80)

        gb.configure_column("Omschrijving", width=300)
        gb.configure_column("ID", hide=True)

        # Checkbox uit in algemene selectie, want we hebben hem bij Locatie gezet
        gb.configure_selection(selection_mode="multiple", use_checkbox=False)

        gridOptions = gb.build()

        # De Tabel
        grid_response = AgGrid(
            df,
            gridOptions=gridOptions,
            # Let op: update_mode versimpeld om crash te voorkomen
            update_mode=GridUpdateMode.MODEL_CHANGED, 
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            fit_columns_on_grid_load=True,
            theme='alpine',
            height=750,
            allow_unsafe_jscode=True,
            key='glas_grid_debug'
        )

        # Opslaan bij wijziging
        updated_df = grid_response['data']
        # Kleine check of data geldig is voor opslaan
        if not df.equals(updated_df):
            sla_data_op(updated_df)

        # 4. Verwijder Logica
        selected_rows = grid_response['selected_rows']

        # Veilige conversie van selectie
        if selected_rows is None:
            selected_rows = []
        elif isinstance(selected_rows, pd.DataFrame):
            selected_rows = selected_rows.to_dict('records')

        if len(selected_rows) > 0:
            with btn_place.container():
                if st.button(f"🗑️ Verwijder ({len(selected_rows)})", type="primary"):
                    st.session_state.ask_del = True
                    
                if st.session_state.get('ask_del'):
                    st.warning("Definitief verwijderen?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("JA", key="real_del_btn"):
                            ids_to_del = [r['ID'] for r in selected_rows]
                            full_df = laad_data()
                            new_df = full_df[~full_df['ID'].isin(ids_to_del)]
                            sla_data_op(new_df)
                            st.session_state.ask_del = False
                            st.rerun()
                    with c2:
                        if st.button("NEE", key="cancel_del_btn"):
                            st.session_state.ask_del = False
                            st.rerun()
                            
    except Exception as e:
        # HIER wordt de echte fout getoond als er iets misgaat
        st.error("Er is een fout opgetreden:")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
