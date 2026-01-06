"""
Resume Tailorer Backend
Flask server with Perplexity API integration and RAG system
"""

import os
import json
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4

from flask import Flask, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import requests
from pathlib import Path

app = Flask(__name__)
CORS(app, origins=["chrome-extension://*"])

# Configuration
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
RAG_FILE = Path(__file__).parent / 'rag_context.txt'
SAVED_RESUME_FILE = Path(__file__).parent / 'main.tex'
COMPILED_FOLDER = UPLOAD_FOLDER / 'compiled'
ALLOWED_EXTENSIONS = {'tex'}

UPLOAD_FOLDER.mkdir(exist_ok=True)
COMPILED_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Store current resume content in memory (in production, use a database)
current_resume = {
    'content': '',
    'filename': '',
    'file_type': ''
}


def load_saved_resume():
    """Load persisted resume on startup if it exists"""
    if SAVED_RESUME_FILE.exists():
        try:
            content = SAVED_RESUME_FILE.read_text(encoding='utf-8')
            current_resume['content'] = content
            current_resume['filename'] = SAVED_RESUME_FILE.name
            current_resume['file_type'] = 'tex'
            print(f"Loaded saved resume: {SAVED_RESUME_FILE.name}")
            return True
        except Exception as e:
            print(f"Error loading saved resume: {e}")
    return False


