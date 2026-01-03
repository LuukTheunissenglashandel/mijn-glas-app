import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager

# =============================================================================
# 1. CONFIGURATIE & DATA CLASSES
# =============================================================================

st.set_page_config(layout="wide", page_title="Voorraad glas", page_icon="theunissen.webp")

WACHTWOORD = st.secrets["auth"]["password"]
LOCATIE_OPTIES = [
    "BK", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", 
    "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18", "B19", "B20", "W0",
    "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10"
]

@dataclass
class AppState:
    ingelogd: bool = False
    mijn_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    bulk_loc: str = "BK"
    zoek_veld: str = ""
    last_query: str = None
    confirm_delete: bool = False
    show_location_grid: bool = False
    current_page: int = 0
    loc_prefix: str = "B"

# =============================================================================
# 2. DATABASE REPOSITORY LAAG
# =============================================================================

class GlasVoorraadRepository:
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
        self.table = "glas_voorraad"
    
    @contextmanager
    def _handle_errors(self, operation: str):
        try:
            yield
        except Exception as e:
            st.error(f"Database fout bij {operation}: {e}")
            raise
    
    def get_data(self, zoekterm: str = "") -> Optional[List[Dict[str, Any]]]:
        with self._handle_errors("ophalen data"):
            query = self.client.table(self.table).select("*")
            if zoekterm:
                search_filter = f"order_nummer.ilike.%{zoekterm}%,omschrijving.ilike.%{zoekterm}%,locatie.ilike.%{zoekterm}%"
                query = query.or_(search_filter)
            result = query.order("id").execute()
            return result.data
    
    def insert_one(self, record: Dict[str, Any]):
        with self._handle_errors("rij toevoegen"):
            self.client.table(self.table).insert(record).execute()
    
    def bulk_update_location(self, ids: List[int], nieuwe_locatie: str) -> bool:
        with self._handle_errors("locatie update"):
            self.client.table(self.table).update({"locatie": nieuwe_locatie}).in_("id", ids).execute()
            return True
    
    def bulk_update_fields(self, updates: List[Dict[str, Any]]) -> bool:
        with self._handle_errors("velden update"):
            self.client.table(self.table).upsert(updates).execute()
            return True
    
    def delete_many(self, ids: List[int]) -> bool:
        with self._handle_errors("verwijderen"):
            self.client.table(self.table).delete().in_("id", ids).execute()
            return True

# =============================================================================
# 3. SERVICE LAAG
# =============================================================================

class VoorraadService:
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo
    
    def laad_voorraad_df(self, zoekterm: str = "") -> pd.DataFrame:
        data = self.repo.get_data(zoekterm)
        kolommen = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
        if not data:
            return pd.DataFrame(columns=kolommen)
        df = pd.DataFrame(data)
        df["Selecteren"] = False
        # Zorg dat alle kolommen aanwezig zijn, zelfs als ze leeg zijn in de DB
        for col in kolommen:
            if col not in df.columns:
                df[col] = None
        return df[kolommen]

# =============================================================================
# 4. UI HELPER FUNCTIES
# =============================================================================

@st.cache_data
def get_base64_logo(img_path: str) -> str:
    if os.path.exists(img_path):
        with open(img_path, "rb") as f: return base64.b64encode(f.read()).decode()
    return ""

def render_styling(logo_b64: str):
    st.markdown(f"""
        <style>
        .block-container {{ padding-top: 1rem; padding-bottom: 5rem; }}
        #MainMenu, footer, header {{visibility: hidden;}}
        .header-left {{ display: flex; align-items: center; gap: 15px; height: 100%; }}
        .header-left img {{ width: 60px; height: auto; }}
        .header-left h1 {{ margin: 0; font-size: 1.8rem !important; font-weight: 700; }}
        div[data-testid="stTextInput"] > div, div[data-testid="stTextInput"] div[data-baseweb="input"] {{ height: 3.5em !important; }}
        div.stButton > button {{ border-radius: 8px; font-weight: 600; height: 3.5em !important; width: 100%; }}
        div.stButton > button[key="logout_btn"] {{ background-color: #ff4b4b; color: white; }}
        .action-box {{ background-color: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 10px; border: 1px solid #dee2e6; }}
        </style>
    """, unsafe_allow_html=True)

def render_header(logo_b64: str):
    h1, h2 = st.columns([7, 2])
    with h1:
        st.markdown(f'<div class="header-left"><img src="data:image/webp;base64,{logo_b64}"><h1>Voorraad glas</h1></div>', unsafe_allow_html=True)
    with h2:
        if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
            st.session_state.app_state.ingelogd = False
            st.query_params.clear()
            st.rerun()

