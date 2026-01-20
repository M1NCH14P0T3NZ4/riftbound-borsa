import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re
import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Market Intelligence", page_icon="📈", layout="wide")

# Nascondi stile Streamlit standard
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud (SUPABASE_URL e SUPABASE_KEY).")
    st.stop()

# --- GESTIONE SESSIONE ---
if "user" not in st.session_state:
    st.session_state.user = None

def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except:
        st.error("Credenziali errate o utente non trovato.")

def signup_user(email, password):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.info("Registrazione inviata! Se non riesci ad accedere, controlla se hai ricevuto una mail di conferma.")
    except Exception as e:
        st.error(f"Errore: {e}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 1. SCHERMATA DI ACCESSO (AUTH WALL) ---
if st.session_state.user is None:
    st.title("🛡️ Riftbound Intelligence - Accesso")
    st.write("Accedi per consultare i trend di mercato e gestire il tuo portfolio criptato.")
    
    tab_l, tab_s = st.tabs(["Login", "Crea Account"])
    with tab_l:
        email = st.text_input("Email")
        pwd = st.text_input("Password", type="password")
        if st.button("Accedi"):
            login_user(email, pwd)
    with tab_s:
        n_email = st.text_input("Nuova Email")
        n_pwd = st.text_input("Nuova Password", type="password")
        if st.button("Registrati"):
            signup_user(n_email, n_pwd)
    st.stop()

# --- DA QUI IN POI L'UTENTE È LOGGATO ---

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def get_base_data():
    # Carica anagrafica carte
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    
    # Carica prezzi per i trend (ultimi 2000 record)
    p_res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty:
        df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    
    return df_c, df_p

def get_history(card_id):
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

df_cards, df_all_prices = get_base_data()

# --- SIDEBAR NAVIGAZIONE ---
with st.sidebar:
    st.title("👤 Account")
    st.write(f"Email: `{st.session_state.user.email}`")
    if st.button("Esci dal sistema"): logout_user()
    st.divider()
    
    st.header("🔍 Navigazione")
    selected_set = st.selectbox("Filtra Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
    f_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]
    
    selected_display = st.selectbox("Cerca Carta:", sorted(f_cards['display_name'].unique()))
    selected_lang = st.radio("Mercato:", ["EN", "CN"])
    
    if st.button("🔄 Aggiorna Database"):
        st.cache_data.clear()
        st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- LAYOUT PRINCIPALE ---
st.title("💹 Riftbound Market Intelligence")
t1, t2, t3 = st.tabs(["🔍 Dettaglio & IA", "🌍 Analisi Mercato", "🎒 La mia Collezione"])

# --- TAB 1: DETTAGLIO & IA ---
with t1:
    col_img, col_chart = st.columns([1, 2.5])
    df_history = get_history(card_id)
    df_lang = df_history[df_history['language'] == selected_lang] if not df_history.empty else pd.DataFrame()

    with col_img:
        st.image(card_info['image_url'], width='stretch')
        st.subheader("📝 Specifiche")
        st.write(f"ID: `{card_id}` | Rarità: {card_info['rarity']}")
        
        if not df_lang.empty:
            lp = float(df_lang.iloc[-1]['price_low'])
            lt = float(df_lang.iloc[-1]['price_trend'])
            st.subheader("🤖 Segnale IA")
            if lp > lt * 1.15: st.warning(f"⚠️ SOPRAVALUTATA (+{round(((lp/lt)-1)*100)}%)")
            elif lp < lt * 0.85: st.success(f"🔥 OCCASIONE (-{round((1-(lp/lt))*100)}%)")
            else: st.info("⚖️ MERCATO STABILE")

    with col_chart:
        if not df_lang.empty:
            # Grafico Doppio (Prezzo vs Media Mobile)
            temp = df_lang[['recorded_at', 'price_low', 'price_trend']].copy()
            melted = temp.melt(id_vars=['recorded_at'], value_vars=['price_low', 'price_trend'], var_name='Tipo', value_name='Prezzo')
            melted['Tipo'] = melted['Tipo'].map({'price_low': 'Prezzo Reale', 'price_trend': 'Trend (SMA 7g)'})
            
            fig = px.line(melted, x="recorded_at", y="Prezzo", color="Tipo", markers=True, template="plotly_dark",
                         color_discrete_map={'Prezzo Reale': "#00CC96", 'Trend (SMA 7g)': "#FFA15A"})
            fig.update_layout(hovermode="x unified", xaxis_title=None, margin=dict(t=0))
            st.plotly_chart(fig, width='stretch')
            st.metric("Valore Attuale", f"{lp} €", f"{round(lp-lt, 2)} € vs Media")
        else:
            st.info("Nessun dato per questo mercato. Avvia lo scraper.")

# --- TAB 2: ANALISI MERCATO ---
with t2:
    st.header("🌍 Trend Globali (EN)")
    if not df_all_prices.empty:
        df_en = df_all_prices[df_all_prices['language'] == 'EN'].copy()
        latest = df_en.sort_values('recorded_at').groupby('card_id').last().reset_index()
        
        # Calcolo Movers
        movers = []
        for cid in latest['card_id'].unique():
            h = df_en[df_en['card_id'] == cid].sort_values('recorded_at', ascending=False)
            if len(h) >= 2:
                c, p = float(h.iloc[0]['price_low']), float(h.iloc[1]['price_low'])
                if p > 0:
                    movers.append({'Carta': df_cards[df_cards['card_id']==cid]['name'].values[0], 
                                   'Variazione %': round(((c-p)/p)*100, 2), 'Prezzo': c})
        df_m = pd.DataFrame(movers)
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("📈 Top Gainers")
            st.dataframe(df_m.sort_values('Variazione %', ascending=False).head(5), hide_index=True, width='stretch')
        with c2:
            st.error("📉 Top Losers")
            st.dataframe(df_m.sort_values('Variazione %', ascending=True).head(5), hide_index=True, width='stretch')

# --- TAB 3: LA MIA COLLEZIONE ---
with t3:
    st.header("🎒 Gestione Raccoglitore")
    
    # 1. Importazione Massiva via TXT
    with st.expander("📥 Importazione Rapida (Copia-Incolla)", expanded=False):
        st.write("Incolla un elenco di nomi (uno per riga). Verranno aggiunte come quantità 1 (EN).")
        bulk_input = st.text_area("Lista nomi carte:", height=150, placeholder="Darius, Trifarian\nAcceptable Losses...")
        if st.button("Esegui Importazione"):
            names = [n.strip() for n in bulk_input.split("\n") if n.strip()]
            count = 0
            for n in names:
                match = df_cards[df_cards['name'].str.lower() == n.lower()]
                if not match.empty:
                    # Prende la versione non-showcase per default
                    target_id = match[match['is_showcase'] == False].iloc[0]['card_id'] if not match[match['is_showcase'] == False].empty else match.iloc[0]['card_id']
                    supabase.table("user_collections").upsert({
                        "user_id": st.session_state.user.id, "card_id": target_id, "quantity": 1
                    }).execute()
                    count += 1
            st.success(f"Aggiunte {count} carte al tuo portfolio!")
            st.rerun()

    # 2. Modifica Singola
    st.subheader(f"Modifica: {selected_display}")
    c_qty = st.number_input("Quantità posseduta", min_value=0, step=1)
    c_buy = st.number_input("Prezzo acquisto unitario (€)", min_value=0.0)
    if st.button("💾 Salva nel Raccoglitore"):
        supabase.table("user_collections").upsert({
            "user_id": st.session_state.user.id, "card_id": card_id, "quantity": c_qty, "purchase_price": c_buy
        }).execute()
        st.toast("Salvato!")
        st.rerun()

    # 3. Visualizzazione Portfolio
    st.divider()
    my_data = supabase.table("user_collections").select("*, cards(name, rarity)").eq("user_id", st.session_state.user.id).execute().data
    if my_data:
        df_my = pd.DataFrame(my_data)
        df_my['Nome'] = df_my['cards'].apply(lambda x: x['name'])
        df_my['Rarità'] = df_my['cards'].apply(lambda x: x['rarity'])
        
        # Calcolo valore totale portfolio
        # (Qui servirebbe una logica per prendere l'ultimo prezzo di ogni carta, per ora mostriamo la tabella)
        st.subheader("🖼️ Il tuo Portfolio")
        st.dataframe(df_my[['Nome', 'Rarità', 'quantity', 'purchase_price']], width='stretch', hide_index=True)
    else:
        st.info("Il tuo raccoglitore è vuoto.")

st.divider()
st.caption("Riftbound Borsa v5.0 | Dati protetti e privati per ogni utente.")
