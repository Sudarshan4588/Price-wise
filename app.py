from flask import Flask, render_template, request, jsonify
from serpapi import GoogleSearch
from datetime import datetime

# ----------------------------------------
# 🔧 CONFIGURATION
# ----------------------------------------

SERPAPI_KEY = ""

# ----------------------------------------
# ⚙️ APP SETUP
# ----------------------------------------

app = Flask(__name__)

# ----------------------------------------
# 🏠 Home Page
# ----------------------------------------

@app.route('/')
def home():
    return render_template('index.html')

# ----------------------------------------
# 🔍 SEARCH PRODUCTS
# ----------------------------------------

@app.route('/search', methods=['GET'])
def search():
    product = request.args.get('q')
    min_price = request.args.get('min', type=int)
    max_price = request.args.get('max', type=int)

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

        products = []
        for item in items:
            price_str = item.get("price")
            if not price_str:
                continue
            try:
                clean_price = int(''.join(filter(str.isdigit, price_str)))
            except:
                continue

            if (min_price and clean_price < min_price) or (max_price and clean_price > max_price):
                continue

            products.append({
                "title": item.get("title"),
                "price": clean_price,
                "platform": item.get("source"),
                "link": item.get("link"),
                "image": item.get("thumbnail"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews")
            })

        return jsonify({"products": products})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------
# 🏁 START FLASK SERVER
# ----------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
