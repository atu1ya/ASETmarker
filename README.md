git clone https://github.com/Udayraj123/OMRChecker
# ASET Marking System

Modern FastAPI web tooling for Everest Tutoring's ASET exam workflow. This milestone replaces the legacy "OMRChecker" README with documentation for the new web layer that sits on top of the existing OCR/OMR core in `src/`.

The goal for Milestone 0 was to stand up a complete, testable scaffold: authentication, configuration upload, single-student processing, batch processing, templated UI, Docker support, and a pytest suite. The OMR/analysis/reporting services are stubbed today but expose the interfaces that later milestones will connect to the production engine.

---

## Highlights

- FastAPI 0.111.x application with session middleware, error handling, and Jinja2 templating.
- Upload-driven configuration (answer keys + concept mapping) stored per staff session.
- Single student and batch processing flows with ZIP/PDF/JSON outputs (stubbed today for predictable tests).
- Responsive vanilla CSS UI, reusable components, and progressive-enhancement JavaScript.
- Pytest coverage for auth, routes, and stub services.
- Dockerfile + docker-compose for consistent local spins.
- Extensive sample assets under `docs/` to exercise the upload workflows.

---

## Repository Layout

```
├── src/                 # Original OMR engine (untouched in this milestone)
├── web/
│   ├── app.py           # FastAPI entrypoint and middleware wiring
│   ├── routes/          # Auth, dashboard, single, and batch routers
│   ├── services/        # Stubbed marker/analysis/report/annotator services
│   ├── templates/       # Jinja2 base layout, components, and pages
│   ├── static/          # CSS + JS assets
│   └── session_store.py # In-memory config state per authenticated session
├── tests/               # Pytest suite covering milestone functionality
├── scripts/             # Helper CLIs (setup_env, dev runner, template measurer)
├── docs/                # Sample manifests, answer keys, concept maps
├── requirements*.txt    # Runtime and dev dependencies
├── docker-compose.yml   # Local container orchestration
└── README.md            # You are here
```

---

## Prerequisites

- Python 3.10 or newer (3.11 recommended)
- pip 21+
- (Optional) Docker Desktop if you prefer containers

---

## Quick Start (local Python)

1. **Clone and enter the repo**

	```bash
	git clone https://github.com/<your-org>/ASETmarker.git
	cd ASETmarker
	```

2. **Create a virtual environment** (example using `venv`)

	```bash
	python -m venv .venv
	.venv\Scripts\activate  # Windows
	# source .venv/bin/activate  # macOS / Linux
	```

3. **Install dependencies**

	```bash
	pip install --upgrade pip
	pip install -r requirements.txt
	```

4. **Create a `.env` file** (auto-generate with helper script)

	```bash
	python scripts/setup_env.py
	```

	The default `.env` contains a random `SECRET_KEY`, a shared demo password (`everest2024`), and enables debug mode.

5. **Run the development server**

	```bash
	python scripts/run_dev.py
	# or uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
	```

6. **Visit the UI**

	Open <http://localhost:8000> in your browser. Use the staff password from `.env` to sign in.

---

## Quick Start (Docker Compose)

```bash
docker compose up --build
```

The service becomes available on <http://localhost:8000>. Stop with `Ctrl+C` and `docker compose down`.

---

## Using the Web App

1. **Log in** with the staff password (`everest2024` by default).
2. **Upload configuration**
	- Reading answer key (`.txt` or `.csv`)
	- QR/AR answer key (`.txt` or `.csv`)
	- Concept mapping (`.json`)
	- Sample files live under `docs/`.
3. **Choose a mode**
	- *Single Student*: supply student name, writing score, and two PNG scans.
	- *Batch Processing*: upload a manifest JSON plus a ZIP archive of PNG scans.
4. **Download results**
	- The current milestone returns deterministic placeholder PDFs/JSON/ZIPs so the UI flow and tests are verifiable. Later milestones will integrate the real OMR engine.

Configuration is stored in-memory per authenticated session; restarting the app or clearing cookies resets it.

---

## Running Tests

```bash
pytest
```

The suite exercises authentication, configuration, single/batch routes, and service stubs. Add new tests alongside the feature you introduce (`tests/`).

---

## Development Tips

- **Code style**: follow `black` (88 char line length) and add focused docstrings/comments only when they unblock comprehension.
- **Environment variables**: extend `web/config.py`'s `Settings` dataclass, then surface defaults via `.env` or runtime env vars.
- **Static assets**: keep CSS/JS under `web/static/`; use existing patterns for flash messages and file input widgets.
- **Templates**: share structure through `web/templates/base.html` and the components in `web/templates/components/`.
- **Services**: all domain operations hang off the stub classes in `web/services/`. Replace placeholder logic with real implementations in future milestones without breaking the HTTP surface area.

---

## Roadmap

Milestone 0 delivered the scaffolding. Upcoming milestones will:

1. Integrate the `src/` OMR engine into the FastAPI services.
2. Generate true annotated PDFs and rich analysis reports.
3. Persist configuration and results (database/Blob storage).
4. Harden authentication and introduce granular permissions.
5. Add CI/CD, infrastructure-as-code, and deployment automation.

---

## Contributing

1. Fork + branch (`git checkout -b feature/my-change`).
2. Keep changes focused; update or add tests.
3. Run `pytest` before opening a PR.
4. Submit a pull request describing the problem, solution, and test coverage.

See `CONTRIBUTING.md` for additional project conventions.

---

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
