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

    # Role-specific instructions
    if role == 'student':
        audience_instruction = """
You are generating an IRAC summary designed to help a law student fully understand the Supreme Court decision.

- Explain the Issue in detail.
- Clearly state the Rule with relevant legal doctrines.
- In the Application section, explain how the court reasoned through the facts and legal rules.
- Clarify any complex legal reasoning for educational purposes.
- Include sufficient context to teach the student why each part of IRAC fits.
- If appropriate, briefly explain why alternative outcomes were rejected.
- Your tone is educational but still professional.

Format your response strictly as:

Issue:
Rule:
Application:
Conclusion:
"""
    elif role == 'paralegal':
        audience_instruction = """
You are generating an IRAC summary designed for a paralegal supporting attorneys.

- Summarize the key legal holdings clearly.
- In the Application, include how this case fits into prior similar cases or established precedent.
- Emphasize how the ruling may apply to future cases or current litigation.
- Highlight any significant historical context that affects how the ruling is applied.
- Keep the summary actionable for legal drafting or research.
- Maintain the IRAC format while focusing on how the case connects to practice and litigation strategy.

Format your response strictly as:

Issue:
Rule:
Application:
Conclusion:
"""
    else:
        audience_instruction = ""

    prompt = f"""
{audience_instruction}

Case Name: {case_name}

Here is the full text of the Supreme Court decision:

{text}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a highly skilled legal assistant AI."},
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
