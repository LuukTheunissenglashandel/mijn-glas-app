import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os
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
    # Verbetering 4 & 5: Global selections en Undo stack
    selected_ids: set = field(default_factory=set)
    undo_stack: List[List[Dict[str, Any]]] = field(default_factory=list) 
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
    
    # Verbetering 2: Server-side paginatie & Verbetering 3: Cache-vriendelijke fetch
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

    def get_all_for_backup(self) -> List[Dict[str, Any]]:
        """Haalt volledige dataset op enkel voor de undo-stack bij mutaties."""
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
            # Veiligere methode: verwijder huidige en voeg backup in (eenvoudigste vorm van restore)
            current = self.client.table(self.table).select("id").execute()
            all_ids = [r['id'] for r in current.data]
            if all_ids:
                self.client.table(self.table).delete().in_("id", all_ids).execute()
            if backup_data:
                # Verwijder eventuele UI-kolommen
                clean_data = [{k: v for k, v in r.items() if k != 'Selecteren'} for r in backup_data]
                self.client.table(self.table).insert(clean_data).execute()

# =============================================================================
# 3. SERVICE LAAG (Met Caching)
# =============================================================================

class VoorraadService:
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo

    def laad_data(self, zoekterm: str, page: int) -> Tuple[pd.DataFrame, int]:
        # Verbetering 3: Gebruik Streamlit caching voor de fetch
        @st.cache_data(ttl=600)
        def _cached_fetch(zoek: str, p: int):
            return self.repo.get_paged_data(zoek, p, ROWS_PER_PAGE)
        
        data, count = _cached_fetch(zoekterm, page)
        
        kolommen = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
        if not data:
            return pd.DataFrame(columns=kolommen), 0
            
        df = pd.DataFrame(data)
        # Verbetering 4: Map global selections naar de DataFrame
        df["Selecteren"] = df["id"].apply(lambda x: x in st.session_state.app_state.selected_ids)
        
        for col in kolommen:
            if col not in df.columns: df[col] = None
        return df[kolommen], count

    def trigger_mutation(self):
        """Maakt de cache leeg na een wijziging."""
        st.cache_data.clear()

    def push_undo_state(self):
        """Verbetering 5: Voeg huidige staat toe aan undo stack voor wijziging."""
        full_data = self.repo.get_all_for_backup()
        st.session_state.app_state.undo_stack.append(full_data)
        # Limiteer stack tot 10 om geheugen te sparen
        if len(st.session_state.app_state.undo_stack) > 10:
            st.session_state.app_state.undo_stack.pop(0)

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
    """Update de globale selectie-set op basis van de editor state."""
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
# 5. MAIN
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

    # Zoekbalk
    c1, c2 = st.columns([7, 2])
    zoek_val = c1.text_input("Zoeken", value=state.zoek_veld, placeholder="🔍 Zoek...", label_visibility="collapsed")
    if zoek_val != state.zoek_veld:
        state.zoek_veld = zoek_val
        state.current_page = 0
        st.rerun()
    if c2.button("WISSEN", use_container_width=True) and state.zoek_veld:
        state.zoek_veld = ""; state.current_page = 0; st.rerun()

    # Data laden
    state.mijn_data, state.total_count = service.laad_data(state.zoek_veld, state.current_page)

    # Batch acties container
    actie_houder = st.container()
    
    # Selectie knoppen
    c_sel1, c_sel2 = st.columns([1, 1])
    if c_sel1.button("✅ ALLES SELECTEREN (HUIDIGE PAGINA)", use_container_width=True):
        for rid in state.mijn_data["id"]: state.selected_ids.add(rid)
        st.rerun()
    if c_sel2.button("⬜ ALLES DESELECTEREN", use_container_width=True):
        state.selected_ids.clear()
        st.rerun()

    # Tabel met Verbetering 4: Selection Sync
    edited_df = st.data_editor(
        state.mijn_data,
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
            "id": None,
            "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", width="small"),
        },
        hide_index=True, use_container_width=True, key="main_editor", height=500, disabled=["id"],
        on_change=sync_selections
    )

    # Verwerk rij-bewerkingen (Inline updates)
    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        db_updates = []
        for idx_str, changes in edits.items():
            clean_changes = {k: v for k, v in changes.items() if k != "Selecteren"}
            if clean_changes:
                row_id = state.mijn_data.iloc[int(idx_str)]["id"]
                db_updates.append({"id": int(row_id), **clean_changes})
        
        if db_updates:
            service.push_undo_state()
            service.repo.bulk_update_fields(db_updates)
            service.trigger_mutation()
            st.rerun()

    # Paginering UI
    num_pages = max(1, (state.total_count - 1) // ROWS_PER_PAGE + 1)
    if num_pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("⬅️ VORIGE", disabled=state.current_page == 0):
            state.current_page -= 1; st.rerun()
        p2.markdown(f"<p style='text-align:center;'>Pagina {state.current_page + 1} van {num_pages} ({state.total_count} records)</p>", unsafe_allow_html=True)
        if p3.button("VOLGENDE ➡️", disabled=state.current_page == num_pages - 1):
            state.current_page += 1; st.rerun()

    # Batch Acties (Locatie/Verwijderen)
    selected_data = state.mijn_data[state.mijn_data["id"].isin(state.selected_ids)]
    if not selected_data.empty:
        with actie_houder:
            st.info(f"{len(state.selected_ids)} items geselecteerd over alle pagina's.")
            b1, b2 = st.columns(2)
            if b1.button("📍 LOCATIE WIJZIGEN", use_container_width=True):
                state.show_location_grid = not state.show_location_grid
                st.rerun()
            
            if b2.button(f"🗑️ MEEGENOMEN ({int(selected_data['aantal'].sum())})", use_container_width=True):
                service.push_undo_state()
                service.repo.delete_many(list(state.selected_ids))
                state.selected_ids.clear()
                service.trigger_mutation()
                st.success("Items verwijderd"); st.rerun()

            if state.show_location_grid:
                # (Locatie grid logica blijft gelijk, maar roept service.trigger_mutation() aan)
                loc = st.selectbox("Nieuwe locatie", LOCATIE_OPTIES, index=LOCATIE_OPTIES.index(state.bulk_loc))
                if st.button(f"Bevestig verplaatsing naar {loc}", type="primary"):
                    service.push_undo_state()
                    service.repo.bulk_update_location(list(state.selected_ids), loc)
                    service.trigger_mutation()
                    state.show_location_grid = False
                    st.rerun()

    # Footer formulieren (Toevoegen / Import)
    st.divider()
    f1, f2 = st.columns(2)
    with f1:
        with st.form("add_form", clear_on_submit=True):
            st.subheader("➕ Toevoegen")
            n_order = st.text_input("Ordernummer")
            n_loc = st.selectbox("Locatie", LOCATIE_OPTIES)
            if st.form_submit_button("TOEVOEGEN", use_container_width=True):
                service.push_undo_state()
                service.repo.insert_one({"order_nummer": n_order, "locatie": n_loc, "aantal": 1})
                service.trigger_mutation()
                st.rerun()
    
    with f2:
        st.subheader("📥 Bulk")
        if st.button("🔄 DATA VERVERSEN", use_container_width=True):
            service.trigger_mutation(); st.rerun()
        
        # Undo knop met Stack
        if state.undo_stack:
            if st.button(f"⏪ UNDO (Stack: {len(state.undo_stack)})", use_container_width=True, type="secondary"):
                last_state = state.undo_stack.pop()
                service.repo.restore_backup(last_state)
                service.trigger_mutation()
                st.success("Laatste actie ongedaan gemaakt!")
                st.rerun()

if __name__ == "__main__": main()
