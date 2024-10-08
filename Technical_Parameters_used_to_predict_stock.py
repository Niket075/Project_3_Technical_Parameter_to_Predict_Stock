import requests
import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred
from textblob import TextBlob
import plotly.graph_objects as go
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="_plotly_utils.basevalidators")


# Constants
ALPHA_VANTAGE_API_KEY = "GNO5WNQ635FTVNRW"
symbols = ["ONON"]

# MacroEconomics Indicators
fred = Fred(api_key='9b43fe6268cc222965da4a0f99fc413b')
macro_data = {}

# Fetching GDP data (GDP is the identifier for the Gross Domestic Product in FRED)
try:
    gdp_data = fred.get_series('GDP')
    macro_data['gdp_data'] = gdp_data.iloc[-1]
except Exception as e:
    print(f"Error fetching GDP data: {e}")
    gdp_data = None

# Inflation Rate (CPI/PPI)
try:
    cpi_data = fred.get_series('CPIAUCNS')
    macro_data['cpi_data'] = cpi_data.iloc[-1]
except Exception as e:
    cpi_data = None

try:
    ppi_data = fred.get_series('PPIACO')
    macro_data['ppi_data'] = ppi_data.iloc[-1]
except Exception as e:
    ppi_data = None

# Unemployment Rate
try:
    unemployment_data = fred.get_series('UNRATE')
    macro_data['unemployment_data'] = unemployment_data.iloc[-1]
except Exception as e:
    unemployment_data = None

# Interest Rates
try:
    fed_funds_rate = fred.get_series('FEDFUNDS')
    macro_data['fed_funds_rate'] = fed_funds_rate.iloc[-1]
except Exception as e:
    fed_funds_rate = None

# Consumer Confidence Index
try:
    consumer_confidence_data = fred.get_series('CONCCONF')
    macro_data['consumer_confidence_data'] = consumer_confidence_data.iloc[-1]
except Exception as e:
    consumer_confidence_data = None

# PMI (Purchasing Managers' Index)
try:
    pmi_data = fred.get_series('ISM/MAN_PMI')
    macro_data['pmi_data'] = pmi_data.iloc[-1]
except Exception as e:
    pmi_data = None

# News Sensitivity Analysis
def fetch_news(symbol):
    stock = yf.Ticker(symbol)
    news_list = stock.news
    if not news_list:
        return []

    news_data = []
    for news_item in news_list:
        headline = news_item['title']
        url = news_item['link']
        news_data.append((headline, url))
    return news_data

def analyze_sentiment(text):
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0:
        return 'Positive'
    elif analysis.sentiment.polarity < 0:
        return 'Negative'
    else:
        return 'Neutral'

def get_news_sentiment(symbol):
    news_data = fetch_news(symbol)
    if not news_data:
        return "No news available for this symbol."

    sentiment_results = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
    for headline, url in news_data:
        sentiment = analyze_sentiment(headline)
        sentiment_results[sentiment] += 1

    # Determine the most dominant sentiment
    max_sentiment = max(sentiment_results, key=sentiment_results.get)
    return max_sentiment

def fetch_data_from_alpha_vantage(symbol):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=5min&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if "Time Series (5min)" not in data:
            note = data.get('Note', '')
            error_message = data.get('Error Message', 'Unknown error')
            print(f"Alpha Vantage error for {symbol}: {note or error_message}")
            return None

        time_series = data['Time Series (5min)']
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns={
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume'
        })

        df = df.apply(pd.to_numeric, errors='coerce')
        df['symbol'] = symbol
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'timestamp'}, inplace=True)

        return df

    except requests.exceptions.RequestException as e:
        print(f"Request error from Alpha Vantage for {symbol}: {e}")
        return None