def update_zoekterm():
    st.session_state.app_state.zoek_veld = st.session_state.zoek_input
    st.session_state.app_state.current_page = 0

def render_zoekbalk():
    state = st.session_state.app_state
    c1, c2 = st.columns([7, 2])
    
    # Gebruik een fallback waarde als zoek_input niet in session_state staat
    zoek_val = state.zoek_veld
    
    zoekterm = c1.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of type...", 
                            label_visibility="collapsed", key="zoek_input", 
                            value=zoek_val, on_change=update_zoekterm)
    
    if state.zoek_veld:
        if c2.button("✖ WISSEN", use_container_width=True):
            state.zoek_veld = ""
            # FIX: Gebruik de key van de widget om de waarde te resetten in plaats van session_state direct
            st.session_state.zoek_input = ""
            state.current_page = 0
            st.rerun()
    else:
        if c2.button("ZOEKEN", use_container_width=True):
            state.zoek_veld = zoekterm
            state.current_page = 0
            st.rerun()
    return state.zoek_veld

def render_batch_acties(geselecteerd_df: pd.DataFrame, service: VoorraadService):
    if geselecteerd_df.empty: return
    ids_to_act = geselecteerd_df["id"].tolist()
    state = st.session_state.app_state
    st.markdown('<div class="action-box">', unsafe_allow_html=True)
    btn_col1, btn_col2 = st.columns(2)
    
    btn_text = "❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN"
    if btn_col1.button(btn_text, use_container_width=True):
        state.show_location_grid = not state.show_location_grid
        st.rerun()
        
    if not state.confirm_delete:
        if btn_col2.button("🗑️ MEEGENOMEN", use_container_width=True):
            state.confirm_delete = True
            st.rerun()
    else:
        with btn_col2:
            st.warning("Zeker?")
            cy, cn = st.columns(2)
            if cy.button("JA", use_container_width=True):
                service.repo.delete_many(ids_to_act)
                state.confirm_delete = False
                state.mijn_data = service.laad_voorraad_df(state.zoek_veld)
                st.rerun()
            if cn.button("NEE", use_container_width=True):
                state.confirm_delete = False
                st.rerun()

    if state.show_location_grid:
        st.divider()
        act_col1, act_col2, act_col3 = st.columns([2, 1, 1])
        if act_col1.button(f"🚀 VERPLAATS NAAR {state.bulk_loc}", type="primary", use_container_width=True):
            service.repo.bulk_update_location(ids_to_act, state.bulk_loc)
            state.show_location_grid = False
            state.mijn_data = service.laad_voorraad_df(state.zoek_veld)
            st.rerun()
        if act_col2.button("📍 Wijchen", use_container_width=True):
            state.loc_prefix = "W"; st.rerun()
        if act_col3.button("📍 Boxmeer", use_container_width=True):
            state.loc_prefix = "B"; st.rerun()
        
        gefilterde_locaties = [l for l in LOCATIE_OPTIES if l.startswith(state.loc_prefix) or l == "BK"]
        cols = st.columns(5)
        for i, loc in enumerate(gefilterde_locaties):
            with cols[i % 5]:
                if st.button(loc, key=f"loc_btn_{loc}", use_container_width=True, type="primary" if state.bulk_loc == loc else "secondary"):
                    state.bulk_loc = loc; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# 5. INITIALISATIE & MAIN
# =============================================================================