def save_resume_to_disk(content):
    """Persist resume to disk so it loads automatically next time"""
    try:
        SAVED_RESUME_FILE.write_text(content, encoding='utf-8')
        print(f"Resume saved to: {SAVED_RESUME_FILE}")
    except Exception as e:
        print(f"Error saving resume: {e}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_tex_text(filepath):
    """Extract text from LaTeX file, keeping structure"""
    with open(filepath, 'r', encoding='utf-8') as file:
        return file.read()


def load_rag_context():
    """Load the RAG context file containing additional user info"""
    if RAG_FILE.exists():
        with open(RAG_FILE, 'r', encoding='utf-8') as file:
            return file.read()
    return ""


def query_perplexity(prompt, system_prompt):
    """Query the Perplexity API"""
    api_key = os.environ.get('PERPLEXITY_API_KEY')
    
    if not api_key:
        raise Exception("PERPLEXITY_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }
    
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload,
        timeout=120
    )
    
    if response.status_code != 200:
        raise Exception(f"Perplexity API error: {response.text}")
    
    return response.json()['choices'][0]['message']['content']


def extract_preamble_from_original(original_tex):
    """Extract the preamble (everything before \\begin{document}) from original resume."""
    if '\\begin{document}' in original_tex:
        idx = original_tex.find('\\begin{document}')
        return original_tex[:idx]
    return ""


def extract_latex_from_response(response_text, original_tex=""):
    """
    Extract pure LaTeX from Perplexity response.
    The model may wrap the code in markdown fences or add explanatory text.
    If the response is missing the preamble, use the original resume's preamble.
    """
    text = response_text.strip()
    
    # Try multiple patterns to extract from markdown code fences
    fence_patterns = [
        r'```latex\s*\n(.*?)```',
        r'```tex\s*\n(.*?)```',
        r'```\s*\n(.*?)```',
        r'```(.*?)```',
    ]
    
    for pattern in fence_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if '\\documentclass' in extracted or '\\begin{document}' in extracted:
                text = extracted
                break
    
    # Find \documentclass and extract from there
    if '\\documentclass' in text:
        start = text.find('\\documentclass')
        text = text[start:]
    elif '\\begin{document}' in text:
        # Model skipped preamble - use original resume's preamble
        print("WARNING: Response missing preamble, using original resume's preamble")
        start = text.find('\\begin{document}')
        body = text[start:]
        
        # Get preamble from original
        preamble = extract_preamble_from_original(original_tex)
        if preamble:
            text = preamble + body
        else:
            text = body
    
    # Remove any trailing text after \end{document}
    end_doc_pattern = r'(\\end\{document\})'
    match = re.search(end_doc_pattern, text, re.IGNORECASE)
    if match:
        text = text[:match.end()]
    
    # Validate we have a proper LaTeX document
    if '\\documentclass' not in text and '\\begin{document}' not in text:
        print(f"WARNING: Could not extract valid LaTeX. Response preview: {response_text[:500]}...")
        raise Exception(f"Could not extract valid LaTeX from API response. The model may not have returned proper LaTeX code.")
    
    return text


def calculate_fill_ratio(pdf_path):
    """
    Calculate the page fill ratio using PyMuPDF.
    Measures how much of the usable page area is filled with content.
    Target: 0.88 <= fill_ratio <= 0.96
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page = doc[0]  # First page
        
        # Get page dimensions (letter size: 612 x 792 points)
        page_rect = page.rect
        page_height = page_rect.height
        
        # Get all text blocks
        blocks = page.get_text("blocks")
        if not blocks:
            doc.close()
            return 0.5  # Default if no content found
        
        # Find the top-most and bottom-most content
        content_top = page_height  # Will find minimum y (top of content)
        content_bottom = 0  # Will find maximum y (bottom of content)
        
        for block in blocks:
            # block format: (x0, y0, x1, y1, text, block_no, block_type)
            y0, y1 = block[1], block[3]
            content_top = min(content_top, y0)
            content_bottom = max(content_bottom, y1)
        
        doc.close()
        
        # For a resume with minimal margins (fullpage package + adjustments):
        # - Top margin is roughly 36-50pt (0.5-0.7 inches)
        # - Bottom margin is roughly 36-50pt
        # - Usable area is approximately page_height - 72pt (top) - 36pt (bottom)
        
        # The key metric: how far down the page does content go?
        # If content_bottom is close to (page_height - bottom_margin), page is full
        
        # Estimate margins based on where content actually starts
        top_margin = content_top  # Where content actually starts
        bottom_margin = 36  # Typical minimal bottom margin (~0.5 inch)
        
        # Usable area from where content starts to where it could end
        usable_bottom = page_height - bottom_margin
        usable_height = usable_bottom - top_margin
        
        # How much of that usable area is actually filled?
        content_used = content_bottom - top_margin
        
        fill_ratio = content_used / usable_height if usable_height > 0 else 0.9
        
        print(f"  Fill ratio debug: content_top={content_top:.0f}, content_bottom={content_bottom:.0f}, "
              f"page_height={page_height:.0f}, usable_height={usable_height:.0f}, ratio={fill_ratio:.2f}")
        
        return min(max(fill_ratio, 0.0), 1.0)  # Clamp to 0-1
    except Exception as e:
        print(f"Error calculating fill ratio: {e}")
        return 0.9  # Default to middle of range


def compile_latex_to_pdf(tex_content, filename_stem, save_final=True):
    """
    Compile LaTeX content to PDF using pdflatex.
    Returns (page_count, fill_ratio, final_path) if save_final=True, 
    else (page_count, fill_ratio, None).
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / f"{filename_stem}.tex"
            tex_path.write_text(tex_content, encoding='utf-8')

            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                error_message = result.stderr or result.stdout or "Unknown LaTeX compilation error"
                raise Exception(f"LaTeX compilation failed: {error_message.strip()[:300]}")

            pdf_path = Path(tmpdir) / f"{filename_stem}.pdf"
            if not pdf_path.exists():
                raise Exception("LaTeX compilation did not produce a PDF file.")

            # Get page count
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
            
            # Calculate fill ratio
            fill_ratio = calculate_fill_ratio(str(pdf_path))

            if not save_final:
                return page_count, fill_ratio, None

            final_filename = f"{filename_stem}.pdf"
            final_path = COMPILED_FOLDER / final_filename
            # Overwrite if exists (same resume name)
            if final_path.exists():
                final_path.unlink()
            shutil.copy(pdf_path, final_path)

            return page_count, fill_ratio, final_path
    except FileNotFoundError:
        raise Exception(
            "pdflatex binary not found. Install a LaTeX distribution (e.g., TeX Live or MiKTeX) "
            "and ensure `pdflatex` is on your PATH."
        )


def shorten_resume(latex_content, original_preamble, job_description, current_fill_ratio):
    """Ask Perplexity to shorten the resume (fill ratio too high or > 1 page)."""
    system_prompt = """You are a resume editor. The resume is too dense/long and needs to be shortened slightly.

Make SMALL targeted cuts - don't dramatically change the resume.

CUTTING PRIORITY:
1. Tighten verbose phrases - remove filler words
2. Shorten the longest bullet points
3. Remove redundant details
4. Cut least relevant skills

PRESERVE:
- All job-relevant qualifications and keywords
- Key achievements and metrics
- Overall structure (3 experiences, 2 projects)

Return ONLY the LaTeX code. No explanations."""

    prompt = f"""This resume needs to be SLIGHTLY shorter. Current fill ratio: {current_fill_ratio:.2f} (target: 0.88-0.96)

Make small cuts to reduce length by about 5-10%.

Job Description (keep these qualifications):
{job_description[:1500]}

Current LaTeX:
{latex_content}

Return slightly shortened LaTeX. Keep all sections, just tighten the content."""

    raw_response = query_perplexity(prompt, system_prompt)
    return extract_latex_from_response(raw_response, original_preamble)


def expand_resume(latex_content, original_preamble, job_description, current_fill_ratio):
    """Ask Perplexity to expand the resume (fill ratio too low)."""
    system_prompt = """You are a resume editor. The resume has too much whitespace and needs more content.

EXPAND by:
1. Add more detail to existing bullet points - elaborate on impact, context, technologies
2. Add an additional bullet to experiences that only have 2
3. Expand project descriptions with more technical detail
4. Add relevant skills that match the job description

RULES:
- Keep 3 experiences, 2 projects structure
- Each experience should have 2-3 bullets
- Each project should have 1-2 bullets
- Stay grounded in the candidate's background - embellish but don't fabricate

Return ONLY the LaTeX code. No explanations."""

    prompt = f"""This resume has too much whitespace. Current fill ratio: {current_fill_ratio:.2f} (target: 0.88-0.96)

Add more content to fill the page better - about 10-15% more content.

Job Description (emphasize these qualifications):
{job_description[:1500]}

Current LaTeX (too sparse):
{latex_content}

Return expanded LaTeX with more detail. Fill the page better while keeping it professional."""

    raw_response = query_perplexity(prompt, system_prompt)
    return extract_latex_from_response(raw_response, original_preamble)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle resume file upload"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Only LaTeX (.tex) resumes are supported"}), 400
    
    filename = secure_filename(file.filename)
    filepath = app.config['UPLOAD_FOLDER'] / filename
    file.save(filepath)
    try:
        content = extract_tex_text(filepath)
        current_resume['content'] = content
        current_resume['filename'] = filename
        current_resume['file_type'] = 'tex'
        
        # Persist to disk so it loads automatically next time
        save_resume_to_disk(content)
        
        return jsonify({
            "success": True,
            "filename": filename,
            "file_type": 'tex',
            "preview": content[:500] + "..." if len(content) > 500 else content,
            "persisted": True
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/tailor', methods=['POST'])
def tailor_resume():
    """Tailor resume based on job description"""
    data = request.get_json()
    
    if not data or 'job_description' not in data:
        return jsonify({"error": "No job description provided"}), 400
    
    if not current_resume['content']:
        return jsonify({"error": "No resume uploaded. Please upload a resume first."}), 400
    
    job_description = data['job_description']
    rag_context = load_rag_context()
    
    # Build the system prompt
    system_prompt = """You are a resume tailoring assistant optimizing for BOTH ATS systems AND human recruiters. Your goal is to make the candidate appear as a strong fit for the role. You can embellish and reframe experiences generously, but stay grounded in the candidate's actual background.

CORE DIRECTIVES:

1. QUALIFICATIONS THROUGHOUT (TOP PRIORITY): Every required qualification from the job description should feel DEMONSTRATED through the bullet points, not just listed in skills. Rewrite experience bullets to naturally showcase the required technologies, methodologies, and competencies. The reader should finish each section thinking "this person clearly has X qualification."

2. THEME SATURATION: The job's dominant theme (e.g., systems programming, ML, networking) should radiate through EVERY bullet point. Reframe existing work to emphasize relevant angles. If a bullet doesn't connect to the job's core theme, rewrite it until it does or cut it.

3. FILL ONE PAGE COMPLETELY: The resume MUST be exactly one page - no more, no less. Fill the page edge-to-edge with relevant content. If there's whitespace at the bottom, add more detail to bullets, include additional relevant projects, or expand descriptions. Don't leave empty space.

4. ATS OPTIMIZATION:
   - Include EXACT keywords and phrases from the job description (titles, technologies, methodologies)
   - Use standard section headers the ATS expects (Experience, Education, Skills, Projects)
   - Spell out acronyms once, then use abbreviation (e.g., "Machine Learning (ML)")
   - Include a dedicated Skills/Technologies section with comma-separated keywords for easy parsing
   - Avoid formatting that breaks ATS: no tables, no multi-column layouts, no text boxes

5. RESUME STRUCTURE (STRICT):
   - EXPERIENCE SECTION: Exactly 3 roles, each with 2-3 bullet points
   - PROJECTS SECTION: Exactly 2 projects, each with 1-2 bullet points
   - Each bullet tells a story: ACTION VERB → what you did → IMPACT/RESULT
   - Lead each role with the most relevant/impressive achievement for THIS job
   - Write naturally - keyword stuffing is obvious; weave terms into compelling narratives

6. CONFIDENT LANGUAGE: Strong, assertive phrasing. "Contributed to" → "Led". "Familiar with" → "Proficient in". "Helped" → "Drove". Never hedge.

7. QUANTIFY STRATEGICALLY: Add metrics to ~50% of bullets - the most impactful ones. Not every bullet needs a number. Use metrics for scale, performance gains, and team size. Leave some bullets as pure narrative to avoid looking formulaic.

8. MAINTAIN BELIEVABILITY: Embellishment is fine, outright fabrication should be rare. Stretch the truth on scope/impact, upgrade titles slightly, claim proficiency in tools they've touched briefly - but don't invent entire roles or major projects from nothing. The candidate must be able to speak to everything on the resume.

9. DO NOT FABRICATE COURSEWORK: Only list courses that appear in the original resume or RAG context. You can reword course names slightly but don't invent courses.

10. DO NOT COMBINE PROJECTS: Keep projects separate. If you need fewer projects, pick the most relevant ones and tailor them individually. Never merge two projects into one hybrid project.

11. PRESERVE LATEX STRUCTURE: Keep the document compilable. Don't break formatting commands."""

    # Build the user prompt with RAG context
    prompt = f"""## Current Resume:
{current_resume['content']}

## Additional Background Information (use this to swap in relevant experiences/skills):
{rag_context if rag_context else "No additional context provided."}

## Job Description to Tailor For:
{job_description}

## Instructions:
Rewrite this resume so every qualification from the job description feels DEMONSTRATED through the narrative:

STRICT STRUCTURE:
- 3 Experience entries with 2-4 bullets each
- 2 Project entries with 1-2 bullets each

1. WEAVE QUALIFICATIONS INTO BULLETS (TOP PRIORITY) - Show skills in action through experience descriptions
2. REWRITE every bullet: ACTION VERB → relevant context → IMPACT
3. FILL THE ENTIRE PAGE - adjust bullet length/detail to fill the page with no whitespace
4. ADD METRICS SELECTIVELY - quantify ~50% of bullets
5. UPGRADE weak language to confident assertions
6. Every bullet should make the reader think "they've done exactly what we need"

Use the additional background to pull in relevant details. Embellish generously but stay grounded in real experience.

CRITICAL OUTPUT FORMAT: Return ONLY the raw LaTeX code starting with \\documentclass and ending with \\end{{document}}. No markdown, no explanations, no code fences. Just valid, compilable LaTeX that fits on ONE page."""

    try:
        raw_response = query_perplexity(prompt, system_prompt)
        
        # Debug: log the raw response
        print("=" * 50)
        print("RAW API RESPONSE (first 1000 chars):")
        print(raw_response[:1000])
        print("=" * 50)
        
        # Extract pure LaTeX from the response (strip markdown fences, explanatory text, etc.)
        # Pass original resume so we can use its preamble if the response is missing it
        tailored_content = extract_latex_from_response(raw_response, current_resume['content'])
        
        # Debug: log the extracted content
        print("EXTRACTED LATEX (first 500 chars):")
        print(tailored_content[:500])
        print("=" * 50)
        
        filename_stem = Path(current_resume['filename']).stem or "resume"
        
        # Target fill ratio range
        MIN_FILL_RATIO = 0.88
        MAX_FILL_RATIO = 0.96
        max_optimization_attempts = 5
        adjustment_count = 0
        adjustment_type = None  # 'shortened' or 'expanded'
        
        for attempt in range(max_optimization_attempts + 1):
            page_count, fill_ratio, _ = compile_latex_to_pdf(tailored_content, filename_stem, save_final=False)
            print(f"Optimization check #{attempt}: {page_count} page(s), fill ratio: {fill_ratio:.2f}")
            
            # Hard constraint: must be 1 page
            if page_count > 1:
                print(f"  → Too long ({page_count} pages), shortening...")
                if attempt < max_optimization_attempts:
                    adjustment_count += 1
                    adjustment_type = 'shortened'
                    tailored_content = shorten_resume(
                        tailored_content,
                        current_resume['content'],
                        job_description,
                        fill_ratio
                    )
                    continue
                else:
                    print(f"WARNING: Could not fit on 1 page after {max_optimization_attempts} attempts")
                    break
            
            # Fill ratio optimization (only if already 1 page)
            if fill_ratio < MIN_FILL_RATIO:
                print(f"  → Too sparse (fill: {fill_ratio:.2f} < {MIN_FILL_RATIO}), expanding...")
                if attempt < max_optimization_attempts:
                    adjustment_count += 1
                    adjustment_type = 'expanded'
                    tailored_content = expand_resume(
                        tailored_content,
                        current_resume['content'],
                        job_description,
                        fill_ratio
                    )
                    continue
            elif fill_ratio > MAX_FILL_RATIO:
                print(f"  → Too dense (fill: {fill_ratio:.2f} > {MAX_FILL_RATIO}), shortening slightly...")
                if attempt < max_optimization_attempts:
                    adjustment_count += 1
                    adjustment_type = 'shortened'
                    tailored_content = shorten_resume(
                        tailored_content,
                        current_resume['content'],
                        job_description,
                        fill_ratio
                    )
                    continue
            
            # Success: 1 page and fill ratio in range
            print(f"✓ Optimized: 1 page, fill ratio {fill_ratio:.2f} (target: {MIN_FILL_RATIO}-{MAX_FILL_RATIO})")
            break
        
        # Final compilation and save
        page_count, fill_ratio, compiled_path = compile_latex_to_pdf(tailored_content, filename_stem, save_final=True)
        compiled_pdf_url = url_for('download_compiled_pdf', filename=compiled_path.name, _external=False)

        response_payload = {
            "success": True,
            "original_filename": current_resume['filename'],
            "file_type": current_resume['file_type'],
            "tailored_resume": tailored_content,
            "page_count": page_count,
            "fill_ratio": round(fill_ratio, 2),
            "was_adjusted": adjustment_count > 0,
            "adjustment_count": adjustment_count,
            "adjustment_type": adjustment_type
        }

        if compiled_pdf_url:
            response_payload["compiled_pdf_url"] = compiled_pdf_url

        return jsonify(response_payload)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/rag-context', methods=['GET'])
def get_rag_context():
    """Get current RAG context"""
    context = load_rag_context()
    return jsonify({"context": context})


@app.route('/rag-context', methods=['POST'])
def update_rag_context():
    """Update RAG context file"""
    data = request.get_json()
    
    if not data or 'context' not in data:
        return jsonify({"error": "No context provided"}), 400
    
    try:
        with open(RAG_FILE, 'w', encoding='utf-8') as file:
            file.write(data['context'])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/current-resume', methods=['GET'])
def get_current_resume():
    """Get currently loaded resume"""
    if not current_resume['content']:
        return jsonify({"loaded": False})
    
    return jsonify({
        "loaded": True,
        "filename": current_resume['filename'],
        "file_type": current_resume['file_type'],
        "preview": current_resume['content'][:500] + "..." if len(current_resume['content']) > 500 else current_resume['content'],
        "persisted": SAVED_RESUME_FILE.exists()
    })


@app.route('/compiled/<path:filename>', methods=['GET'])
def download_compiled_pdf(filename):
    """Serve compiled PDF files."""
    return send_from_directory(COMPILED_FOLDER, filename, as_attachment=True)


if __name__ == '__main__':
    print("=" * 50)
    print("Resume Tailorer Backend Starting...")
    print("=" * 50)
    
    # Load saved resume if it exists
    if load_saved_resume():
        print(f"✓ Resume loaded from: {SAVED_RESUME_FILE}")
    else:
        print("No saved resume found. Upload one via the extension.")
    
    print("\nServer running at http://localhost:5000")
    print("=" * 50)
    
    app.run(debug=True, port=5000)
