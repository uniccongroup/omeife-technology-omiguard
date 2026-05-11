import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS


WORKSPACE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = WORKSPACE_DIR / "gas_ai_system" / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chatbot_service import generate_chat_reply  # noqa: E402


app = Flask(__name__)
CORS(app)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    context = data.get("context") or data.get("prediction") or {}

    try:
        return jsonify({"reply": generate_chat_reply(message, context)})
    except Exception as exc:
        return jsonify({"reply": "Chat service is unavailable.", "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