@st.cache_resource
def init_supabase() -> Client: 
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def main():
    if "app_state" not in st.session_state: 
        st.session_state.app_state = AppState(ingelogd=st.query_params.get("auth") == "true")
    state = st.session_state.app_state

    if not state.ingelogd:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.header("Inloggen")
            pw_input = st.text_input("Wachtwoord", type="password")
            if st.button("Inloggen", use_container_width=True):
                if pw_input == WACHTWOORD:
                    state.ingelogd = True; st.query_params["auth"] = "true"; st.rerun()
                else: st.error("Wachtwoord onjuist")
        st.stop()
    
    service = VoorraadService(GlasVoorraadRepository(init_supabase()))
    logo_b64 = get_base64_logo("theunissen.webp")
    render_styling(logo_b64)
    render_header(logo_b64)
    zoekterm = render_zoekbalk()
    
    if state.mijn_data.empty or state.last_query != zoekterm:
        state.mijn_data = service.laad_voorraad_df(zoekterm)
        state.last_query = zoekterm

    # Sync edits
    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        if edits:
            ROWS_PER_PAGE = 25
            temp_start = state.current_page * ROWS_PER_PAGE
            display_slice = state.mijn_data.iloc[temp_start : temp_start + ROWS_PER_PAGE]
            
            db_updates = []
            for row_idx_str, changes in edits.items():
                row_idx = int(row_idx_str)
                # Vind de echte ID van de rij in de hoofd-dataframe
                real_idx = display_slice.index[row_idx]
                row_id = state.mijn_data.at[real_idx, "id"]
                
                # Update de lokale dataframe onmiddellijk voor de vinkjes
                for col, val in changes.items():
                    state.mijn_data.at[real_idx, col] = val
                
                # Verzamel database updates (alles behalve de selectie-kolom)
                clean_changes = {k: v for k, v in changes.items() if k != "Selecteren"}
                if clean_changes:
                    db_updates.append({"id": int(row_id), **clean_changes})
            
            if db_updates:
                service.repo.bulk_update_fields(db_updates)
                # Herlaad alleen als er database wijzigingen waren
                state.mijn_data = service.laad_voorraad_df(state.zoek_veld)
            st.rerun()

    # Paginering
    ROWS_PER_PAGE = 25
    total_rows = len(state.mijn_data)
    num_pages = max(1, (total_rows - 1) // ROWS_PER_PAGE + 1)
    display_df = state.mijn_data.iloc[state.current_page * ROWS_PER_PAGE : (state.current_page + 1) * ROWS_PER_PAGE].copy()

    # Batch actie knoppen container
    actie_houder = st.container()
    
    # Selectie knoppen
    c_sel1, c_sel2 = st.columns([1, 1])
    if c_sel1.button("✅ ALLES SELECTEREN", use_container_width=True):
        state.mijn_data["Selecteren"] = True; st.rerun()
    if c_sel2.button("⬜ ALLES DESELECTEREN", use_container_width=True):
        state.mijn_data["Selecteren"] = False; st.rerun()

    # De Tabel
    st.data_editor(
        display_df, 
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"), 
            "id": None, 
            "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", width="small")
        }, 
        hide_index=True, use_container_width=True, key="main_editor", height=500, disabled=["id"]
    )

    # Pagina navigatie
    if num_pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("⬅️ VORIGE", use_container_width=True, disabled=state.current_page == 0):
            state.current_page -= 1; st.rerun()
        p2.markdown(f"<p style='text-align:center;'>Pagina {state.current_page + 1} van {num_pages}</p>", unsafe_allow_html=True)
        if p3.button("VOLGENDE ➡️", use_container_width=True, disabled=state.current_page == num_pages - 1):
            state.current_page += 1; st.rerun()

    with st.expander("➕ Nieuwe ruit(en) toevoegen"):
        with st.form("nieuw_item_form", clear_on_submit=True):
            f1, f2, f3 = st.columns([1, 1, 2])
            n_loc = f1.selectbox("Locatie", options=LOCATIE_OPTIES, index=0)
            n_aantal = f2.number_input("Aantal", min_value=1, value=1)
            n_order = f3.text_input("Ordernummer", placeholder="Ordernr...")
            n_omschrijving = st.text_input("Omschrijving", placeholder="Breedte x Hoogte, type glas...")
            
            if st.form_submit_button("TOEVOEGEN", use_container_width=True):
                service.repo.insert_one({
                    "locatie": n_loc, 
                    "aantal": n_aantal, 
                    "order_nummer": n_order, 
                    "omschrijving": n_omschrijving
                })
                state.mijn_data = service.laad_voorraad_df(state.zoek_veld)
                st.rerun()

    with actie_houder: 
        selected_rows = state.mijn_data[state.mijn_data["Selecteren"] == True]
        if not selected_rows.empty:
            render_batch_acties(selected_rows, service)

    st.divider()
    
    # Bulk Import & Refresh
    imp_col1, imp_col2 = st.columns([2, 1])
    with imp_col1:
        uploaded_file = st.file_uploader("📥 Bulk import Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed")
        if uploaded_file and st.button("🚀 IMPORT STARTEN", use_container_width=True):
            try:
                df_import = pd.read_excel(uploaded_file)
                service.repo.bulk_update_fields(df_import.to_dict('records'))
                state.mijn_data = service.laad_voorraad_df(state.zoek_veld); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")
    with imp_col2:
        if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
            st.cache_data.clear(); state.mijn_data = service.laad_voorraad_df(state.zoek_veld); st.rerun()

if __name__ == "__main__": main()
