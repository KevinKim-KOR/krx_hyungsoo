import json

def recursive_sanitize(obj):
    if isinstance(obj, dict):
        return {k: recursive_sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_sanitize(v) for v in obj]
    elif isinstance(obj, str):
        return obj.replace("\\", "/") # Force forward slashes to avoid JSON escape issues
    else:
        return obj

def test_sanitize():
    data = {
        "path": "C:\\Users\\Test",
        "nested": {
            "file": "D:\\Data\\file.json",
            "list": ["E:\\Backup\\1", "F:\\Backup\\2"]
        },
        "normal": "Hello World"
    }
    
    sanitized = recursive_sanitize(data)
    print(json.dumps(sanitized, indent=2))
    
    assert sanitized["path"] == "C:/Users/Test"
    assert sanitized["nested"]["file"] == "D:/Data/file.json"
    assert sanitized["nested"]["list"][0] == "E:/Backup/1"
    
    print("✅ Logic Verified")

if __name__ == "__main__":
    test_sanitize()
