# ResumeFilter: HR Signup + NLP Resume Matching

## Features
- HR creates an account using name, email, and password.
- Passwords are hashed; they are not stored as plain text.
- HR must log in before using the resume dashboard.
- spaCy phrase matching identifies skills such as `ML` / `Machine Learning`, `NLP`, `Python`, and `SQL`.
- PDF, DOCX, and TXT resume text extraction.
- Matched/missing skills and score.
- Candidate email extraction from readable resume text, with a clickable email link when found.
- An Open Resume link for each uploaded resume.
- SQLite works locally; PostgreSQL is used when `DATABASE_URL` is configured for deployment.

## Run locally (Windows)
```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. Select **Create an account**, register, then log in.

## Deploy to Vercel
1. Push this folder to a GitHub repository.
2. In Vercel, choose **Add New → Project**, import that repository, and deploy. Vercel supports Flask detection; the root `app.py` exposes `app`.
3. Create a PostgreSQL database through a Vercel Marketplace integration such as Neon or Supabase.
4. In Vercel project **Settings → Environment Variables**, add:
   - `DATABASE_URL` = PostgreSQL connection string from your database provider
   - `SECRET_KEY` = a long, random secret value (do not share it)
5. Redeploy after adding the variables.

Important: on Vercel, do not rely on a local SQLite file for user accounts because serverless function files are not persistent. The app uses PostgreSQL when `DATABASE_URL` is set. Resume uploads are temporary and kept under 4 MB in this demo; Vercel Functions have a 4.5 MB request-body limit. The Open Resume link is reliable for local runs; on Vercel, use persistent object storage (such as S3-compatible storage) for reliable file access across serverless requests. For larger uploads, use object storage and upload directly to it.

## Supported resume types
PDF, DOCX, TXT. Scanned image-only PDFs may not work because OCR is not included.

## Extend the skill list
Edit `SKILL_ALIASES` in `app.py`. Example:
```python
"Machine Learning": ["machine learning", "machine-learning", "ml"],
```

## Important security notes
This is a learning project, not production-ready HR software. Before real use, add email verification, rate limiting, CSRF protection, account recovery, privacy controls, and a review of local employment/privacy requirements. The skill vocabulary is predefined and matching is not a hiring decision.
