import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os

# --- 1. CONFIGURATIE & INITIALISATIE ---
st.set_page_config(layout="wide", page_title="Voorraad glas", page_icon="theunissen.webp")

# Callback voor veilig wissen van zoekopdracht (voorkomt API errors)
def cb_wis_zoekveld():
    st.session_state.zoek_veld = ""

# --- 2. LOGO & STYLING ---
@st.cache_data
def get_base64_logo(img_path):
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

LOGO_B64 = get_base64_logo("theunissen.webp")

st.markdown(f"""
    <style>
    .block-container {{ 
        padding-top: 1rem; 
        padding-bottom: 5rem;
    }}
    
    #MainMenu, footer, header {{visibility: hidden;}}

    /* Verbetering scroll-gedrag: voorkomt scroll-trap in tabel */
    [data-testid="stDataEditor"] {{
        overscroll-behavior: auto !important;
    }}

    /* Header styling */
    .header-left {{
        display: flex;
        align-items: center;
        gap: 15px;
        height: 100%;
    }}
    .header-left img {{ width: 60px; height: auto; flex-shrink: 0; }}
    .header-left h1 {{ margin: 0; font-size: 1.8rem !important; font-weight: 700; white-space: nowrap; }}

    /* Mobiele optimalisatie */
    @media (max-width: 600px) {{
        .header-left img {{ width: 35px; }}
        .header-left h1 {{ font-size: 1.1rem !important; }}
    }}

    /* Exacte hoogte uitlijning voor zoekveld en buttons */
    div[data-testid="stTextInput"] > div {{
        height: 3.5em !important;
    }}
    div[data-testid="stTextInput"] div[data-baseweb="input"] {{
        height: 3.5em !important;
    }}
    div.stButton > button {{ 
        border-radius: 8px; 
        font-weight: 600; 
        height: 3.5em !important; 
        width: 100%;
        white-space: nowrap;
    }}
    
    div.stButton > button[key="logout_btn"] {{
        background-color: #ff4b4b;
        color: white;
    }}

    .action-box {{ background-color: #f8f9fa; border-radius: 10px; padding: 10px 15px; margin-bottom: 10px; border: 1px solid #dee2e6; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
WACHTWOORD = st.secrets["auth"]["password"]
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

@st.cache_resource
def init_connection():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = init_connection()

def db_query(action, table="glas_voorraad", data=None, filters=None):
    try:
        query = supabase.table(table)
        if action == "select": res = query.select("*").order("id").execute()
        elif action == "insert": res = query.insert(data).execute()
        elif action == "update": res = query.update(data).in_("id", filters).execute()
        elif action == "delete": res = query.delete().in_("id", filters).execute()
        return res.data
    except Exception as e:
        st.error(f"Database fout: {e}")
        return None

def laad_data_df():
    data = db_query("select")
    if data is None: return pd.DataFrame()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"])
    df["Selecteren"] = False
    return df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = st.query_params.get("auth") == "true"

if not st.session_state.ingelogd:
    _, col, _ = st.columns([1,2,1])
    with col:
        st.header("Inloggen")
        pw = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if pw == WACHTWOORD:
                st.session_state.ingelogd = True; st.query_params["auth"] = "true"; st.rerun()
            else: st.error("Wachtwoord onjuist")
    st.stop()

# --- 5. STATE MANAGEMENT ---
if 'mijn_data' not in st.session_state: st.session_state.mijn_data = laad_data_df()
if 'bulk_loc' not in st.session_state: st.session_state.bulk_loc = "HK"
if 'zoek_veld' not in st.session_state: st.session_state.zoek_veld = ""
for key in ['confirm_delete', 'show_location_grid']:
    if key not in st.session_state: st.session_state[key] = False

# --- 6. UI: HEADER SECTIE ---
# Behoud van de kolomstructuur voor uitlijning met de zoekbalk
h1, h2, h3 = st.columns([5, 1.5, 2])

with h1:
    st.markdown(f"""
        <div class="header-left">
            <img src="data:image/webp;base64,{LOGO_B64}">
            <h1>Voorraad glas</h1>
        </div>
    """, unsafe_allow_html=True)

with h3:
    if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
        st.session_state.ingelogd = False; st.query_params.clear(); st.rerun()

# --- 7. ZOEKEN ---
c1, c2, c3 = st.columns([5, 1.5, 2])
zoekterm = c1.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of type...", label_visibility="collapsed", key="zoek_veld")

if c2.button("ZOEKEN", use_container_width=True): 
    st.rerun()

if st.session_state.zoek_veld:
    c3.button("WISSEN", use_container_width=True, on_click=cb_wis_zoekveld)

# Filter data
view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 8. DATA EDITOR ---
actie_houder = st.container()
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
        "id": None,
        "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
    },
    hide_index=True, use_container_width=True, key="main_editor", height=500
)

# --- 9. BATCH ACTIES ---
geselecteerd = edited_df[edited_df["Selecteren"]]
ids_to_act = geselecteerd["id"].tolist()

if not geselecteerd.empty:
    with actie_houder:
        st.markdown('<div class="action-box">', unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns(2)
        
        if btn_col1.button("📍 LOCATIE WIJZIGEN" if not st.session_state.show_location_grid else "❌ SLUIT", use_container_width=True):
            st.session_state.show_location_grid = not st.session_state.show_location_grid; st.rerun()

        if not st.session_state.confirm_delete:
            if btn_col2.button("🗑️ VERWIJDEREN/MEEGENOMEN", key="delete_btn", use_container_width=True):
                st.session_state.confirm_delete = True; st.rerun()
        else:
            with btn_col2:
                st.warning("Zeker?")
                cy, cn = st.columns(2)
                if cy.button("JA", key="confirm_delete_yes", use_container_width=True):
                    db_query("delete", filters=ids_to_act)
                    st.session_state.confirm_delete = False; st.session_state.mijn_data = laad_data_df(); st.rerun()
                if cn.button("NEE", use_container_width=True):
                    st.session_state.confirm_delete = False; st.rerun()

        if st.session_state.show_location_grid:
            st.divider()
            if st.button(f"🚀 VERPLAATS NAAR {st.session_state.bulk_loc}", type="primary", use_container_width=True):
                db_query("update", data={"locatie": st.session_state.bulk_loc}, filters=ids_to_act)
                st.session_state.show_location_grid = False; st.session_state.mijn_data = laad_data_df(); st.rerun()
            cols = st.columns(5)
            for i, loc in enumerate(LOCATIE_OPTIES):
                if cols[i % 5].button(loc, key=f"g_{loc}", use_container_width=True, type="primary" if st.session_state.bulk_loc == loc else "secondary"):
                    st.session_state.bulk_loc = loc; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 10. IN-LINE EDITS ---
edits = st.session_state.main_editor.get("edited_rows", {})
if edits:
    any_actual_change = False
    for row_idx, changes in edits.items():
        clean_changes = {k: v for k, v in changes.items() if k != "Selecteren"}
        if clean_changes:
            any_actual_change = True
            row_id = [view_df.iloc[int(row_idx)]["id"]]
            db_query("update", data=clean_changes, filters=row_id)
    if any_actual_change: st.session_state.mijn_data = laad_data_df(); st.rerun()

# --- 11. BEHEER ---
st.divider()
ex1, ex2 = st.columns(2)
with ex1.expander("➕ Nieuwe Ruit"):
    with st.form("add_form", clear_on_submit=True):
        f = {
            "locatie": st.selectbox("Locatie", LOCATIE_OPTIES),
            "order_nummer": st.text_input("Ordernummer"),
            "aantal": st.number_input("Aantal", min_value=1, value=1),
            "breedte": st.number_input("Breedte", value=0),
            "hoogte": st.number_input("Hoogte", value=0),
            "omschrijving": st.text_input("Glas type"),
            "uit_voorraad": "Nee"
        }
        if st.form_submit_button("VOEG TOE", use_container_width=True):
            db_query("insert", f)
            st.session_state.mijn_data = laad_data_df(); st.rerun()

with ex2.expander("📥 Excel Import"):
    up = st.file_uploader("Excel bestand", type=["xlsx"])
    if up and st.button("UPLOAD NU", use_container_width=True):
        try:
            df_up = pd.read_excel(up)
            df_up.columns = [str(c).strip().lower() for c in df_up.columns]
            df_up = df_up.rename(columns={"order": "order_nummer"}).dropna(subset=["order_nummer"])
            df_up["uit_voorraad"] = "Nee"
            data_dict = df_up[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")
            db_query("insert", data_dict)
            st.success("Succes!"); st.session_state.mijn_data = laad_data_df(); st.rerun()
        except Exception as e: st.error(f"Fout: {e}")

if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
    st.cache_data.clear(); st.session_state.mijn_data = laad_data_df(); st.rerun()