def fetch_data_from_yf(symbol,period,interval):
    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False)
        if df.empty:
            print(f"No data returned for {symbol}")
            return None

        df['symbol'] = symbol
        df.reset_index(inplace=True)
        df.rename(columns={
            'Datetime': 'timestamp',
            'Date': 'timestamp',
            'timestamp': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Adj Close': 'adj_close',
            'Volume': 'volume'
        }, inplace=True)

        return df

    except Exception as e:
        print(f"Error fetching data from Yahoo Finance for {symbol}: {e}")
        return None

def calculate_indicators(df):
    if df.empty:
        return df

    # Moving Average
    df['MA_20'] = df['close'].rolling(window=20).mean()
    df['MA_50'] = df['close'].rolling(window=50).mean()
    df['MA_200'] = df['close'].rolling(window=200).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Volatility
    df['Volatility'] = df['close'].rolling(window=20).std()

    # MACD
    df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    df['Bollinger_Middle'] = df['close'].rolling(window=20).mean()
    df['Bollinger_Upper'] = df['Bollinger_Middle'] + 2 * df['close'].rolling(window=20).std()
    df['Bollinger_Lower'] = df['Bollinger_Middle'] - 2 * df['close'].rolling(window=20).std()

    # Average True Range (ATR)
    df['High-Low'] = df['high'] - df['low']
    df['High-Close'] = np.abs(df['high'] - df['close'].shift())
    df['Low-Close'] = np.abs(df['low'] - df['close'].shift())
    df['True_Range'] = df[['High-Low', 'High-Close', 'Low-Close']].max(axis=1)
    df['ATR'] = df['True_Range'].rolling(window=14).mean()

    return df


def fetch_pe_ratio(symbol):
    stock = yf.Ticker(symbol)
    try:
        info = stock.info
        pe_ratio = info.get('forwardEps') / info.get('currentPrice') if info.get('currentPrice') else None
        return pe_ratio
    except Exception as e:
        print(f"Error fetching P/E ratio for {symbol}: {e}")
        return None

def make_recommendation(df, pe_ratio=None):
    if df.empty or len(df) < 20:
        return None

    latest_data = df.iloc[-1]
    recommendation = "Hold"

    if (latest_data['close'] > latest_data['MA_20'] and
        latest_data['RSI'] < 30 and
        latest_data['MACD'] > latest_data['MACD_Signal'] and
        latest_data['close'] < latest_data['Bollinger_Lower'] and
        (pe_ratio and pe_ratio < 20)):  # Example P/E Ratio condition
        recommendation = "Buy"

    elif (latest_data['close'] < latest_data['MA_20'] and
          latest_data['RSI'] > 70 and
          latest_data['MACD'] < latest_data['MACD_Signal'] and
          latest_data['close'] > latest_data['Bollinger_Upper'] and
          (pe_ratio and pe_ratio > 30)):  # Example P/E Ratio condition
        recommendation = "Sell"

    return recommendation

def analyze_macroeconomic_data(macro_data):
    if not macro_data:
        return "Neutral"

    positive_indicators = 0
    negative_indicators = 0

    # GDP is generally considered a positive indicator
    if macro_data.get('gdp_data'):
        positive_indicators += 1

    # CPI and PPI: Inflationary indicators; high values can be negative
    if macro_data.get('cpi_data') and macro_data['cpi_data'] > 2:
        negative_indicators += 1
    if macro_data.get('ppi_data') and macro_data['ppi_data'] > 2:
        negative_indicators += 1

    # Unemployment Rate: Lower is generally better
    if macro_data.get('unemployment_data') and macro_data['unemployment_data'] < 5:
        positive_indicators += 1
    else:
        negative_indicators += 1

    # Federal Funds Rate: Higher rates are often seen as negative
    if macro_data.get('fed_funds_rate') and macro_data['fed_funds_rate'] < 2:
        positive_indicators += 1
    else:
        negative_indicators += 1

    # Consumer Confidence Index: Higher is better
    if macro_data.get('consumer_confidence_data') and macro_data['consumer_confidence_data'] > 100:
        positive_indicators += 1

    # PMI: Higher indicates economic growth
    if macro_data.get('pmi_data') and macro_data['pmi_data'] > 50:
        positive_indicators += 1
    else:
        negative_indicators += 1

    if positive_indicators > negative_indicators:
        return "Positive"
    elif negative_indicators > positive_indicators:
        return "Negative"
    else:
        return "Neutral"

