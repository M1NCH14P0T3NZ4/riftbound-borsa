import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Market Intelligence", page_icon="📈", layout="wide")

# Nascondi menu Streamlit
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Errore: Secrets non configurati su Streamlit Cloud.")
    st.stop()

# --- GESTIONE SESSIONE AUTENTICAZIONE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.logged_in = True
        st.session_state.user_email = res.user.email
        st.session_state.user_id = res.user.id
        st.success("Accesso eseguito!")
        st.rerun()
    except Exception as e:
        st.error("Credenziali non valide o utente non trovato.")

def signup_user(email, password):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.info("Registrazione inviata! Controlla la tua email per confermare (se richiesto) e riprova il login.")
    except Exception as e:
        st.error(f"Errore registrazione: {e}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_id = None
    st.rerun()

# --- SCHERMATA DI AUTENTICAZIONE (Se non loggato) ---
if not st.session_state.logged_in:
    st.title("🛡️ Riftbound Borsa - Accesso Riservato")
    st.markdown("Benvenuto nella piattaforma di analisi avanzata per Riftbound. Effettua l'accesso per consultare i prezzi e gestire la tua collezione.")
    
    col_auth1, col_auth2 = st.columns(2)
    
    with col_auth1:
        st.subheader("Login")
        l_email = st.text_input("Email", key="login_email")
        l_pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Accedi"):
            login_user(l_email, l_pwd)
            
    with col_auth2:
        st.subheader("Nuovo Utente")
        s_email = st.text_input("Email", key="signup_email")
        s_pwd = st.text_input("Password", type="password", key="signup_pwd")
        if st.button("Crea Account"):
            signup_user(s_email, s_pwd)
    st.stop() # Blocca l'esecuzione qui finché non sono loggato

# --- DA QUI IN POI IL CODICE VIENE ESEGUITO SOLO SE LOGGATI ---

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def get_all_base_data():
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    p_res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty:
        df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    return df_c, df_p

def get_card_history(card_id):
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

df_cards, df_all_prices = get_all_base_data()

# --- SIDEBAR (LOGGATO) ---
with st.sidebar:
    st.success(f"Loggato come: \n{st.session_state.user_email}")
    if st.button("Esci (Logout)"):
        logout_user()
    st.divider()
    st.header("🔍 Navigazione")
    selected_set = st.sidebar.selectbox("Filtra per Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
    f_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]
    selected_display = st.sidebar.selectbox("Scegli Carta:", sorted(f_cards['display_name'].unique()))
    selected_lang = st.sidebar.radio("Mercato:", ["EN", "CN"])
    if st.sidebar.button("🔄 Aggiorna Database"):
        st.cache_data.clear()
        st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']
df_history = get_card_history(card_id)

# --- LAYOUT PRINCIPALE CON TABS ---
st.title("💹 Riftbound Market Intelligence")
tab1, tab2, tab3 = st.tabs(["🔍 Dettaglio & IA", "🌍 Analisi Mercato", "🎒 La mia Collezione"])

# --- TAB 1: DETTAGLIO CARTA & IA ---
with tab1:
    col_img, col_chart = st.columns([1, 2.5])
    with col_img:
        st.image(card_info['image_url'], use_container_width=True)
        st.subheader("📝 Info")
        st.write(f"**ID:** `{card_id}` | **Rarità:** {card_info['rarity']}")
        if card_info['ability']:
            with st.expander("Vedi Abilità"): st.write(card_info['ability'])
        
        # LOGICA SEGNALE IA
        df_lang = df_history[df_history['language'] == selected_lang]
        if not df_lang.empty:
            last_p = float(df_lang.iloc[-1]['price_low'])
            last_t = float(df_lang.iloc[-1]['price_trend'])
            st.subheader("🤖 Segnale IA")
            if last_p > last_t * 1.15: st.warning(f"⚠️ SOPRAVALUTATA (+{round(((last_p/last_t)-1)*100)}%)")
            elif last_p < last_t * 0.85: st.success(f"🔥 OCCASIONE (-{round((1-(last_p/last_t))*100)}%)")
            else: st.info("⚖️ MERCATO STABILE")

    with col_chart:
        if not df_lang.empty:
            temp_df = df_lang[['recorded_at', 'price_low', 'price_trend']].copy()
            df_melted = temp_df.melt(id_vars=['recorded_at'], value_vars=['price_low', 'price_trend'],
                                     var_name='Legenda', value_name='Prezzo')
            df_melted['Legenda'] = df_melted['Legenda'].map({'price_low': 'Prezzo Real', 'price_trend': 'Media Mobile (7g)'})

            fig = px.line(df_melted, x="recorded_at", y="Prezzo", color="Legenda",
                         markers=True, template="plotly_dark",
                         color_discrete_map={'Prezzo Real': "#00CC96", 'Media Mobile (7g)': "#FFA15A"})
            fig.update_layout(hovermode="x unified", xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
            st.metric("Ultimo Rilevamento", f"{last_p} €", f"{round(last_p - last_t, 2)} € vs Media")
        else:
            st.warning("Nessun dato per questa lingua.")

# --- TAB 2: ANALISI MERCATO ---
with tab2:
    st.header("🌍 Panoramica Origins & Spiritforged")
    if not df_all_prices.empty:
        df_en = df_all_prices[df_all_prices['language'] == 'EN'].copy()
        latest_market = df_en.sort_values('recorded_at').groupby('card_id').last().reset_index()
        total_val = latest_market['price_low'].sum()
        
        st.metric("Valore Totale Set (1x EN)", f"{round(total_val, 2)} €")
        
        # Calcolo Gainers/Losers
        movers = []
        for cid in latest_market['card_id'].unique():
            h = df_en[df_en['card_id'] == cid].sort_values('recorded_at', ascending=False)
            if len(h) >= 2:
                curr, prev = float(h.iloc[0]['price_low']), float(h.iloc[1]['price_low'])
                if prev > 0:
                    movers.append({'Carta': df_cards[df_cards['card_id']==cid]['name'].values[0], 
                                   'Var %': round(((curr-prev)/prev)*100, 2), 'Prezzo': curr})
        df_m = pd.DataFrame(movers)
        cg, cl = st.columns(2)
        with cg:
            st.success("📈 Top Gainers (24h)")
            st.dataframe(df_m.sort_values('Var %', ascending=False).head(5), hide_index=True, use_container_width=True)
        with cl:
            st.error("📉 Top Losers (24h)")
            st.dataframe(df_m.sort_values('Var %', ascending=True).head(5), hide_index=True, use_container_width=True)

# --- TAB 3: LA MIA COLLEZIONE (DATABASE PRIVATO) ---
with tab3:
    st.header(f"🎒 Raccoglitore di {st.session_state.user_email}")
    st.write("Aggiungi carte per monitorare il valore del tuo patrimonio personale.")
    
    col_port1, col_port2 = st.columns(2)
    with col_port1:
        st.write(f"Stai aggiungendo: **{selected_display}**")
        qty = st.number_input("Quantità posseduta", min_value=0, step=1, key="col_qty")
        buy_p = st.number_input("Prezzo di acquisto unitario (€)", min_value=0.0, key="col_price")
        if st.button("Salva nel Portfolio"):
            supabase.table("user_collections").upsert({
                "user_id": st.session_state.user_id,
                "card_id": card_id,
                "quantity": qty,
                "purchase_price": buy_p
            }).execute()
            st.toast(f"Salvato: {card_info['name']}!", icon="✅")

    with col_port2:
        st.subheader("La tua collezione")
        my_coll = supabase.table("user_collections").select("*, cards(name)").execute().data
        if my_coll:
            df_my = pd.DataFrame(my_coll)
            # Mostriamo una versione semplificata
            df_my['Nome Carta'] = df_my['cards'].apply(lambda x: x['name'])
            st.dataframe(df_my[['Nome Carta', 'quantity', 'purchase_price']], use_container_width=True, hide_index=True)
        else:
            st.info("Il tuo raccoglitore è ancora vuoto.")

st.divider()
st.caption("Riftbound Borsa v5.0 | Sistema protetto da crittografia SSL")
