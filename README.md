# Nabha TeleCare

A Python Flask + SQLite telemedicine platform for improving healthcare access in rural Nabha, Punjab. This local-first milestone includes a responsive patient experience, doctor directory, database-backed appointment workflow, role-protected dashboards, development OTP API, prescription PDF generation, PWA shell caching, the browser media foundation for WebRTC consultations, and universal Home/Back navigation on every inner page.

## Run locally (macOS/Linux)

```bash
cd telecare-nabha
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open http://localhost:5000.

## Run on Windows PowerShell

```powershell
cd telecare-nabha
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

## Demo credentials

- Patient: `patient@nabha-telecare.local` / `Patient@123`
- Doctor: `doctor@nabha-telecare.local` / `Doctor@123`
- Admin: `admin@nabha-telecare.local` / `Admin@123`

Seed data is created automatically in the absolute project path `instance/telecare.db` and persists between restarts, regardless of the directory from which Flask is launched.

## What is functional now

- Python backend with SQLAlchemy models for users, patients, doctors, OTP verifications, appointments, consultations, prescriptions, medical records, notifications, and audit logs.
- Role-based session authentication for patient, doctor, and admin accounts.
- Role selection at `/role-selection` with separate `/login/patient`, `/login/doctor`, and `/login/admin` experiences; backend role checks remain authoritative and logout returns to role selection.
- Patient registration at `/register`, including validation, secure password hashing, duplicate-email checks, and database persistence.
- Password recovery at `/forgot-password`, using expiring OTP verification and a secure hashed password update.
- Remote consultation requests at `/consult-remotely`, persisted as Pending appointments and visible in the doctor's dashboard.
- Doctor directory with search and specialization filtering.
- Patient appointment creation, status actions, and database-level double-booking prevention.
- Development OTP endpoints (`/api/auth/request-otp`, `/api/auth/verify-otp`). Development responses include the OTP only when `OTP_MODE=development`; production delivery adapters should be added before deployment.
- Doctor/patient dashboards and protected consultation routes.
- Prescription creation API and authorized PDF download.
- Digital Prescriptions workspace at `/prescriptions`: patients can view only their own records; doctors can create and edit prescriptions for their assigned appointments. It includes diagnosis, medicines, dosage, duration, instructions, follow-up date, persistent SQLite storage, PDF download, and browser print actions. The dashboard tile now links to this page.
- Admin management at `/admin/overview`, `/admin/pending-patients`, `/admin/doctors`, `/admin/appointments`, and `/admin/records`, protected by the admin role. Patient approvals, doctor approval/activation, appointment status updates, patient details, and live database statistics use POST-backed actions and real SQLite records. Older databases receive an automatic `approval_status` migration.
- Browser camera/microphone permission and track controls in the consultation room. A production signaling service should connect peers via WebRTC offer/answer and ICE candidates; the room model and notes API are ready for that integration.
- Lightweight service worker caching. It deliberately does not cache private medical responses.
- Every current page has its own actual local MP4 in `static/videos/`, mounted through the reusable `templates/_background_video.html` component with autoplay, muted, loop, playsinline, object-fit cover, dark overlay, and poster fallback behavior. The homepage asset `static/videos/home.mp4` is a compressed, locally served copy of the freely listed Pexels video “A woman in a white coat and a child sitting on a bench” (source: https://www.pexels.com/video/a-woman-in-a-white-coat-and-a-child-sitting-on-a-bench-19665416/). The login page intentionally contains no demo credentials or technical notes. Inner pages use separate optimized local JPEG backgrounds in `static/images/`; only the homepage keeps the moving background video. A request-time database guard protects clean local launches from an empty SQLite file.

## Production configuration

Configure a strong `SECRET_KEY`, PostgreSQL `DATABASE_URL`, SMTP credentials for email OTP, and an SMS provider adapter. Use HTTPS for camera/microphone access. For multi-instance deployment, add Redis or a managed pub/sub layer for Socket.IO/WebRTC signaling. Never log OTPs or cache sensitive medical records in the browser.

## Testing

```bash
pytest -q
```

## Troubleshooting

- If the database is reset, remove `instance/telecare.db` and restart to reseed demo data.
- If video does not load, the interface keeps its readable dark fallback; set a local MP4 source in `VIDEO_URLS` for restricted networks.
- If camera access fails, serve through `localhost` or HTTPS and allow browser permissions.
- If an appointment returns 409, the doctor/time pair is already booked by design.