def print_colored(text, color_code):
    """
    Prints text with a specific color and bold effect.
    """
    return f"\033[1;{color_code}m{text}\033[0m"

def process_symbol(symbol, period, interval):
    print(f"\n***{symbol}***")

    # Fetch and analyze news sentiment
    news_sentiment = get_news_sentiment(symbol)

    # Fetch and analyze financial data
    df_alpha_vantage = fetch_data_from_alpha_vantage(symbol)
    df_yf = fetch_data_from_yf(symbol, period, interval)
    alpha_vantage_recommendation = None
    yf_recommendation = None

    pe_ratio = fetch_pe_ratio(symbol)

    if df_alpha_vantage is not None and not df_alpha_vantage.empty:
        df_alpha_vantage = calculate_indicators(df_alpha_vantage)
        alpha_vantage_recommendation = make_recommendation(df_alpha_vantage, pe_ratio)
        print("\nAlpha Vantage Data Indicators:")
        print(df_alpha_vantage.tail())
        explain_indicators(df_alpha_vantage.tail().iloc[-1], pe_ratio, source="Alpha Vantage")

    if df_yf is not None and not df_yf.empty:
        df_yf = calculate_indicators(df_yf)
        yf_recommendation = make_recommendation(df_yf, pe_ratio)
        print("\nYahoo Finance Data Indicators:")
        explain_indicators(df_yf.tail().iloc[-1], pe_ratio, source="Yahoo Finance")

    # Fetch and analyze macroeconomic data
    macro_sentiment = analyze_macroeconomic_data(macro_data)

    # Determine overall financial analysis sentiment
    financial_analysis_sentiment = "Neutral"
    if alpha_vantage_recommendation == "Buy" or yf_recommendation == "Buy":
        financial_analysis_sentiment = "Positive"
    elif alpha_vantage_recommendation == "Sell" or yf_recommendation == "Sell":
        financial_analysis_sentiment = "Negative"

    # Print consolidated results
    print("\nRecommendations:")
    print(f"Financial Analysis: {print_colored(financial_analysis_sentiment, '32' if financial_analysis_sentiment == 'Positive' else '31' if financial_analysis_sentiment == 'Negative' else '33')}")
    print(f"Macroeconomic Analysis: {print_colored(macro_sentiment, '32' if macro_sentiment == 'Positive' else '31' if macro_sentiment == 'Negative' else '33')}")
    print(f"News Sensitivity Analysis: {print_colored(news_sentiment, '32' if news_sentiment == 'Positive' else '31' if news_sentiment == 'Negative' else '33')}")

    # Create and show charts
    create_charts(symbol)


