from flask import Flask, request, jsonify, render_template
import requests
import pandas as pd
from flask_cors import CORS
from datetime import datetime, timedelta
from statsmodels.tsa.arima.model import ARIMA
import os

import logging

# Set up logging for AI explainability
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# IBM Watsonx credentials and API URL
WATSONX_API_KEY = 'Sw-FBmmPvG-AeLumgpBIgBJtsF8kLCwUGx-8CiltffFU'
WATSONX_MODEL_ID = 'ibm/granite-13b-chat-v2'
WATSONX_PROJECT_ID = 'fcf6a4f6-e88d-4e78-b032-48bb0fcfa588'
WATSONX_API_URL = 'https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version=2023-05-29'

# Load prompts from config file
PROMPTS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'config', 'prompts.txt')

def load_prompts(file_path):
    prompts = {}
    current_key = None
    current_value = []

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            if line.endswith('|'):
                if current_key:
                    prompts[current_key] = '\n'.join(current_value).strip()
                current_key = line[:-1].strip()
                current_value = []
            else:
                current_value.append(line)

        if current_key:
            prompts[current_key] = '\n'.join(current_value).strip()

    return prompts

prompts = load_prompts(PROMPTS_FILE_PATH)

def get_iam_token(api_key):
    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': api_key.strip()}

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()['access_token']

def send_request_to_watsonx(payload):
    url = WATSONX_API_URL
    headers = {
        'Authorization': f'Bearer {get_iam_token(WATSONX_API_KEY)}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def analyze_sentiment(sentimentText):
    sentiment_prompt = prompts.get('sentiment_prompt')
    if not sentiment_prompt:
        return "neutral", "No sentiment prompt available."

    sentimentText = sentimentText.strip()
    if not sentimentText:
        return "neutral", "No sentiment text provided."

    sentiment_prompt = sentiment_prompt.replace("{{input_text}}", sentimentText)

    payload = {
        'project_id': WATSONX_PROJECT_ID,
        'model_id': WATSONX_MODEL_ID,
        'input': sentiment_prompt,
        'parameters': {
            'decoding_method': 'greedy',
            'max_new_tokens': 50
        }
    }

    response = send_request_to_watsonx(payload)
    generated_text = response.get('results', [{}])[0].get('generated_text', '').lower()

    explanation = response.get('explanation', 'Sentiment based on provided text.')  # Fetch explanation if available

    if 'positive' in generated_text:
        return 'positive', explanation
    elif 'negative' in generated_text:
        return 'negative', explanation
    else:
        return 'neutral', explanation

def adjust_predictions_based_on_sentiment(predicted_highs, predicted_lows, sentiment):
    adjustment_factor = 0.02 if sentiment == 'positive' else -0.02 if sentiment == 'negative' else 0
    adjusted_highs = [high * (1 + adjustment_factor) for high in predicted_highs]
    adjusted_lows = [low * (1 + adjustment_factor) for low in predicted_lows]
    return adjusted_highs, adjusted_lows

def get_stock_data(symbol):
    ALPHA_VANTAGE_API_KEY = '0WFJ8X8IJ1OLF4C0'
    params = {
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'apikey': ALPHA_VANTAGE_API_KEY,
        'outputsize': 'full',
        'datatype': 'json'
    }
    response = requests.get('https://www.alphavantage.co/query', params=params)
    response.raise_for_status()
    data = response.json()

    if 'Time Series (Daily)' not in data:
        return {"error": "No stock data found for the symbol"}

    time_series = data['Time Series (Daily)']
    df = pd.DataFrame.from_dict(time_series, orient='index')
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    df.index = pd.to_datetime(df.index)
    df = df.asfreq('D', method='pad')
    df = df.apply(pd.to_numeric)
    df = df.sort_index()

    today = pd.to_datetime(datetime.now())
    six_months_ago = today - timedelta(days=180)
    return df.loc[six_months_ago:today]

def custom_ml_model_prediction(stock_data_df):
    predicted_highs = []
    predicted_lows = []

    high_model = ARIMA(stock_data_df['high'], order=(5, 1, 0))
    high_model_fit = high_model.fit()
    predicted_highs = list(high_model_fit.forecast(steps=7))

    low_model = ARIMA(stock_data_df['low'], order=(5, 1, 0))
    low_model_fit = low_model.fit()
    predicted_lows = list(low_model_fit.forecast(steps=7))

    return predicted_highs, predicted_lows

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_stock_data', methods=['POST'])
def stock_data():
    data = request.json
    symbol = data.get('symbol')
    has_news = data.get('has_news', False)
    sentiment_text = data.get('sentiment_text', '')

    sentiment = 'neutral'
    explanation = ''
    if has_news and sentiment_text:
        sentiment, explanation = analyze_sentiment(sentiment_text)

    if not symbol:
        return jsonify({"error": "No symbol provided"}), 400

    try:
        stock_data_df = get_stock_data(symbol)
        if isinstance(stock_data_df, dict) and 'error' in stock_data_df:
            return jsonify(stock_data_df), 500
        
        if stock_data_df.empty:
            return jsonify({"error": "No stock data available for the provided symbol."}), 404
        
        predicted_highs, predicted_lows = custom_ml_model_prediction(stock_data_df)

        adjusted_highs, adjusted_lows = adjust_predictions_based_on_sentiment(predicted_highs, predicted_lows, sentiment)

        last_date = stock_data_df.index[-1]
        future_dates = [(last_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 8)]

        # Log AI explainability from Watsonx
        logging.info(f"Predictions based on: {explanation}")

        return jsonify({
            "date": stock_data_df.index.strftime('%Y-%m-%d').tolist(),
            "high": stock_data_df['high'].tolist(),
            "low": stock_data_df['low'].tolist(),
            "predicted_high": adjusted_highs,
            "predicted_low": adjusted_lows,
            "predicted_dates": future_dates
        })
    
    except Exception as e:
        return jsonify({"error": "An error occurred while processing the request.", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)