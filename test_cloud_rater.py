from app import CloudRater
import json

def test():
    rater = CloudRater()
    print("Testing VRT...")
    data = rater.rate_stock("VRT")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    test()
