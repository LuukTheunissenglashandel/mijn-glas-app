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
AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")

@dataclass
class AppState:
    ingelogd: bool = False
    mijn_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    bulk_loc: str = "BK"
    zoek_veld: str = ""
    last_query: str = None
    confirm_delete: bool = False  
    confirm_undo: bool = False    
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
            
            try:
                result = query.order("id").range(start, end).execute()
                return result.data, result.count
            except Exception as e:
                if "416" in str(e) or "Range" in str(e):
                    result = query.order("id").range(0, limit - 1).execute()
                    return result.data, result.count
                raise e

    def get_by_ids(self, ids: List[int]) -> List[Dict[str, Any]]:
        if not ids: return []
        res = self.client.table(self.table).select("*").in_("id", ids).execute()
        return res.data

    def get_all_matching_ids(self, zoekterm: str = "") -> List[int]:
        query = self.client.table(self.table).select("id")
        if zoekterm:
            query = query.or_(f"order_nummer.ilike.%{zoekterm}%,omschrijving.ilike.%{zoekterm}%,locatie.ilike.%{zoekterm}%")
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
        return self.client.table(self.table).insert(record).execute()
    
    def bulk_update_location(self, ids: List[int], nieuwe_locatie: str):
        self.client.table(self.table).update({"locatie": nieuwe_locatie}).in_("id", ids).execute()
    
    def bulk_update_fields(self, updates: List[Dict[str, Any]]):
        self.client.table(self.table).upsert(updates).execute()
    
    def delete_many(self, ids: List[int]):
        self.client.table(self.table).delete().in_("id", ids).execute()

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

    def push_undo_state(self, affected_ids: List[int]):
        records = self.repo.get_by_ids(affected_ids)
        if not records: return
        nu = datetime.now(AMSTERDAM_TZ).strftime("%H:%M:%S")
        st.session_state.app_state.undo_stack.append({"data": records, "tijd": nu})
        if len(st.session_state.app_state.undo_stack) > 10:
            st.session_state.app_state.undo_stack.pop(0)

# =============================================================================
# 4. UI HELPER FUNCTIES & CACHING
# =============================================================================

