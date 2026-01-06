# 📄 Resume Tailorer

Add a rag_context.txt file if wanting to use yourself. This is the ground truth hub of context

And yes I am using the Perplexity API of all things. I had some spare credits left

AI-powered Chrome extension that tailors your resume to specific job descriptions using the Perplexity API. Upload your resume, paste a job description, and get a customized version optimized for that role.

![Resume Tailorer](https://img.shields.io/badge/Chrome-Extension-4285F4?style=flat&logo=googlechrome)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask)

## Features

- LaTeX-only Uploads: Drop a `.tex` resume so the backend can parse the exact source you already maintain.
- Automatic PDF Conversion: After the resume is tailored, the backend compiles the updated LaTeX into a downloadable PDF via `pdflatex`.

## Project Structure

```
resume-tailorer/
├── backend/                    # Python Flask backend
│   ├── app.py                  # Main server application
│   ├── requirements.txt        # Python dependencies
│   ├── rag_context.txt         # Your additional background info
│   └── uploads/                # Uploaded resume storage
├── extension/                  # Chrome extension
│   ├── manifest.json           # Extension configuration
│   ├── popup.html              # Extension UI
│   ├── popup.css               # Styles
│   ├── popup.js                # Frontend logic
│   ├── background.js           # Service worker
│   └── icons/                  # Extension icons
├── scripts/
│   └── generate_icons.py       # Icon generation script
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Google Chrome browser
- Perplexity API key ([Get one here](https://www.perplexity.ai/settings/api))
- A LaTeX distribution (TeX Live, MiKTeX, etc.) so the backend can run `pdflatex` if you upload `.tex` resumes

### 1. Backend Setup

```bash
# Clone or navigate to the project
cd resume-tailorer

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Set your Perplexity API key
export PERPLEXITY_API_KEY='your-api-key-here'

# Start the backend server
python3 backend/app.py
```

The server will start at `http://localhost:5000`.

### 2. Chrome Extension Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top right)
3. Click **Load unpacked**
4. Select the `extension` folder from this project
5. The Resume Tailorer icon should appear in your extensions bar

### 3. Configure RAG Context (Optional but Recommended)

Edit `backend/rag_context.txt` to add additional information about yourself:

- Extra skills not on your main resume
- Side projects and personal work
- Certifications and courses
- Volunteer experience
- Industry-specific knowledge

This context helps the AI swap in relevant experiences when tailoring your resume.

## 📖 Usage

### Upload Your Resume

1. Click the Resume Tailorer extension icon
2. Drag & drop your LaTeX (`.tex`) resume onto the upload area
3. Or click to browse and select the `.tex` file
4. Your LaTeX content will be extracted and displayed

### Tailor to a Job Description

1. Switch to the **Tailor** tab
2. Paste the job description into the text area
3. Click **Tailor Resume**
4. Wait for the AI to process (usually 10-30 seconds)
5. Review the tailored result
6. Copy to clipboard or download the result
7. If your source was a `.tex` file, click **Download PDF** to grab the compiled version

### Manage Context

1. Switch to the **Context** tab
2. Add additional skills, projects, experiences
3. Click **Save Context** to save to the server
4. This information will be used to enhance future tailoring

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PERPLEXITY_API_KEY` | Your Perplexity API key | Yes |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/upload` | POST | Upload resume file |
| `/tailor` | POST | Tailor resume to job description |
| `/rag-context` | GET | Get current RAG context |
| `/rag-context` | POST | Update RAG context |
| `/current-resume` | GET | Get currently loaded resume |

## 🔧 Development

### Regenerate Icons

If you want to customize the icons:

```bash
# Install Pillow if needed
pip install Pillow
```

### Running in Development Mode

The Flask backend runs in debug mode by default, providing:
- Auto-reload on file changes
- Detailed error messages
- Debug logging

### Testing the Extension

1. Make changes to extension files
2. Go to `chrome://extensions/`
3. Click the refresh icon on the Resume Tailorer card
4. Test your changes

## Security Notes

- Your Perplexity API key is stored locally and never sent to the extension
- Resume files are stored temporarily on your local machine
- No data is sent to external servers except Perplexity's API
- The extension only has access to `localhost:5000`

## Troubleshooting

### "Server Offline" Status

1. Make sure the backend is running (`python3 backend/app.py`)
2. Check that port 5000 is available
3. Verify your terminal shows "Server running at http://localhost:5000"

### "PERPLEXITY_API_KEY not set" Error

```bash
# Set the API key in your terminal
export PERPLEXITY_API_KEY='your-api-key-here'

# Restart the backend
python3 backend/app.py
```

### PDF Extraction Issues

Some PDFs (especially scanned documents) may not extract text properly. Try:
- Using a text-based PDF
- Converting to .tex or .txt format
- Re-saving the PDF with text layer

### CORS Errors

If you see CORS errors in the browser console:
1. Make sure you're running the backend with Flask-CORS installed
2. Check that the extension is loaded from the `extension` folder (not zipped)

### LaTeX Compilation Issues

- Make sure `pdflatex` is installed and available on your PATH before starting the backend (TeX Live or MiKTeX)
- If the PDF download button never appears, check the Flask console for LaTeX compilation log output

## License

MIT License - feel free to use and modify for your own purposes.

## Acknowledgments

- [Perplexity AI](https://www.perplexity.ai/) for their powerful API
- [Flask](https://flask.palletsprojects.com/) for the backend framework
- [PyPDF2](https://pypdf2.readthedocs.io/) for PDF text extraction

---

**Happy job hunting! 🎯**
