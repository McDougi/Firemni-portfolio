import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
import plotly.express as px

# --- NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="Firemní Portfolio 2.0", layout="wide")

# --- DATABÁZE ---
def init_db():
    conn = sqlite3.connect('portfolio.db', check_same_thread=False)
    c = conn.cursor()
    # Přidán sloupec currency
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, ticker TEXT, amount REAL, 
                  buy_price REAL, type TEXT, rent_or_interest REAL, currency TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- KURZ DOLARU ---
@st.cache_data(ttl=3600)
def get_usd_czk():
    try:
        return yf.Ticker("CZK=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 23.5 # Záložní kurz, pokud by API vypadlo

usd_rate = get_usd_czk()

# --- FUNKCE PRO CENY AKCIÍ ---
@st.cache_data(ttl=3600)
def get_price(ticker):
    if not ticker or ticker == "-": return 0
    try:
        return yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except: return 0

# --- SIDEBAR (VKLÁDÁNÍ) ---
st.sidebar.header("➕ Nová investice")
category = st.sidebar.selectbox("Typ aktiva", ["Akcie/Krypto", "Nemovitost (Přímá)", "Participace (Úrok)"])

with st.sidebar.form("input_form", clear_on_submit=True):
    name = st.text_input("Název investice")
    ticker = st.text_input("Ticker (např. BTC-USD, AAPL)")
    curr = st.selectbox("Měna nákupu", ["CZK", "USD"])
    amount = st.number_input("Množství (kusy / investice)", min_value=0.0)
    buy_price = st.number_input("Nákupní cena (za kus / celková)", min_value=0.0)
    rent_interest = st.number_input("Měsíční nájem (Kč) / Roční úrok (%)", min_value=0.0)
    
    if st.form_submit_button("Uložit do portfolia"):
        conn.execute("INSERT INTO assets (name, ticker, amount, buy_price, type, rent_or_interest, currency) VALUES (?,?,?,?,?,?,?)",
                     (name, ticker, amount, buy_price, category, rent_interest, curr))
        conn.commit()
        st.rerun()

# --- DATA A VÝPOČTY ---
df = pd.read_sql_query("SELECT * FROM assets", conn)

if not df.empty:
    # 1. Získání cen pro akcie
    unique_tickers = df[df['ticker'] != ""]['ticker'].unique()
    current_prices = {t: get_price(t) for t in unique_tickers}

    # 2. Výpočet hodnot
    def calc_values(row):
        # Aktuální cena v původní měně
        if row['type'] == "Akcie/Krypto":
            prip = current_prices.get(row['ticker'], 0)
            val_orig = prip * row['amount']
        else:
            val_orig = row['buy_price']
        
        # Přepočet na CZK
        val_czk = val_orig * usd_rate if row['currency'] == "USD" else val_orig
        
        # Výpočet měsíčního úroku/nájmu v CZK
        if row['type'] == "Participace (Úrok)":
            monthly_czk = (val_czk * (row['rent_or_interest'] / 100)) / 12
        elif row['type'] == "Nemovitost (Přímá)":
            monthly_czk = row['rent_or_interest'] # Zde zadáváme rovnou nájem v CZK
        else:
            monthly_czk = 0
            
        return pd.Series([val_orig, val_czk, monthly_czk])

    df[['Hodnota (Orig)', 'Hodnota (CZK)', 'Měsíční Cashflow (CZK)']] = df.apply(calc_values, axis=1)

    # --- DASHBOARD ---
    st.title("📊 Firemní Portfolio Dashboard")
    st.info(f"Aktuální kurz: 1 USD = {usd_rate:.2f} CZK")
    
    total_czk = df['Hodnota (CZK)'].sum()
    total_passive = df['Měsíční Cashflow (CZK)'].sum()

    m1, m2 = st.columns(2)
    m1.metric("CELKOVÁ HODNOTA (CZK)", f"{total_czk:,.2f} Kč")
    m2.metric("PASIVNÍ PŘÍJEM (Měsíčně)", f"{total_passive:,.2f} Kč")

    # Grafy
    c1, c2 = st.columns(2)
    with c1:
        fig = px.pie(df, values='Hodnota (CZK)', names='type', title="Rozložení kapitálu", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(df, x='name', y='Měsíční Cashflow (CZK)', title="Měsíční příjem podle projektů", color='type')
        st.plotly_chart(fig2, use_container_width=True)

    # Tabulka detailů
    st.subheader("📋 Detailní přehled aktiv")
    display_df = df[['name', 'type', 'currency', 'Hodnota (Orig)', 'Hodnota (CZK)', 'Měsíční Cashflow (CZK)']]
    st.dataframe(display_df.style.format({
        'Hodnota (Orig)': '{:,.2f}',
        'Hodnota (CZK)': '{:,.2f} Kč',
        'Měsíční Cashflow (CZK)': '{:,.2f} Kč'
    }), use_container_width=True)

    # Správa dat
    with st.expander("🗑️ Správa / Smazat aktiva"):
        to_del = st.selectbox("Vyberte položku", df['name'].tolist())
        if st.button("Definitivně smazat"):
            conn.execute("DELETE FROM assets WHERE name = ?", (to_del,))
            conn.commit()
            st.rerun()
else:
    st.title("Vítejte!")
    st.info("Portfolio je prázdné. Přidejte první investici vlevo.")
