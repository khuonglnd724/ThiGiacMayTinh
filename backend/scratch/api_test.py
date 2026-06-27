import requests
import numpy as np
import cv2
import tempfile, os

BASE = "http://localhost:8000"

# Tao anh test ngau nhien
img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
cv2.imwrite(tmp.name, img)
tmp.close()

print("=== Test 1: GET / ===")
r = requests.get(f"{BASE}/")
print(f"  Status: {r.status_code} | Response: {r.json()}")

print("\n=== Test 2: GET /logs ===")
r = requests.get(f"{BASE}/logs")
j = r.json()
print(f"  Status: {r.status_code} | count: {j['count']}")

print("\n=== Test 3: POST /detect ===")
with open(tmp.name, "rb") as f:
    r = requests.post(f"{BASE}/detect", files={"file": ("test.jpg", f, "image/jpeg")}, params={"conf": 0.1})
j = r.json()
print(f"  Status: {r.status_code} | status_field: {j['status']} | predictions: {len(j['predictions'])}")

print("\n=== Test 4: POST /segment ===")
with open(tmp.name, "rb") as f:
    r = requests.post(f"{BASE}/segment", files={"file": ("test.jpg", f, "image/jpeg")}, params={"conf": 0.1})
j = r.json()
print(f"  Status: {r.status_code} | status_field: {j['status']} | predictions: {len(j['predictions'])}")

print("\n=== Test 5: POST /caption ===")
with open(tmp.name, "rb") as f:
    r = requests.post(f"{BASE}/caption", files={"file": ("test.jpg", f, "image/jpeg")})
j = r.json()
print(f"  Status: {r.status_code} | caption: {j['caption']}")

print("\n=== Test 6: POST /vqa ===")
with open(tmp.name, "rb") as f:
    r = requests.post(f"{BASE}/vqa", files={"file": ("test.jpg", f, "image/jpeg")}, data={"question": "Is there any defect?"})
j = r.json()
print(f"  Status: {r.status_code}")
print(f"  Question: {j['question']}")
print(f"  Answer: {j['answer']}")

os.unlink(tmp.name)
print("\n=== All API tests completed! ===")
