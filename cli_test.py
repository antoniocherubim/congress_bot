import requests

user_id = "cli-test-001"

while True:
    msg = input("Você: ")
    if msg.lower() in ["sair", "exit"]:
        break

    resp = requests.post(
        "http://localhost:8000/chat",
        json={"user_id": user_id, "message": msg}
    )

    print("Bot:", resp.json()["reply"])