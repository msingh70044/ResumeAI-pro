# ResumeAI Pro 🎯

AI-powered resume checker with admin portal, user authentication, and database storage.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables (optional but recommended)
```bash
# Add your Anthropic API key for real AI analysis
export ANTHROPIC_API_KEY="sk-ant-..."

# Set a secure secret key for sessions
export SECRET_KEY="your-very-secure-random-secret"
```
> Without `ANTHROPIC_API_KEY`, the app uses smart mock analysis for testing.

### 3. Run the Server
```bash
python app.py
```

### 4. Open in Browser
Visit **http://localhost:5000**

---

## Default Credentials

| Role  | Email                  | Password   |
|-------|------------------------|------------|
| Admin | admin@resumeai.pro     | Admin@123  |
| Demo  | demo@resumeai.pro      | Demo@123   |

---

## Pages & Features

| Page         | URL Path    | Description                                      |
|--------------|-------------|--------------------------------------------------|
| Home         | `/`         | Landing page with hero, features, CTA            |
| Features     | `/features` | Detailed feature overview                        |
| Checker      | `/checker`  | Upload resume + AI analysis (login required)     |
| Dashboard    | `/dashboard`| Personal history & score tracking                |
| Admin Portal | `/admin`    | User management, logs, platform stats (admin)    |
| Login        | `/login`    | Email/password authentication                    |
| Register     | `/register` | New account creation                             |

---

## API Endpoints

### Auth
- `POST /api/auth/register` — Create account
- `POST /api/auth/login` — Sign in
- `POST /api/auth/logout` — Sign out
- `GET  /api/auth/me` — Current user info

### Resume
- `POST /api/resume/check` — Analyze resume (multipart/form-data)
- `GET  /api/resume/history` — User's check history

### Admin (admin only)
- `GET  /api/admin/stats` — Platform overview
- `GET  /api/admin/users` — All users
- `GET  /api/admin/logs` — Activity log
- `POST /api/admin/toggle-admin/<id>` — Toggle user admin status

---

## Architecture

```
resume-checker/
├── app.py              # Flask backend (routes, models, AI integration)
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Single-page frontend (HTML + CSS + JS)
└── instance/
    └── resumeai.db     # SQLite database (auto-created)
```

### Database Models
- **User** — id, uid, name, email, hashed_password, is_admin, created_at, last_login
- **ResumeCheck** — id, user_id, filename, job_role, score, ats_score, result_json, created_at
- **ActivityLog** — id, user_id, action, detail, ip_address, created_at

---

## AI Analysis Output
Each resume check returns:
- `overall_score` (0–100)
- `ats_score` — ATS compatibility
- `summary` — Human-readable assessment
- `sections` — Contact, Summary, Experience, Skills, Education scores
- `strengths` — What's working
- `improvements` — Areas to fix
- `keywords_found` / `keywords_missing` — Keyword gap analysis
- `action_items` — Prioritized next steps

---

## Security Notes
- Passwords are bcrypt-hashed (never stored plain)
- Sessions are server-side with 24-hour expiry
- Admin routes require explicit `is_admin=True`
- Change `SECRET_KEY` in production
- For production: use PostgreSQL and add HTTPS
