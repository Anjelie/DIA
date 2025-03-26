from flask import Flask, request, jsonify
import tensorflow as tf
import numpy as np
import sqlite3
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import requests
from bs4 import BeautifulSoup
import random
import time
from flask_cors import CORS  # Import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load the trained model
model = tf.keras.models.load_model("backend/sentiment_model.h5")

# Define Nitter instance
nitter_instances = ["https://nitter.privacyredirect.com"]

# Tokenizer settings
vocab_size = 10282
max_length = 100
oov_token = "<OOV>"
tokenizer = Tokenizer(num_words=vocab_size, oov_token=oov_token)

def fetch_tweets(username, instance, max_tweets=100):
    tweets = []
    page = ""
    headers = {"User-Agent": "Mozilla/5.0"}

    while len(tweets) < max_tweets:
        url = f"{instance}/{username}{page}"
        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 403:
                print(f"403 Forbidden from {instance}")
                return None

            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            tweet_divs = soup.find_all("div", class_="tweet-content")
            new_tweets = [tweet.get_text(strip=True) for tweet in tweet_divs]

            if not new_tweets:
                print(f"No more tweets found for {username}")
                break

            tweets.extend(new_tweets)
            tweets = tweets[:max_tweets]

            next_page = soup.find("a", string="Next")
            if next_page:
                page = next_page["href"]
            else:
                break

            time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching tweets for {username}: {e}")
            break

    print(f"Fetched {len(tweets)} tweets for {username}")
    return tweets

def get_tweets(username, max_tweets=100):
    for _ in range(len(nitter_instances)):
        instance = random.choice(nitter_instances)
        print(f"Trying instance: {instance}")
        tweets = fetch_tweets(username, instance, max_tweets)

        if tweets is None:
            print(f"403 Forbidden from {instance}, trying another instance...")
            continue

        return tweets

    return ["All instances blocked the request. Try using a proxy or Tor."]

def preprocess_text(texts):
    if not texts:
        print("Error: No tweets to process!")
        return np.array([])  # Return an empty array to avoid breaking `model.predict()`
    

    tokenizer.fit_on_texts(texts)

    sequences = tokenizer.texts_to_sequences(texts)

    # Debugging: Check if sequences contain None
    if any(seq is None for seq in sequences):
        print("Warning: Some tweets could not be tokenized properly!")

    # Remove None values and empty lists
    sequences = [seq for seq in sequences if seq]

    if not sequences:
        print("Error: No valid sequences after tokenization!")
        return np.array([])

    padded_sequences = pad_sequences(sequences, maxlen=max_length, padding='post', truncating='post')
    print(f"Processed {len(texts)} tweets into {len(padded_sequences)} valid sequences.")
    return padded_sequences


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Welcome to the ChatApp API!"})

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    username = data.get("username", "")
    
    if not username:
        return jsonify({"error": "Username is required"}), 400

    print(f"Fetching tweets for: {username}")
    tweets = get_tweets(username, max_tweets=100)

    if "All instances blocked" in tweets[0]:
        return jsonify({"error": "Failed to fetch tweets. Try again later."}), 500

    print(f"Processing tweets for {username}")
    processed_tweets = preprocess_text(tweets)

    print(f"Running prediction for {username}")
    predictions = model.predict(processed_tweets)
    avg_confidence = np.mean(predictions)
    result = "Depressed" if avg_confidence > 0.5 else "Not Depressed"

    print(f"Prediction Result for {username}: {result} (Confidence: {avg_confidence})")

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

# Try updating first
    cursor.execute(
    "UPDATE users SET depression_score = ? WHERE username = ?",
    (avg_confidence, username),
    )

# If no row was updated, insert a new one
    if cursor.rowcount == 0:
        cursor.execute(
            "INSERT INTO users (username, depression_score) VALUES (?, ?)",
            (username, avg_confidence),
        )

    conn.commit()
    conn.close()


    return jsonify({"username": username, "depression": result, "confidence": float(avg_confidence)})


app.secret_key = "your_secret_key"  # Required for session tracking

# Define the sequence of questions
QUESTIONS = [
    "What is your age?",
    "What is your gender? (Male/Female/Other)",
    "What is your occupation?",
    "What country do you live in?"
]

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    username = data.get("username")
    user_input = data.get("message")  # User's response to the last question

    # Initialize session if first time
    if "question_index" not in session:
        session["question_index"] = 0
        session["user_responses"] = {}

    question_index = session["question_index"]

    if question_index < len(QUESTIONS):
        # Store the user's response to the previous question
        if question_index > 0:
            session["user_responses"][QUESTIONS[question_index - 1]] = user_input

        # If all questions are answered, process the responses
        if question_index == len(QUESTIONS):
            demographic_data = session["user_responses"]

            # Store demographic data in the database
            store_demographic_data(username, demographic_data)

            # Clear session
            session.pop("question_index", None)
            session.pop("user_responses", None)

            return jsonify({"message": "Thank you! Your data has been saved."})

        # Send the next question
        next_question = QUESTIONS[question_index]
        session["question_index"] += 1
        return jsonify({"message": next_question})

    return jsonify({"message": "Something went wrong."})


def store_demographic_data(username, demographic_data):
    """Store user's demographic responses in the database"""
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS demographics (
            username TEXT PRIMARY KEY,
            age INTEGER,
            gender TEXT,
            occupation TEXT,
            country TEXT
        )
    """)

    cursor.execute("""
        INSERT OR REPLACE INTO demographics (username, age, gender, occupation, country)
        VALUES (?, ?, ?, ?, ?)
    """, (username, demographic_data["What is your age?"], demographic_data["What is your gender? (Male/Female/Other)"],
          demographic_data["What is your occupation?"], demographic_data["What country do you live in?"]))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    app.run(debug=True)
