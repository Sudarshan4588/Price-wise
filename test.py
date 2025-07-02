from serpapi import GoogleSearch

params = {
    "engine": "google_shopping",
    "q": "iPhone 16",
    "api_key": "YOUR_SERPAPI_KEY",
    "gl": "in"
}

search = GoogleSearch(params)
results = search.get_dict()
print("✅ Search OK")
print(results.get("shopping_results", []))
