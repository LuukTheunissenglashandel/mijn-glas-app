import streamlit as st
import pandas as pd
import uuid
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas5831"
ZICHTBARE_KOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- CSS: Layout & Kleuren ---
st.markdown("""
    <style>
    /* Witruimte bovenin minimaliseren */
    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0rem;
    }
    /* Menu's verbergen */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Gekleurde knoppen */
    div.stButton > button[key="real_del_btn"] { background-color: #28a745; color: white; border-radius: 5px; height: 50px; width: 100%; }
    div.stButton > button[key="cancel_del_btn"] { background-color: #dc3545; color: white; border-radius: 5px; height: 50px; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    """Zorgt dat waarden altijd hele cijfers zijn (geen 5.0 maar 5)"""
    try:
        if pd.isna(val) or str(val).strip() == "":
            return ""
        # Eerst naar float (voor '15.0'), dan naar int, dan naar string
        getal = float(str(val).replace(',', '.'))
        return str(int(getal))
    except:
        return str(val)

def laad_data():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df.empty:
            return pd.DataFrame(columns=["ID"] + ZICHTBARE_KOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + ZICHTBARE_KOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    # Kolommen aanvullen
    for col in ZICHTBARE_KOLOMMEN:
        if col not in df.columns:
            df[col] = ""

    # Opschonen van cijfers (Aantal én Spouw)
    for col in ["Aantal", "Spouw"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_int)
            
    return df[["ID"] + ZICHTBARE_KOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df)
    st.cache_data.clear()

# --- AUTH ---
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
    st.stop()

# --- MAIN APP ---
st.title("🏭 Glas Voorraad")

df = laad_data()

# 1. Sidebar (Import)
with st.sidebar:
    st.header("📥 Import")
    uploaded_file = st.file_uploader("Excel bestand (.xlsx)", type=["xlsx"])
    if uploaded_file:
        try:
            if st.button("Bevestig Upload"):
                nieuwe_data = pd.read_excel(uploaded_file)
                nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
                
                # Mapping
                mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                nieuwe_data = nieuwe_data.rename(columns=mapping)
                
                nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                if "Locatie" not in nieuwe_data.columns:
                    nieuwe_data["Locatie"] = ""
                
                # Opschonen cijfers in import
                for col in ["Aantal", "Spouw"]:
                    if col in nieuwe_data.columns:
                        nieuwe_data[col] = nieuwe_data[col].apply(clean_int)

                # Alleen relevante kolommen
                for c in ZICHTBARE_KOLOMMEN:
                    if c not in nieuwe_data.columns: nieuwe_data[c] = ""
                
                final_upload = nieuwe_data[["ID"] + ZICHTBARE_KOLOMMEN].astype(str)
                df_combined = pd.concat([df, final_upload], ignore_index=True)
                sla_data_op(df_combined)
                st.success("✅ Geüpload!")
                st.rerun()
        except Exception as e:
            st.error(f"Fout: {e}")

# 2. Zoeken & Knoppen
col_search, col_buttons = st.columns([3, 1])
with col_search:
    zoekterm = st.text_input("🔍", placeholder="Zoek op order, afmeting...", label_visibility="collapsed")
btn_place = col_buttons.empty()

# 3. Tabel Configuratie
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=50) # Meer regels per pagina

if zoekterm:
    gb.configure_grid_options(quickFilterText=zoekterm)

# Algemeen
gb.configure_default_column(
    editable=False, 
    filterable=True, 
    sortable=True, 
    resizable=True, 
    wrapText=True, 
    autoHeight=True
)

# --- KOLOMMEN ---
# We zetten het vinkje nu expliciet op de Locatie kolom
gb.configure_column("Locatie", 
                    editable=True, 
                    width=130, 
                    checkboxSelection=True,  # HIER ZIT HET VINKJE NU
                    headerCheckboxSelection=True,
                    pinned='left', # Zet deze kolom vast aan de linkerkant
                    cellStyle={'backgroundColor': '#e6f3ff'})

# Smalle kolommen
for col in ["Aantal", "Breedte", "Hoogte", "Spouw"]:
    gb.configure_column(col, width=80)

gb.configure_column("Omschrijving", width=300)
gb.configure_column("ID", hide=True)

# Selectie aanzetten (belangrijk voor de delete knop)
gb.configure_selection(selection_mode="multiple", use_checkbox=False) # Checkbox zit al op Locatie

gridOptions = gb.build()

# De Tabel
grid_response = AgGrid(
    df,
    gridOptions=gridOptions,
    update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.SELECTION_CHANGED, 
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    fit_columns_on_grid_load=True,
    theme='alpine',
    height=750, # HIER IS DE HOOGTE AANGEPAST
    allow_unsafe_jscode=True,
    key='glas_grid_v2'
)

# Opslaan bij wijziging
updated_df = grid_response['data']
if not df.equals(updated_df):
    sla_data_op(updated_df)
    st.toast("Opgeslagen!")

# 4. Verwijder Logica
selected_rows = grid_response['selected_rows']

# Conversie fix
if isinstance(selected_rows, pd.DataFrame):
    selected_rows = selected_rows.to_dict('records')
elif selected_rows is None:
    selected_rows = []

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
