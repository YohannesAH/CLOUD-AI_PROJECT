import logging
from flask import Flask, render_template, request, jsonify
import requests
import boto3
import ssl
import os
from dotenv import load_dotenv

load_dotenv()
# Configure logging I have added this for trouble shooting while debugging
logging.basicConfig(filename='prediction_errors.log', level=logging.ERROR)

app = Flask(__name__)

def allowSelfSignedHttps(allowed):
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
        ssl._create_default_https_context = ssl._create_unverified_context

allowSelfSignedHttps(True)

# AML API URL and key
AML_URL = os.environ.get('AML_URL')
AML_API_KEY = os.environ.get('AML_API_KEY')

# Custom Vision endpoint and key
CUSTOM_VISION_ENDPOINT = os.environ.get('CUSTOM_VISION_ENDPOINT')
CUSTOM_VISION_API_KEY = os.environ.get('CUSTOM_VISION_API_KEY')

# AWS credentials
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION_NAME = os.environ.get('AWS_REGION_NAME')

# Initialize AWS Comprehend client
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_NAME
)
comprehend = session.client('comprehend')

# The main landing page
@app.route('/')
def index():
    return render_template('index.html')

# Here the route for image_recognition is made
@app.route('/image_recognition')
def image_recognition():
    return render_template('image_recognition.html')

# Here I define the route for the predict_page route
@app.route('/predict_page')
def predict_page():
    return render_template('predict_page.html')

# Here I define teh route for the text_analysis image
@app.route('/text_analysis')
def text_analysis():
    return render_template('text_analysis.html')

@app.route('/recognize', methods=['POST'])
def recognize_image():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        headers = {
            'Prediction-Key': CUSTOM_VISION_API_KEY,
            'Content-Type': 'application/octet-stream'
        }
        response = requests.post(CUSTOM_VISION_ENDPOINT, headers=headers, data=file.read())

        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Image recognition failed'}), 500
    except Exception as e:
        # Log the error
        app.logger.error("An unexpected error occurred: " + str(e))
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        text_to_analyze = request.form['text']

        # Call AWS Comprehend API to analyze text
        sentiment_response = comprehend.detect_sentiment(Text=text_to_analyze, LanguageCode='en')
        entities_response = comprehend.detect_entities(Text=text_to_analyze, LanguageCode='en')
        syntax_response = comprehend.detect_syntax(Text=text_to_analyze, LanguageCode='en')

        # Process analysis results
        sentiment = sentiment_response['Sentiment']
        entities = entities_response['Entities']
        syntax_tokens = syntax_response['SyntaxTokens']

        # Prepare analysis result
        result = {
            'sentiment': sentiment,
            'entities': entities,
            'syntax_tokens': syntax_tokens
        }

        return jsonify(result)
    except Exception as e:
        # Log the error
        app.logger.error("An unexpected error occurred: " + str(e))
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/predict', methods=['POST'])
def predict():
    try:
        req_data = request.json
        app.logger.info("Received values:")
        app.logger.info(req_data)

        required_fields = ["genre", "published_year", "average_rating", "comprehension", "enticement"]
        for field in required_fields:
            if field not in req_data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Convert published_year and average_rating to numeric types
        try:
            req_data["published_year"] = int(req_data["published_year"])
            req_data["average_rating"] = float(req_data["average_rating"])
        except ValueError:
            return jsonify({"error": f"Invalid value for '{field}': {req_data[field]}"})

        # Prepare data in the required format
        data = {
            "Inputs": {
                "input1": [{
                    "genre": req_data["genre"],
                    "published_year": req_data["published_year"],
                    "average_rating": req_data["average_rating"],
                    "num_pages": req_data.get("num_pages", 0),  # Default value of 0 if not provided
                    "enticement": req_data["enticement"],
                    "comprehension": req_data["comprehension"]
                }]
            },
            "GlobalParameters": {}
        }

        headers = {'Content-Type': 'application/json', 'Authorization': AML_API_KEY}

        response = requests.post(AML_URL, json=data, headers=headers)

        app.logger.info("AML response:")
        app.logger.info(response.text)

        if response.status_code != 200:
            return jsonify({"error": f"The request failed with status code: {response.status_code}"}), 500

        result = response.json()
        predicted_page_count = result["Results"]["WebServiceOutput0"][0]["Scored Labels"]
        return jsonify({"predicted_page_count": predicted_page_count})
    except Exception as e:
        # Log the error
        app.logger.error("An unexpected error occurred: " + str(e))
        return jsonify({"error": "An unexpected error occurred"}), 500

if __name__ == '__main__':
    app.run(debug=True)
