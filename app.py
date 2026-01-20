import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re
import time

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Riftbound Intelligence", 
    page_icon="📈", 
    layout="wide"
)

# CSS per pulizia estetica
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .stMetric {background-color: #1e2130; padding: 15px; border-radius: 10px;}</style>""", unsafe_allow_html=True)

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets (URL e KEY) su Streamlit Cloud.")
    st.stop()

# --- 3. GESTIONE AUTENTICAZIONE ---
if "user" not in st.session_state:
    st.session_state.user = None

def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except:
        st.error("Credenziali non valide.")

def signup_user(email, password):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.info("Registrazione inviata! Controlla la mail per confermare (se richiesto) e accedi.")
    except Exception as e:
        st.error(f"Errore: {e}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 4. AUTH WALL ---
if st.session_state.user is None:
    st.title("🛡️ Riftbound Market Intelligence")
    st.markdown("### Accedi per sbloccare i dati della borsa e la tua collezione.")
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Login")
        l_em = st.text_input("Email", key="le")
        l_pw = st.text_input("Password", type="password", key="lp")
        if st.button("Entra"): login_user(l_em, l_pw)
    with col_r:
        st.subheader("Registrazione")
        s_em = st.text_input("Nuova Email", key="se")
        s_pw = st.text_input("Nuova Password", type="password", key="sp")
        if st.button("Crea Account"): signup_user(s_em, s_pw)
    st.stop()

# --- 5. CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def get_global_data():
    # Anagrafica
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    
    # Prezzi globali (EN) per statistiche mercato
    p_res = supabase.table("card_prices").select("*").eq("language", "EN").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty: df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    return df_c, df_p

def get_specific_history(card_id):
    # Query mirata per evitare limite 1000 righe
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty: df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

df_cards, df_market = get_global_data()

# --- 6. SIDEBAR ---
with st.sidebar:
    st.title("👤 Account")
    st.write(f"Loggato: `{st.session_state.user.email}`")
    if st.button("Logout"): logout_user()
    st.divider()
    
    st.header("📊 Filtri")
    sel_set = st.selectbox("Espansione:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
    f_cards = df_cards if sel_set == "Tutti" else df_cards[df_cards['set_code'] == sel_set]
    sel_card_display = st.selectbox("Cerca Carta:", sorted(f_cards['display_name'].unique()))
    sel_lang = st.radio("Mercato Prezzi:", ["EN", "CN"])
    
    if st.button("🔄 Forza Refresh Dati"):
        st.cache_data.clear()
        st.rerun()

# Recupero dati carta attiva
c_info = df_cards[df_cards['display_name'] == sel_card_display].iloc[0]
c_id = c_info['card_id']
df_h = get_specific_history(c_id)

# --- 7. LAYOUT PRINCIPALE ---
st.title("💹 Riftbound Market Watch")
tab1, tab2, tab3 = st.tabs(["🔍 Analisi Carta", "🌍 Panoramica Mercato", "🎒 Il mio Portfolio"])

# --- TAB 1: DETTAGLIO & IA ---
with tab1:
    col_a, col_b = st.columns([1, 2.5])
    df_l = df_h[df_h['language'] == sel_lang] if not df_h.empty else pd.DataFrame()
    
    with col_a:
        st.image(c_info['image_url'], use_container_width=True)
        st.subheader("📝 Info")
        st.write(f"ID: `{c_id}` | Rarità: {c_info['rarity']}")
        
        if not df_l.empty:
            curr_p = float(df_l.iloc[-1]['price_low'])
            curr_t = float(df_l.iloc[-1]['price_trend'])
            st.subheader("🤖 Segnale IA")
            if curr_p > curr_t * 1.15: st.warning(f"⚠️ SOPRAVALUTATA (+{round(((curr_p/curr_t)-1)*100)}%)")
            elif curr_p < curr_t * 0.85: st.success(f"🔥 OCCASIONE (-{round((1-(curr_p/curr_t))*100)}%)")
            else: st.info("⚖️ VALORE STABILE")

    with col_b:
        if not df_l.empty:
            # Grafico SMA (Media Mobile)
            temp = df_l[['recorded_at', 'price_low', 'price_trend']].copy()
            melted = temp.melt(id_vars=['recorded_at'], value_vars=['price_low', 'price_trend'], var_name='Metric', value_name='Euro')
            melted['Metric'] = melted['Metric'].map({'price_low': 'Prezzo', 'price_trend': 'Trend (7g)'})
            
            fig = px.line(melted, x="recorded_at", y="Euro", color="Metric", markers=True, template="plotly_dark",
                         color_discrete_map={'Prezzo': "#00CC96", 'Trend (7g)': "#FFA15A"})
            fig.update_layout(hovermode="x unified", xaxis_title=None, margin=dict(t=0))
            st.plotly_chart(fig, use_container_width=True)
            st.metric("Valore Attuale", f"{curr_p} €", f"{round(curr_p - curr_t, 2)} € vs Media")
        else:
            st.info("Nessun dato di prezzo disponibile per questa carta.")

# --- TAB 2: ANALISI MERCATO (Gainers/Losers) ---
with tab2:
    st.header("🌍 Origins & Spiritforged Hub")
    if not df_market.empty:
        latest = df_market.sort_values('recorded_at').groupby('card_id').last().reset_index()
        st.metric("Valore Totale Set (1x EN)", f"{round(latest['price_low'].sum(), 2)} €")
        
        # Calcolo Movers
        movers = []
        for cid in latest['card_id'].unique():
            h = df_market[df_market['card_id'] == cid].sort_values('recorded_at', ascending=False)
            if len(h) >= 2:
                c, p = float(h.iloc[0]['price_low']), float(h.iloc[1]['price_low'])
                if p > 0:
                    movers.append({'Carta': df_cards[df_cards['card_id']==cid]['name'].values[0], 
                                   'Var %': round(((c-p)/p)*100, 2), '€': c})
        
        df_m = pd.DataFrame(movers)
        c_g, c_l = st.columns(2)
        with c_g:
            st.success("📈 Top Gainers (24h)")
            st.dataframe(df_m.sort_values('Var %', ascending=False).head(5), hide_index=True, use_container_width=True)
        with c_l:
            st.error("📉 Top Losers (24h)")
            st.dataframe(df_m.sort_values('Var %', ascending=True).head(5), hide_index=True, use_container_width=True)

# --- TAB 3: PORTFOLIO (Con Fix Upsert & Bulk Import) ---
with tab3:
    st.header("🎒 Gestione Raccoglitore")
    
    # IMPORTAZIONE RAPIDA
    with st.expander("📥 Importazione Massiva (Copia-Incolla nomi)"):
        txt_in = st.text_area("Incolla un elenco (Darius, Trifarian...)")
        if st.button("Importa"):
            lines = [l.strip() for l in txt_in.split("\n") if l.strip()]
            success = 0
            for name in lines:
                match = df_cards[df_cards['name'].str.lower() == name.lower()]
                if not match.empty:
                    tid = match[match['is_showcase'] == False].iloc[0]['card_id'] if not match[match['is_showcase'] == False].empty else match.iloc[0]['card_id']
                    # FIX: Specifichiamo on_conflict per evitare APIError
                    supabase.table("user_collections").upsert(
                        {"user_id": st.session_state.user.id, "card_id": tid, "quantity": 1},
                        on_conflict="user_id,card_id"
                    ).execute()
                    success += 1
            st.success(f"Aggiunte {success} carte!")
            st.rerun()

    # SALVATAGGIO SINGOLO
    st.subheader(f"Modifica: {sel_card_display}")
    c1, c2 = st.columns(2)
    with c1: q = st.number_input("Quantità", min_value=0, step=1, key="qi")
    with c2: bp = st.number_input("Prezzo d'acquisto (€)", min_value=0.0, key="pi")
    
    if st.button("💾 Salva nel Portfolio"):
        try:
            supabase.table("user_collections").upsert({
                "user_id": st.session_state.user.id, 
                "card_id": c_id, 
                "quantity": q, 
                "purchase_price": bp
            }, on_conflict="user_id,card_id").execute()
            st.success("Portfolio aggiornato!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Dettagli Errore: {e}")

    # VISUALIZZAZIONE
    st.divider()
    my_data = supabase.table("user_collections").select("quantity, purchase_price, cards(name, rarity)").eq("user_id", st.session_state.user.id).execute().data
    if my_data:
        df_my = pd.DataFrame(my_data)
        df_my['Nome'] = df_my['cards'].apply(lambda x: x['name'] if x else 'N/A')
        df_my['Rarità'] = df_my['cards'].apply(lambda x: x['rarity'] if x else 'N/A')
        st.subheader("🖼️ La tua collezione")
        st.dataframe(df_my[['Nome', 'Rarità', 'quantity', 'purchase_price']], use_container_width=True, hide_index=True)
    else:
        st.info("Portfolio vuoto.")

st.divider()
st.caption("Riftbound Borsa Intelligence v6.0 | System Secure")