@st.cache_resource
def init_supabase() -> Client: 
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

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
        
        .custom-header {{ 
            display: flex; 
            align-items: center; 
            gap: 15px;
            margin-bottom: 30px; 
        }}
        .custom-header img {{ 
            height: 55px; 
            width: auto;
            display: block;
        }}
        .custom-header h1 {{ 
            margin: 0 !important; 
            padding: 0 !important;
            font-size: 1.85rem !important; 
            font-weight: 700;
            display: flex;
            align-items: center;
        }}
        
        div[data-testid="stTextInput"] > div, div[data-testid="stTextInput"] div[data-baseweb="input"] {{ height: 3.5em !important; }}
        div.stButton > button {{ border-radius: 8px; font-weight: 600; height: 3.5em !important; width: 100%; }}
        [data-testid="stVerticalBlock"] {{ gap: 0.4rem !important; }}
        
        @media (max-width: 640px) {{
            .custom-header h1 {{ font-size: 1.4rem !important; }}
            .custom-header img {{ height: 45px; }}
            .custom-header {{ margin-bottom: 20px; }}
        }}
        </style>
    """, unsafe_allow_html=True)

def render_header(logo_b64: str):
    h1, h2 = st.columns([7, 2], vertical_alignment="center")
    with h1:
        st.markdown(f"""
            <div class="custom-header">
                <img src="data:image/webp;base64,{logo_b64}">
                <h1>Voorraad glas</h1>
            </div>
        """, unsafe_allow_html=True)
    with h2:
        if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
            st.query_params.clear()
            st.session_state.clear()
            st.rerun()

def sync_selections():
    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        df = st.session_state.app_state.mijn_data
        for idx, changes in edits.items():
            if "Selecteren" in changes:
                rid = df.iloc[int(idx)]["id"]
                if changes["Selecteren"]: st.session_state.app_state.selected_ids.add(rid)
                else: st.session_state.app_state.selected_ids.discard(rid)

# =============================================================================
# 5. GEOPTIMALISEERD INTERACTIEF BLOK
# =============================================================================

@st.fragment
def render_main_interface(service):
    state = st.session_state.app_state
    c1, c2 = st.columns([7, 2])
    zoek_val = c1.text_input("Zoeken", value=state.zoek_veld, placeholder="🔍 Zoek...", label_visibility="collapsed")
    
    if zoek_val != state.zoek_veld:
        state.zoek_veld = zoek_val; state.current_page = 0; st.rerun(scope="fragment")
        
    if not state.zoek_veld:
        if c2.button("ZOEKEN", use_container_width=True, key="search_btn"): st.rerun(scope="fragment")
    else:
        if c2.button("WISSEN", use_container_width=True, key="clear_btn"):
            state.zoek_veld = ""; state.current_page = 0; st.rerun(scope="fragment")

    actie_houder = st.container()
    state.mijn_data, state.total_count = service.laad_data(state.zoek_veld, state.current_page)
    
    curr_ids = set(state.mijn_data['id'].tolist())
    sel_on = state.selected_ids.intersection(curr_ids)
    sum_on = state.mijn_data[state.mijn_data['id'].isin(sel_on)]['aantal'].fillna(0).astype(int).sum()
    
    @st.cache_data(ttl=300)
    def get_off_page_sum(ids_tuple):
        if not ids_tuple: return 0
        return service.repo.get_sum_aantal_for_ids(list(ids_tuple))
    
    sel_off = state.selected_ids.difference(curr_ids)
    sum_off = get_off_page_sum(tuple(sorted(list(sel_off))))
    totaal_sel = sum_on + sum_off
    suffix = f" ({totaal_sel})" if totaal_sel > 0 else ""

    if state.selected_ids:
        with actie_houder:
            b1, b2 = st.columns(2)
            if b1.button("❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN", use_container_width=True):
                state.show_location_grid = not state.show_location_grid; st.rerun(scope="fragment")
            
            with b2:
                if not state.confirm_delete:
                    if st.button(f"🗑️ MEEGENOMEN ({totaal_sel})", use_container_width=True):
                        state.confirm_delete = True; st.rerun(scope="fragment")
                else:
                    st.write("**Weet je het zeker?**")
                    mj1, mj2 = st.columns(2)
                    if mj1.button("Ja", use_container_width=True, type="primary"):
                        service.push_undo_state(list(state.selected_ids))
                        service.repo.delete_many(list(state.selected_ids))
                        state.selected_ids.clear()
                        state.confirm_delete = False
                        state.zoek_veld = ""    # Zoekopdracht wissen
                        state.current_page = 0   # Terug naar pagina 1
                        service.trigger_mutation()
                        st.rerun(scope="fragment")
                    if mj2.button("Annuleer", use_container_width=True):
                        state.confirm_delete = False; st.rerun(scope="fragment")
            
            if state.show_location_grid:
                st.divider()
                al1, al2, al3 = st.columns([2, 1, 1])
                if al1.button(f"🚀 VERPLAATS NAAR {state.bulk_loc}", type="primary", use_container_width=True):
                    service.push_undo_state(list(state.selected_ids))
                    service.repo.bulk_update_location(list(state.selected_ids), state.bulk_loc)
                    service.trigger_mutation(); state.show_location_grid = False; st.rerun(scope="fragment")
                if al2.button("📍 Wijchen", use_container_width=True): state.loc_prefix = "W"; st.rerun(scope="fragment")
                if al3.button("📍 Boxmeer", use_container_width=True): state.loc_prefix = "B"; st.rerun(scope="fragment")
                
                locs = [l for l in LOCATIE_OPTIES if l.startswith(state.loc_prefix) or l == "BK"]
                cols = st.columns(5)
                for i, loc in enumerate(locs):
                    with cols[i % 5]:
                        if st.button(loc, key=f"lb_{loc}", use_container_width=True, type="primary" if state.bulk_loc == loc else "secondary"):
                            state.bulk_loc = loc; st.rerun(scope="fragment")

    cs1, cs2 = st.columns([1, 1])
    if cs1.button(f"✅ ALLES SELECTEREN{suffix}", use_container_width=True):
        state.selected_ids.update(service.repo.get_all_matching_ids(state.zoek_veld)); st.rerun(scope="fragment")
    if cs2.button(f"⬜ ALLES DESELECTEREN{suffix}", use_container_width=True):
        state.selected_ids.clear(); st.rerun(scope="fragment")

    st.data_editor(
        state.mijn_data,
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
            "id": None,
            "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", width="small")
        },
        hide_index=True, use_container_width=True, key="main_editor", height=500, disabled=["id"],
        on_change=sync_selections
    )

    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        db_up = []
        for idx, changes in edits.items():
            clean = {k: v for k, v in changes.items() if k != "Selecteren"}
            if clean: db_up.append({"id": int(state.mijn_data.iloc[int(idx)]["id"]), **clean})
        if db_up:
            service.push_undo_state([r['id'] for r in db_up])
            service.repo.bulk_update_fields(db_up); service.trigger_mutation(); st.rerun(scope="fragment")

    num_p = max(1, (state.total_count - 1) // ROWS_PER_PAGE + 1)
    if num_p > 1:
        p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")
        if p1.button("⬅️ VORIGE", disabled=state.current_page == 0, use_container_width=True):
            state.current_page -= 1; st.rerun(scope="fragment")
        p2.markdown(f"<p style='text-align:center; margin:0;'>Pagina {state.current_page + 1} van {num_p}</p>", unsafe_allow_html=True)
        if p3.button("VOLGENDE ➡️", disabled=state.current_page == num_p - 1, use_container_width=True):
            state.current_page += 1; st.rerun(scope="fragment")

# =============================================================================
# 6. MAIN EXECUTION
# =============================================================================

def main():
    if "app_state" not in st.session_state: 
        st.session_state.app_state = AppState(ingelogd=st.query_params.get("auth") == "true")
    state = st.session_state.app_state

    logo_b64 = get_base64_logo("theunissen.webp")
    render_styling(logo_b64)

    if not state.ingelogd:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.header("Inloggen")
            pw = st.text_input("Wachtwoord", type="password")
            if st.button("Inloggen", use_container_width=True):
                if pw == WACHTWOORD:
                    state.ingelogd = True; st.query_params["auth"] = "true"; st.rerun()
                else: st.error("Wachtwoord onjuist")
        st.stop()
    
    service = VoorraadService(GlasVoorraadRepository(init_supabase()))
    render_header(logo_b64)
    render_main_interface(service)

    st.divider()
    f1, f2 = st.columns([1, 1])
    with f1:
        st.subheader("➕ Nieuwe ruit toevoegen")
        if state.success_msg: st.success(state.success_msg); state.success_msg = ""
        with st.form("add_form", clear_on_submit=True):
            f1a, f1b = st.columns(2)
            n_loc = f1a.selectbox("Locatie", options=LOCATIE_OPTIES)
            n_aant = f1b.number_input("Aantal", min_value=1, value=1)
            f1c, f1d = st.columns(2)
            n_br = f1c.number_input("Breedte (mm)", min_value=0, value=0)
            n_ho = f1d.number_input("Hoogte (mm)", min_value=0, value=0)
            n_ord = st.text_input("Ordernummer")
            n_oms = st.text_input("Omschrijving")
            if st.form_submit_button("TOEVOEGEN", use_container_width=True):
                service.repo.insert_one({"locatie": n_loc, "aantal": n_aant, "breedte": n_br if n_br > 0 else None, "hoogte": n_ho if n_ho > 0 else None, "order_nummer": n_ord.strip() or None, "omschrijving": n_oms.strip() or None})
                service.trigger_mutation(); state.success_msg = "Gelukt!"; st.rerun()

    with f2:
        st.subheader("📥 Bulk & Systeem")
        up = st.file_uploader("Bulk import Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed")
        if up and st.button("🚀 IMPORT STARTEN", use_container_width=True):
            try:
                df_import = pd.read_excel(up)
                df_import.columns = [str(c).lower().strip().replace(' ', '_') for c in df_import.columns]
                if 'order' in df_import.columns: df_import = df_import.rename(columns={'order': 'order_nummer'})
                db_cols = ["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"]
                final_import = df_import[[c for c in df_import.columns if c in db_cols]]
                all_ids = [r['id'] for r in service.repo.get_all_for_backup()]
                service.push_undo_state(all_ids)
                service.repo.bulk_update_fields(final_import.to_dict('records'))
                service.trigger_mutation(); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")
        
        if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
            service.trigger_mutation(); st.rerun()
        
        if state.undo_stack:
            st.divider()
            ls = state.undo_stack[-1]
            st.write(f"Laatste actie om: **{ls['tijd']}**")
            if not state.confirm_undo:
                if st.button(f"⏪ TERUGZETTEN", use_container_width=True):
                    state.confirm_undo = True; st.rerun()
            else:
                st.write("**Weet je het zeker? (Undo)**")
                u1, u2 = st.columns(2)
                if u1.button("Ja", use_container_width=True, type="primary", key="undo_yes"):
                    undo_data = state.undo_stack.pop()["data"]
                    clean_undo = [{k:v for k,v in r.items() if k != 'Selecteren'} for r in undo_data]
                    service.repo.bulk_update_fields(clean_undo)
                    state.confirm_undo = False
                    service.trigger_mutation(); st.success("Hersteld!"); st.rerun()
                if u2.button("Annuleer", use_container_width=True, key="undo_no"):
                    state.confirm_undo = False; st.rerun()

if __name__ == "__main__": main()
