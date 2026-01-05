import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os
from datetime import datetime
import pytz
from typing import Optional, List, Dict, Any, Tuple
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
ROWS_PER_PAGE = 25

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
    success_msg: str = ""
    selected_ids: set = field(default_factory=set)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list) 
    total_count: int = 0

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
    
    def get_paged_data(self, zoekterm: str = "", page: int = 0, limit: int = 25) -> Tuple[List[Dict[str, Any]], int]:
        with self._handle_errors("ophalen data"):
            start = page * limit
            end = start + limit - 1
            query = self.client.table(self.table).select("*", count="exact")
            if zoekterm:
                search_filter = f"order_nummer.ilike.%{zoekterm}%,omschrijving.ilike.%{zoekterm}%,locatie.ilike.%{zoekterm}%"
                query = query.or_(search_filter)
            result = query.order("id").range(start, end).execute()
            return result.data, result.count

    def get_all_matching_ids(self, zoekterm: str = "") -> List[int]:
        query = self.client.table(self.table).select("id")
        if zoekterm:
            search_filter = f"order_nummer.ilike.%{zoekterm}%,omschrijving.ilike.%{zoekterm}%,locatie.ilike.%{zoekterm}%"
            query = query.or_(search_filter)
        result = query.execute()
        return [r['id'] for r in result.data]

    def get_sum_aantal_for_ids(self, ids: List[int]) -> int:
        if not ids: return 0
        result = self.client.table(self.table).select("aantal").in_("id", ids).execute()
        return sum(int(r['aantal'] or 0) for r in result.data)

    def get_all_for_backup(self) -> List[Dict[str, Any]]:
        res = self.client.table(self.table).select("*").execute()
        return res.data
    
    def insert_one(self, record: Dict[str, Any]):
        with self._handle_errors("rij toevoegen"):
            self.client.table(self.table).insert(record).execute()
    
    def bulk_update_location(self, ids: List[int], nieuwe_locatie: str):
        with self._handle_errors("locatie update"):
            self.client.table(self.table).update({"locatie": nieuwe_locatie}).in_("id", ids).execute()
    
    def bulk_update_fields(self, updates: List[Dict[str, Any]]):
        with self._handle_errors("velden update"):
            self.client.table(self.table).upsert(updates).execute()
    
    def delete_many(self, ids: List[int]):
        with self._handle_errors("verwijderen"):
            self.client.table(self.table).delete().in_("id", ids).execute()

    def restore_backup(self, backup_data: List[Dict[str, Any]]):
        with self._handle_errors("undo uitvoeren"):
            current = self.client.table(self.table).select("id").execute()
            all_ids = [r['id'] for r in current.data]
            if all_ids:
                self.client.table(self.table).delete().in_("id", all_ids).execute()
            if backup_data:
                clean_data = [{k: v for k, v in r.items() if k != 'Selecteren'} for r in backup_data]
                self.client.table(self.table).insert(clean_data).execute()

# =============================================================================
# 3. SERVICE LAAG
# =============================================================================

class VoorraadService:
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo

    def laad_data(self, zoekterm: str, page: int) -> Tuple[pd.DataFrame, int]:
        @st.cache_data(ttl=600)
        def _cached_fetch(zoek: str, p: int):
            return self.repo.get_paged_data(zoek, p, ROWS_PER_PAGE)
        
        data, count = _cached_fetch(zoekterm, page)
        kolommen = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
        if not data: return pd.DataFrame(columns=kolommen), 0
        df = pd.DataFrame(data)
        df["Selecteren"] = df["id"].apply(lambda x: x in st.session_state.app_state.selected_ids)
        for col in kolommen:
            if col not in df.columns: df[col] = None
        return df[kolommen], count

    def trigger_mutation(self):
        st.cache_data.clear()

    def push_undo_state(self):
        full_data = self.repo.get_all_for_backup()
        amsterdam_tz = pytz.timezone("Europe/Amsterdam")
        nu = datetime.now(amsterdam_tz).strftime("%d-%m-%Y %H:%M:%S")
        st.session_state.app_state.undo_stack.append({"data": full_data, "tijd": nu})
        if len(st.session_state.app_state.undo_stack) > 10:
            st.session_state.app_state.undo_stack.pop(0)

# =============================================================================
# 4. UI HELPER FUNCTIES & CACHING
# =============================================================================

