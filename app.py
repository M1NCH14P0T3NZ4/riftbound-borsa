import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Market Intelligence", page_icon="📈", layout="wide")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- CONNESSIONE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- AUTH ---
if "user" not in st.session_state: st.session_state.user = None

def login_user(e, p):
    try:
        res = supabase.auth.sign_in_with_password({"email": e, "password": p})
        st.session_state.user = res.user
        st.rerun()
    except: st.error("Credenziali errate.")

def signup_user(e, p):
    try:
        supabase.auth.sign_up({"email": e, "password": p})
        st.info("Registrazione inviata! Controlla la mail.")
    except Exception as ex: st.error(f"Errore: {ex}")

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- AUTH WALL ---
if st.session_state.user is None:
    st.title("🛡️ Riftbound Intelligence - Accesso")
    t_l, t_s = st.tabs(["Login", "Registrati"])
    with t_l:
        em = st.text_input("Email", key="l_em")
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("Accedi"): login_user(em, pw)
    with t_s:
        nem = st.text_input("Email", key="s_em")
        npw = st.text_input("Password", type="password", key="s_pw")
        if st.button("Crea Account"): signup_user(nem, npw)
    st.stop()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def get_base_data():
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    p_res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty: df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    return df_c, df_p

def get_history(cid):
    res = supabase.table("card_prices").select("*").eq("card_id", cid).order("recorded_at").execute()
    df = pd.DataFrame(res.data)
    if not df.empty: df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

df_cards, df_all_prices = get_base_data()

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"👤 `{st.session_state.user.email}`")
    if st.button("Logout"): logout()
    st.divider()
    s_set = st.selectbox("Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
    f_cards = df_cards if s_set == "Tutti" else df_cards[df_cards['set_code'] == s_set]
    s_card = st.selectbox("Carta:", sorted(f_cards['display_name'].unique()))
    s_lang = st.radio("Mercato:", ["EN", "CN"])
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

c_info = df_cards[df_cards['display_name'] == s_card].iloc[0]
c_id = c_info['card_id']

# --- LAYOUT ---
st.title("💹 Riftbound Market Intelligence")
t1, t2, t3 = st.tabs(["🔍 Dettaglio & IA", "🌍 Analisi Mercato", "🎒 La mia Collezione"])

# TAB 1: Dettaglio & IA
with t1:
    c_i, c_g = st.columns([1, 2.5])
    df_h = get_history(c_id)
    df_l = df_h[df_h['language'] == s_lang] if not df_h.empty else pd.DataFrame()
    with c_i:
        st.image(c_info['image_url'], width='stretch')
        if not df_l.empty:
            lp, lt = float(df_l.iloc[-1]['price_low']), float(df_l.iloc[-1]['price_trend'])
            st.subheader("🤖 Segnale IA")
            if lp > lt * 1.15: st.warning(f"⚠️ SOPRAVALUTATA (+{round(((lp/lt)-1)*100)}%)")
            elif lp < lt * 0.85: st.success(f"🔥 OCCASIONE (-{round((1-(lp/lt))*100)}%)")
            else: st.info("⚖️ STABILE")
    with c_g:
        if not df_l.empty:
            temp = df_l[['recorded_at', 'price_low', 'price_trend']].copy()
            mlt = temp.melt(id_vars=['recorded_at'], value_vars=['price_low', 'price_trend'], var_name='T', value_name='€')
            fig = px.line(mlt, x="recorded_at", y="€", color="T", markers=True, template="plotly_dark",
                         color_discrete_map={'price_low': "#00CC96", 'price_trend': "#FFA15A"})
            fig.update_layout(hovermode="x unified", xaxis_title=None, showlegend=False)
            st.plotly_chart(fig, width='stretch')
            st.metric("Ultimo Prezzo", f"{lp} €", f"{round(lp-lt, 2)} € vs Media")

# TAB 2: Analisi Mercato
with t2:
    if not df_all_prices.empty:
        df_en = df_all_prices[df_all_prices['language'] == 'EN'].copy()
        latest = df_en.sort_values('recorded_at').groupby('card_id').last().reset_index()
        st.metric("Valore Totale Origins (1x EN)", f"{round(latest['price_low'].sum(), 2)} €")
        movers = []
        for cid in latest['card_id'].unique():
            h = df_en[df_en['card_id'] == cid].sort_values('recorded_at', ascending=False)
            if len(h) >= 2:
                c, p = float(h.iloc[0]['price_low']), float(h.iloc[1]['price_low'])
                if p > 0: movers.append({'Carta': df_cards[df_cards['card_id']==cid]['name'].values[0], 'Var %': round(((c-p)/p)*100, 2), '€': c})
        df_m = pd.DataFrame(movers)
        cg, cl = st.columns(2)
        with cg:
            st.success("📈 Top Gainers")
            st.dataframe(df_m.sort_values('Var %', ascending=False).head(5), hide_index=True, width='stretch')
        with cl:
            st.error("📉 Top Losers")
            st.dataframe(df_m.sort_values('Var %', ascending=True).head(5), hide_index=True, width='stretch')

# TAB 3: LA MIA COLLEZIONE
with t3:
    st.header("🎒 Gestione Raccoglitore")
    
    # IMPORTAZIONE MASSIVA
    with st.expander("📥 Importazione Rapida (Copia-Incolla nomi)", expanded=False):
        bulk_in = st.text_area("Incolla elenco nomi (uno per riga):", height=150)
        if st.button("Esegui Importazione"):
            names = [n.strip() for n in bulk_in.split("\n") if n.strip()]
            c_up = 0
            for n in names:
                m = df_cards[df_cards['name'].str.lower() == n.lower()]
                if not m.empty:
                    tid = m[m['is_showcase'] == False].iloc[0]['card_id'] if not m[m['is_showcase'] == False].empty else m.iloc[0]['card_id']
                    supabase.table("user_collections").upsert({"user_id": st.session_state.user.id, "card_id": tid, "quantity": 1}).execute()
                    c_up += 1
            st.success(f"Importate {c_up} carte!")
            st.rerun()

    # MODIFICA SINGOLA
    st.subheader(f"Modifica: {s_card}")
    c_q = st.number_input("Quantità", min_value=0, step=1, key="q_in")
    c_b = st.number_input("Prezzo acquisto unitario (€)", min_value=0.0, key="p_in")
    if st.button("💾 Salva nel Portfolio"):
        # L'operazione di upsert userà il vincolo UNIQUE(user_id, card_id) creato via SQL
        supabase.table("user_collections").upsert({
            "user_id": st.session_state.user.id, 
            "card_id": c_id, 
            "quantity": c_q, 
            "purchase_price": c_b
        }).execute()
        st.success("Salvato!")
        st.rerun()

    # VISUALIZZAZIONE
    st.divider()
    my_data = supabase.table("user_collections").select("*, cards(name, rarity)").eq("user_id", st.session_state.user.id).execute().data
    if my_data:
        df_my = pd.DataFrame(my_data)
        df_my['Nome'] = df_my['cards'].apply(lambda x: x['name'])
        df_my['Rarità'] = df_my['cards'].apply(lambda x: x['rarity'])
        st.dataframe(df_my[['Nome', 'Rarità', 'quantity', 'purchase_price']], width='stretch', hide_index=True)
    else:
        st.info("Portfolio vuoto.")

st.caption("Riftbound Borsa v5.1 | Powered by Supabase Auth")
