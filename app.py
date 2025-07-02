from flask import Flask, request, jsonify
from serpapi import GoogleSearch
from pymongo import MongoClient
from datetime import datetime
from sklearn.linear_model import LinearRegression
import pandas as pd
import numpy as np

# ----------------------------------------
# 🔧 CONFIGURATION
# ----------------------------------------

SERPAPI_KEY = ""
MONGO_URI = ""
DB_NAME = "pricewise"
COLLECTION_NAME = "product_prices"

# ----------------------------------------
# ⚙️ APP SETUP
# ----------------------------------------

app = Flask(__name__)

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("✅ MongoDB Atlas connected successfully.")
except Exception as e:
    print("❌ MongoDB Atlas connection error:", e)

# ----------------------------------------
# 🔍 /search
# ----------------------------------------

@app.route('/search', methods=['GET'])
def search_product():
    product = request.args.get('q')
    if not product:
        return jsonify({"error": "Please provide a product name using ?q=product_name"}), 400

    try:
        params = {
            "engine": "google_shopping",
            "q": product,
            "api_key": SERPAPI_KEY,
            "gl": "in"
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        items = results.get("shopping_results", [])

        if not items:
            return jsonify({"message": f"No prices found for '{product}'."}), 404

        saved_data = []
        for item in items:
            price_str = item.get("price")
            if not price_str:
                continue

            try:
                clean_price = int(''.join(filter(str.isdigit, price_str)))
            except:
                continue

            entry = {
                "product": product.lower(),
                "title": item.get("title"),
                "price": clean_price,
                "platform": item.get("source"),
                "link": item.get("link"),
                "timestamp": datetime.utcnow()
            }

            inserted = collection.insert_one(entry)
            entry["_id"] = str(inserted.inserted_id)
            saved_data.append(entry)

        return jsonify({
            "message": f"{len(saved_data)} prices saved for '{product}'.",
            "results": saved_data
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------
# 🔮 /predict
# ----------------------------------------

@app.route('/predict', methods=['GET'])
def predict_price():
    product = request.args.get('q')
    if not product:
        return jsonify({"error": "Please provide a product name using ?q=product_name"}), 400

    try:
        cursor = collection.find({"product": product.lower(), "price": {"$exists": True}}).sort("timestamp", 1)
        data = list(cursor)

        for doc in data:
            doc["_id"] = str(doc["_id"])

        if len(data) < 5:
            return jsonify({"error": "Not enough data to predict"}), 400

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["day"] = (df["timestamp"] - df["timestamp"].min()).dt.days
        df = df[["day", "price"]]

        # 🔍 Remove outliers using IQR
        Q1 = df["price"].quantile(0.25)
        Q3 = df["price"].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        df = df[(df["price"] >= lower_bound) & (df["price"] <= upper_bound)]

        if len(df) < 5:
            return jsonify({"error": "Not enough clean data to predict"}), 400

        X = df["day"].values.reshape(-1, 1)
        y = df["price"].values
        model = LinearRegression()
        model.fit(X, y)

        future_days = np.arange(df["day"].max() + 1, df["day"].max() + 16).reshape(-1, 1)
        predicted_prices = model.predict(future_days)

        predictions = [
            {
                "day_from_today": int(day),
                "predicted_price": int(price)
            }
            for day, price in zip(future_days.flatten(), predicted_prices)
        ]

        return jsonify({
            "product": product,
            "prediction_days": len(predictions),
            "predictions": predictions
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------
# 🤖 /smart (search + predict + trend)
# ----------------------------------------

@app.route('/smart', methods=['GET'])
def smart_predict():
    product = request.args.get('q')
    if not product:
        return jsonify({"error": "Please provide a product name using ?q=product_name"}), 400

    try:
        # Step 1: Scrape
        params = {
            "engine": "google_shopping",
            "q": product,
            "api_key": SERPAPI_KEY,
            "gl": "in"
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        items = results.get("shopping_results", [])

        scraped_data = []
        for item in items:
            price_str = item.get("price")
            if not price_str:
                continue
            try:
                clean_price = int(''.join(filter(str.isdigit, price_str)))
            except:
                continue

            entry = {
                "product": product.lower(),
                "title": item.get("title"),
                "price": clean_price,
                "platform": item.get("source"),
                "link": item.get("link"),
                "timestamp": datetime.utcnow()
            }

            collection.insert_one(entry)
            entry["_id"] = str(entry.get("_id", ""))
            scraped_data.append(entry)

        if not scraped_data:
            return jsonify({"message": "No data found to scrape."}), 404

        # Step 2: Predict
        cursor = collection.find({"product": product.lower(), "price": {"$exists": True}}).sort("timestamp", 1)
        data = list(cursor)

        for doc in data:
            doc["_id"] = str(doc["_id"])

        if len(data) < 5:
            return jsonify({"message": "Not enough data to predict", "latest_scraped": scraped_data}), 200

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["day"] = (df["timestamp"] - df["timestamp"].min()).dt.days
        df = df[["day", "price"]]

        # Remove outliers using IQR
        Q1 = df["price"].quantile(0.25)
        Q3 = df["price"].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        df = df[(df["price"] >= lower_bound) & (df["price"] <= upper_bound)]

        if len(df) < 5:
            return jsonify({"error": "Not enough clean data to predict"}), 400

        model = LinearRegression()
        model.fit(df[["day"]], df["price"])

        future_days = np.arange(df["day"].max() + 1, df["day"].max() + 16).reshape(-1, 1)
        predicted = model.predict(future_days)
        predictions = [{"day_from_today": int(d), "predicted_price": int(p)} for d, p in zip(future_days.flatten(), predicted)]

        today_price = df["price"].iloc[-1]
        lowest_future_price = min(predicted)
        trend_message = (
            f"📉 Price may drop to ₹{int(lowest_future_price)} in upcoming days."
            if lowest_future_price < today_price else
            "📈 Price is expected to stay the same or increase."
        )

        return jsonify({
            "product": product,
            "latest_scraped": scraped_data,
            "prediction_days": len(predictions),
            "predictions": predictions,
            "insight": trend_message
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------
# 🏁 START SERVER
# ----------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
