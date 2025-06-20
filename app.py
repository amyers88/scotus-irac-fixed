import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
import openai
import PyPDF2

app = Flask(__name__)
CORS(app)

# Config
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

limiter = Limiter(get_remote_address, app=app, default_limits=["100 per day", "30 per hour"])
openai.api_key = os.environ.get("OPENAI_API_KEY")

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/api/generate_irac", methods=["POST"])
@limiter.limit("10 per minute")
def generate_irac():
    file = request.files.get("pdf")
    role = request.form.get("role")
    case_name = request.form.get("caseName")

    if not file or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type."}), 400

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(temp_path)

    try:
        reader = PyPDF2.PdfReader(temp_path)
        text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    except Exception as e:
        return jsonify({"error": "Failed to read PDF."}), 500
    finally:
        os.remove(temp_path)

    prompt = f"""
    Analyze the following Supreme Court case and produce an IRAC summary for a {role}:
    Case Name: {case_name}
    Text: {text}
    Output format: IRAC (Issue, Rule, Application, Conclusion)
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a legal analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        summary = response.choices[0].message.content
        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(".", "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)