def explain_indicators(latest_data, pe_ratio, source=""):
    """
    Explain the indicators and provide a rationale for whether the signal is Positive, Negative, or Neutral.
    """
    print(f"\n{source} Indicator Explanation:")

    # Moving Averages
    print(f"MA_20: {latest_data['MA_20']:.2f} (20-day Moving Average)")
    if latest_data['close'] > latest_data['MA_20']:
        print("The current price is above the 20-day moving average, which is generally a Positive signal.")
    else:
        print("The current price is below the 20-day moving average, which can be a Negative signal.")

    # RSI
    print(f"RSI: {latest_data['RSI']:.2f} (Relative Strength Index)")
    if latest_data['RSI'] < 30:
        print(print_colored("RSI is below 30, indicating that the stock might be oversold and could be a Positive signal.", '32'))
    elif latest_data['RSI'] > 70:
        print(print_colored("RSI is above 70, indicating that the stock might be overbought and could be a Negative signal.", '31'))
    else:
        print(print_colored("RSI is between 30 and 70, suggesting a Neutral stance.", '33'))

    # MACD
    print(f"MACD: {latest_data['MACD']:.2f}")
    print(f"MACD Signal Line: {latest_data['MACD_Signal']:.2f}")
    if latest_data['MACD'] > latest_data['MACD_Signal']:
        print(print_colored("MACD is above the signal line, which is a Positive momentum signal.", '32'))
    else:
        print(print_colored("MACD is below the signal line, which indicates a Negative momentum signal.", '31'))

    # Bollinger Bands
    print(f"Bollinger Upper Band: {latest_data['Bollinger_Upper']:.2f}")
    print(f"Bollinger Lower Band: {latest_data['Bollinger_Lower']:.2f}")
    if latest_data['close'] < latest_data['Bollinger_Lower']:
        print(print_colored("Price is below the lower Bollinger Band, which could be a Positive buying opportunity.", '32'))
    elif latest_data['close'] > latest_data['Bollinger_Upper']:
        print(print_colored("Price is above the upper Bollinger Band, which might indicate an overbought condition and could be Negative.", '31'))
    else:
        print(print_colored("Price is within the Bollinger Bands, suggesting a Neutral outlook.", '33'))

    # ATR (Volatility)
    print(f"ATR: {latest_data['ATR']:.2f} (Average True Range)")
    if latest_data['ATR'] > latest_data['ATR'].mean():
        print("High ATR suggests increased volatility, which can be a risk factor.")
    else:
        print("Low ATR suggests lower volatility, which could imply stability.")

    # P/E Ratio
    if pe_ratio:
        print(f"P/E Ratio: {pe_ratio:.2f}")
        if pe_ratio < 20:
            print(print_colored("A low P/E ratio might indicate that the stock is undervalued, which could be a Positive signal.", '32'))
        elif pe_ratio > 30:
            print(print_colored("A high P/E ratio might suggest overvaluation, which could be a Negative signal.", '31'))
        else:
            print(print_colored("P/E ratio is within a Neutral range.", '33'))
    else:
        print("P/E Ratio not available.")

def create_charts(symbol):
    periods = ['1y', '6mo', '1d']
    intervals = ['1d', '1d', '1m']
    
    for period, interval in zip(periods, intervals):
        data = fetch_data_from_yf(symbol, period, interval)
        if data is None or data.empty:
            print(f"No data available for {symbol} with period {period} and interval {interval}")
            continue
        
        # Calculate indicators
        data = calculate_indicators(data)

        # Create traces for plotly
        traces = []

        # Closing price trace
        traces.append(go.Scatter(x=data['timestamp'], y=data['close'], mode='lines', name='Close', line=dict(color='#00B2E2')))

        # Bollinger Bands traces
        traces.append(go.Scatter(x=data['timestamp'], y=data['Bollinger_Upper'], mode='lines', name='Bollinger Upper Band', line=dict(color='red', dash='dash')))
        traces.append(go.Scatter(x=data['timestamp'], y=data['Bollinger_Lower'], mode='lines', name='Bollinger Lower Band', line=dict(color='red', dash='dash')))

        # Moving Averages traces
        traces.append(go.Scatter(x=data['timestamp'], y=data['MA_20'], mode='lines', name='MA 20', line=dict(color='green')))
        traces.append(go.Scatter(x=data['timestamp'], y=data['MA_50'], mode='lines', name='MA 50', line=dict(color='orange')))
        traces.append(go.Scatter(x=data['timestamp'], y=data['MA_200'], mode='lines', name='MA 200', line=dict(color='purple')))

        # Create figure
        fig = go.Figure(data=traces)

        # Update layout for interactive features
        fig.update_layout(
            title=f'{symbol} - {period} {interval}',
            xaxis_title='Date',
            yaxis_title='Value',
            template='plotly_dark',  # Dark theme
            hovermode='x unified'
        )
        
        # Show the plot
        fig.show()


for symbol in symbols:
    process_symbol(symbol,'1y','1d')
