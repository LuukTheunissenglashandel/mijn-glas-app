import streamlit as st
import pandas as pd
import uuid
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"

# Kolommen
ZICHTBARE_KOLOMMEN = ["Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Locatie"]

st.set_page_config(layout="wide", page_title="Glas Voorraad Cloud")

# --- FUNCTIES ---

def get_connection():
    """Maakt verbinding met Google Sheets"""
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data():
    conn = get_connection()
    # We lezen de sheet. ttl=0 betekent: niet cachen, altijd verse data halen.
    try:
        df = conn.read(worksheet="Blad1", ttl=0) # Zorg dat je tabblad in Google Sheets 'Blad1' heet (of Sheet1)
    except:
        # Als de sheet leeg is of niet bestaat, maak een lege dataframe
        df = pd.DataFrame(columns=["ID"] + ZICHTBARE_KOLOMMEN)

    # Zorg dat ID bestaat
    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        
    # Zorg dat alle kolommen bestaan en strings zijn (voorkomt crashes)
    for kolom in ZICHTBARE_KOLOMMEN:
        if kolom not in df.columns:
            df[kolom] = ""
    
    # Maak alles tekst (behalve ID) om gedoe met getallen in Google Sheets te voorkomen
    df = df.fillna("")
    return df

def sla_data_op(df):
    conn = get_connection()
    # Schrijf terug naar Google Sheets
    conn.update(worksheet="Blad1", data=df)
    st.cache_data.clear() # Cache legen zodat we zeker weten dat we de nieuwe data zien

def check_wachtwoord():
    if "ingelogd" not in st.session_state:
        st.session_state.ingelogd = False

    if not st.session_state.ingelogd:
        col1, col2, col3 = st.columns([1,1,1])
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

    st.title("☁️ Glas Voorraad (Google Sheets)")

    # 1. Data Laden
    # Omdat Google Sheets iets trager is dan een lokaal bestand, tonen we een ladertje
    with st.spinner('Verbinding maken met Google...'):
        df = laad_data()

    # 2. Sidebar
    with st.sidebar:
        st.header("📥 Import")
        uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
        if uploaded_file:
            if st.button("Toevoegen aan Cloud"):
                try:
                    nieuwe_data = pd.read_excel(uploaded_file)
                    nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns] 
                    nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]

                    if "Locatie" not in nieuwe_data.columns:
                        nieuwe_data["Locatie"] = ""
                    
                    # Alles naar string converteren voor veiligheid
                    nieuwe_data = nieuwe_data.astype(str)
                        
                    df = pd.concat([df, nieuwe_data], ignore_index=True)
                    
                    # Kolommen netjes maken
                    alle_kolommen = ["ID"] + ZICHTBARE_KOLOMMEN
                    for k in alle_kolommen:
                        if k not in df.columns:
                            df[k] = ""
                    df = df[alle_kolommen]
                    
                    sla_data_op(df)
                    st.success("✅ Opgeslagen in Google Sheets!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fout: {e}")

    # 3. LAYOUT
    col_search, col_buttons = st.columns([4, 1]) 
    with col_search:
        zoekterm = st.text_input("🔍 Zoek in voorraad", placeholder="Typ ordernummer, afmeting of locatie...")
    button_placeholder = col_buttons.empty()

    # 4. TABEL
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
    if zoekterm:
        gb.configure_grid_options(quickFilterText=zoekterm)

    gb.configure_default_column(editable=False, groupable=True, value=True, enableRowGroup=True, filterable=True, sortable=True, resizable=True)
    gb.configure_column("Aantal", checkboxSelection=True, headerCheckboxSelection=True)
    gb.configure_column("Omschrijving", width=350)
    gb.configure_column("Order", width=150)
    gb.configure_column("Locatie", editable=True, width=130, cellStyle={'backgroundColor': '#e6f3ff'}) 
    gb.configure_column("ID", hide=True)
    gb.configure_selection('multiple', use_checkbox=True)
    
    gridOptions = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED, 
        fit_columns_on_grid_load=False,
        theme='alpine',
        height=600,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False
    )

    updated_df = grid_response['data']
    selected_rows = grid_response['selected_rows']

    if isinstance(selected_rows, pd.DataFrame):
        selected_rows = selected_rows.to_dict('records')
    elif selected_rows is None:
        selected_rows = []

    # Check op wijzigingen (Locatie typen) en direct opslaan naar Google
    if not df.astype(str).equals(updated_df.astype(str)):
        try:
             # We updaten de lokale dataframe eerst
             changed = False
             for index, row in updated_df.iterrows():
                 mask = df['ID'] == row['ID']
                 if mask.any():
                     for col in ZICHTBARE_KOLOMMEN:
                         if str(df.loc[mask, col].values[0]) != str(row[col]):
                             df.loc[mask, col] = row[col]
                             changed = True
             
             if changed:
                 sla_data_op(df)
                 st.toast("Wijziging opgeslagen in Cloud!", icon="☁️")
        except Exception as e:
            st.warning(f"Opslaan niet gelukt: {e}")

    # 5. VERWIJDEREN
    if 'verwijder_bevestiging' not in st.session_state:
        st.session_state['verwijder_bevestiging'] = False

    if len(selected_rows) > 0:
        with button_placeholder.container():
            st.write("") 
            st.write("") 
            if st.button(f"🗑️ Verwijder ({len(selected_rows)})", type="primary", key="del_btn_top"):
                st.session_state['verwijder_bevestiging'] = True

            if st.session_state['verwijder_bevestiging']:
                st.error("Cloud update: Weet je het zeker?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("JA"):
                        with st.spinner("Bezig met verwijderen uit Google Sheets..."):
                            ids = [rij['ID'] for rij in selected_rows]
                            # We halen vers op om conflicten te voorkomen
                            conn = get_connection()
                            vers_df = conn.read(worksheet="Blad1", ttl=0)
                            
                            # Filteren
                            new_data = vers_df[~vers_df['ID'].isin(ids)]
                            
                            # Opslaan
                            conn.update(worksheet="Blad1", data=new_data)
                            st.cache_data.clear()
                            
                            st.session_state['verwijder_bevestiging'] = False
                            st.success("Verwijderd uit Cloud!")
                            st.rerun()
                with c2:
                    if st.button("NEE"):
                        st.session_state['verwijder_bevestiging'] = False
                        st.rerun()
    else:
        st.session_state['verwijder_bevestiging'] = False
        with button_placeholder.container():
             st.write("")
             st.write("")
             st.button("🗑️ Verwijder", disabled=True, key="del_btn_disabled")

if __name__ == "__main__":
    main()