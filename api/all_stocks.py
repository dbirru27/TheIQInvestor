import json
import os

def handler(request, response):
    """Serve all_stocks.json for detail view"""
    try:
        # Load from file
        file_path = os.path.join(os.getcwd(), 'all_stocks.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return response.json(data)
    except FileNotFoundError:
        return response.json({"error": "Stock data not found"}, status_code=500)
    except Exception as e:
        return response.json({"error": str(e)}, status_code=500)