@st.cache_data
def get_base64_logo(img_path: str) -> str:
    if os.path.exists(img_path):
        with open(img_path, "rb") as f: return base64.b64encode(f.read()).decode()
    return ""

@st.cache_data(ttl=300)
def get_cached_sum(_repo, ids: tuple) -> int:
    if not ids: return 0
    return _repo.get_sum_aantal_for_ids(list(ids))

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
        </style>
    """, unsafe_allow_html=True)

def render_header(logo_b64: str):
    h1, h2 = st.columns([7, 2])
    with h1:
        st.markdown(f'<div class="header-left"><img src="data:image/webp;base64,{logo_b64}"><h1>Voorraad glas</h1></div>', unsafe_allow_html=True)
    with h2:
        if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
            st.session_state.clear()
            st.rerun()

def sync_selections():
    if "main_editor" in st.session_state:
        edited_rows = st.session_state.main_editor.get("edited_rows", {})
        df = st.session_state.app_state.mijn_data
        for idx_str, changes in edited_rows.items():
            if "Selecteren" in changes:
                row_id = df.iloc[int(idx_str)]["id"]
                if changes["Selecteren"]:
                    st.session_state.app_state.selected_ids.add(row_id)
                else:
                    st.session_state.app_state.selected_ids.discard(row_id)

# =============================================================================
# 5. MAIN FRAGMENT (VOOR SNELLE INTERACTIE)
# =============================================================================

@st.fragment
def render_interactive_section(service):
    state = st.session_state.app_state
    
    # Zoekbalk
    c1, c2 = st.columns([7, 2])
    zoek_val = c1.text_input("Zoeken", value=state.zoek_veld, placeholder="🔍 Zoek...", label_visibility="collapsed")
    if zoek_val != state.zoek_veld:
        state.zoek_veld = zoek_val; state.current_page = 0; st.rerun()
    if c2.button("WISSEN", use_container_width=True) and state.zoek_veld:
        state.zoek_veld = ""; state.current_page = 0; st.rerun()

    state.mijn_data, state.total_count = service.laad_data(state.zoek_veld, state.current_page)
    
    # PERFORMANCE OPTIMALISATIE: Bereken de som lokaal voor de huidige pagina, 
    # gebruik cache voor ID's buiten de huidige weergave.
    current_ids = set(state.mijn_data['id'].tolist())
    selected_on_page = state.selected_ids.intersection(current_ids)
    selected_off_page = state.selected_ids.difference(current_ids)
    
    sum_on_page = state.mijn_data[state.mijn_data['id'].isin(selected_on_page)]['aantal'].fillna(0).astype(int).sum()
    sum_off_page = get_cached_sum(service.repo, tuple(sorted(list(selected_off_page))))
    
    totaal_ruiten_geselecteerd = sum_on_page + sum_off_page
    sel_suffix = f" ({totaal_ruiten_geselecteerd})" if totaal_ruiten_geselecteerd > 0 else ""

    actie_houder = st.container()
    
    c_sel1, c_sel2 = st.columns([1, 1])
    if c_sel1.button(f"✅ ALLES SELECTEREN{sel_suffix}", use_container_width=True):
        all_ids = service.repo.get_all_matching_ids(state.zoek_veld)
        state.selected_ids.update(all_ids); st.rerun()
    if c_sel2.button(f"⬜ ALLES DESELECTEREN{sel_suffix}", use_container_width=True):
        state.selected_ids.clear(); st.rerun()

    st.data_editor(
        state.mijn_data,
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
            "id": None,
            "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", width="small"),
            "breedte": st.column_config.NumberColumn("Breedte", width="small"),
            "hoogte": st.column_config.NumberColumn("Hoogte", width="small")
        },
        hide_index=True, use_container_width=True, key="main_editor", height=500, disabled=["id"],
        on_change=sync_selections
    )

    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        db_updates = []
        for idx_str, changes in edits.items():
            clean_changes = {k: v for k, v in changes.items() if k != "Selecteren"}
            if clean_changes:
                row_id = state.mijn_data.iloc[int(idx_str)]["id"]
                db_updates.append({"id": int(row_id), **clean_changes})
        if db_updates:
            service.push_undo_state(); service.repo.bulk_update_fields(db_updates); service.trigger_mutation(); st.rerun()

    num_pages = max(1, (state.total_count - 1) // ROWS_PER_PAGE + 1)
    if num_pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")
        if p1.button("⬅️ VORIGE", disabled=state.current_page == 0, use_container_width=True):
            state.current_page -= 1; st.rerun()
        p2.markdown(f"<p style='text-align:center; margin:0;'>Pagina {state.current_page + 1} van {num_pages}</p>", unsafe_allow_html=True)
        if p3.button("VOLGENDE ➡️", disabled=state.current_page == num_pages - 1, use_container_width=True):
            state.current_page += 1; st.rerun()

    if state.selected_ids:
        with actie_houder:
            b1, b2 = st.columns(2)
            btn_text = "❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN"
            if b1.button(btn_text, use_container_width=True):
                state.show_location_grid = not state.show_location_grid; st.rerun()
            if b2.button(f"🗑️ MEEGENOMEN ({totaal_ruiten_geselecteerd})", use_container_width=True):
                service.push_undo_state(); service.repo.delete_many(list(state.selected_ids))
                state.selected_ids.clear(); service.trigger_mutation(); st.rerun()
            
            if state.show_location_grid:
                st.divider()
                act_col1, act_col2, act_col3 = st.columns([2, 1, 1])
                if act_col1.button(f"🚀 VERPLAATS NAAR {state.bulk_loc}", type="primary", use_container_width=True):
                    service.push_undo_state(); service.repo.bulk_update_location(list(state.selected_ids), state.bulk_loc)
                    service.trigger_mutation(); state.show_location_grid = False; st.rerun()
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

# =============================================================================
# 6. APP EXECUTION
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

    # De interactieve sectie in een fragment voor performance
    render_interactive_section(service)

    # Footer
    st.divider()
    footer_col1, footer_col2 = st.columns([1, 1])
    with footer_col1:
        st.subheader("➕ Nieuwe ruit toevoegen")
        if state.success_msg: st.success(state.success_msg); state.success_msg = ""
        with st.form("nieuw_item_form", clear_on_submit=True):
            f1, f2 = st.columns(2)
            n_loc = f1.selectbox("Locatie", options=LOCATIE_OPTIES)
            n_aantal = f2.number_input("Aantal", min_value=1, value=1)
            f3, f4 = st.columns(2)
            n_breedte = f3.number_input("Breedte (mm)", min_value=0, value=0)
            n_hoogte = f4.number_input("Hoogte (mm)", min_value=0, value=0)
            n_order = st.text_input("Ordernummer", placeholder="Letters en cijfers toegestaan...")
            n_omschrijving = st.text_input("Omschrijving", placeholder="Type glas...")
            if st.form_submit_button("TOEVOEGEN", use_container_width=True):
                service.push_undo_state()
                service.repo.insert_one({
                    "locatie": n_loc, "aantal": n_aantal, "breedte": n_breedte if n_breedte > 0 else None,
                    "hoogte": n_hoogte if n_hoogte > 0 else None, "order_nummer": str(n_order).strip() if n_order else None,
                    "omschrijving": str(n_omschrijving).strip() if n_omschrijving else None
                })
                service.trigger_mutation(); state.success_msg = "Gelukt!"; st.rerun()

    with footer_col2:
        st.subheader("📥 Bulk & Systeem")
        uploaded_file = st.file_uploader("Bulk import Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed")
        if uploaded_file and st.button("🚀 IMPORT STARTEN", use_container_width=True):
            try:
                df_import = pd.read_excel(uploaded_file)
                df_import.columns = [str(c).lower().strip().replace(' ', '_') for c in df_import.columns]
                if 'order' in df_import.columns: df_import = df_import.rename(columns={'order': 'order_nummer'})
                db_cols = ["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"]
                final_import = df_import[[c for c in df_import.columns if c in db_cols]]
                service.push_undo_state(); service.repo.bulk_update_fields(final_import.to_dict('records'))
                service.trigger_mutation(); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")
        
        if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
            service.trigger_mutation(); st.rerun()
        if state.undo_stack:
            laatste = state.undo_stack[-1]
            if st.button(f"⏪ TERUGZETTEN (Laatste aanpassing: {laatste['tijd']})", use_container_width=True):
                state_to_restore = state.undo_stack.pop(); service.repo.restore_backup(state_to_restore['data'])
                service.trigger_mutation(); st.success("Versie hersteld!"); st.rerun()

if __name__ == "__main__": main()
