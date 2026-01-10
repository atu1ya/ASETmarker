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

## Deployment & Handover

This section covers production deployment to **Azure Web App for Containers** with automated CI/CD via GitHub Actions.

### Prerequisites

Before deployment, ensure you have:

- An **Azure subscription** with appropriate permissions
- **Azure CLI** installed and authenticated (`az login`)
- A **GitHub repository** with this codebase
- Administrative access to configure **GitHub Secrets**

### Azure Resource Setup

#### 1. Create an Azure Container Registry (ACR)

```bash
# Set variables
RESOURCE_GROUP="asetmarker-rg"
LOCATION="eastus"
ACR_NAME="asetmarkeracr"  # Must be globally unique, lowercase alphanumeric only

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create container registry
az acr create --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true
```

#### 2. Create an Azure Web App for Containers

```bash
# Set variables
APP_SERVICE_PLAN="asetmarker-plan"
WEBAPP_NAME="asetmarker-webapp"  # Must be globally unique

# Create App Service Plan (Linux)
az appservice plan create --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --is-linux \
  --sku B1

# Create Web App
az webapp create --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $WEBAPP_NAME \
  --deployment-container-image-name $ACR_NAME.azurecr.io/asetmarker:latest
```

#### 3. Configure Web App Environment Variables

The application requires several environment variables from `web/config.py`:

```bash
# Configure application settings
az webapp config appsettings set --resource-group $RESOURCE_GROUP \
  --name $WEBAPP_NAME \
  --settings \
    SECRET_KEY="<generate-a-secure-random-key>" \
    STAFF_PASSWORD="<your-production-password>" \
    DEBUG="False" \
    SESSION_DURATION_HOURS="8" \
    MAX_UPLOAD_SIZE_MB="50" \
    PORT="8000"
```

**Required Environment Variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Session signing key (use strong random string) | `openssl rand -hex 32` |
| `STAFF_PASSWORD` | Shared authentication password | `YourSecurePassword123!` |
| `DEBUG` | Enable debug mode (set to `False` in production) | `False` |
| `SESSION_DURATION_HOURS` | Session lifetime in hours | `8` |
| `MAX_UPLOAD_SIZE_MB` | Maximum file upload size | `50` |
| `PORT` | Container port (Azure uses 8000 by default) | `8000` |

**Optional Variables:**
- `ALLOWED_EXTENSIONS`: List of allowed file extensions (defaults to `.png`, `.jpg`, `.jpeg`)

#### 4. Configure Container Registry Connection

```bash
# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)

# Configure Web App to use ACR
az webapp config container set --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_LOGIN_SERVER/asetmarker:latest \
  --docker-registry-server-url https://$ACR_LOGIN_SERVER \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD
```

### GitHub Actions CI/CD Setup

#### 1. Create Azure Service Principal

```bash
# Create service principal with Contributor role
az ad sp create-for-rbac --name "asetmarker-github-actions" \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

Save the entire JSON output - you'll need it for GitHub Secrets.

#### 2. Configure GitHub Secrets

Navigate to your GitHub repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Add the following secrets:

| Secret Name | Value | How to Obtain |
|-------------|-------|---------------|
| `AZURE_CREDENTIALS` | Full JSON output from service principal creation | From step 1 above |
| `REGISTRY_LOGIN_SERVER` | ACR login server URL | `<acr-name>.azurecr.io` |
| `REGISTRY_USERNAME` | ACR admin username | From ACR credentials |
| `REGISTRY_PASSWORD` | ACR admin password | From ACR credentials |
| `WEBAPP_NAME` | Azure Web App name | Your Web App name |

#### 3. Trigger Deployment

The GitHub Actions workflow (`.github/workflows/azure-deploy.yml`) automatically triggers on:
- **Push to `main` branch**: Builds and deploys automatically
- **Manual trigger**: Go to **Actions** → **Build and Deploy to Azure Web App** → **Run workflow**

The workflow performs:
1. Checks out the code
2. Logs in to Azure using service principal credentials
3. Builds the Docker image
4. Pushes image to Azure Container Registry with tags `latest` and `<commit-sha>`
5. Deploys the image to Azure Web App
6. Logs out from Azure

### Monitoring and Logs

#### View Application Logs

```bash
# Stream live logs
az webapp log tail --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP

# Download logs
az webapp log download --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP
```

#### Access the Application

Your application will be available at:
```
https://<webapp-name>.azurewebsites.net
```

### Pre-Deployment Cleanup

Before final handover, remove these files from the repository:

- `zz left to do.md` - Internal notes
- `milestones.md` - Development planning
- `Prompts/` - Development prompts (optional, keep for documentation)
- Any `.env` files - Never commit secrets
- `__pycache__/` directories - Auto-generated (excluded via `.dockerignore`)

These files are already excluded from the Docker build via `.dockerignore`.

### Security Best Practices

1. **Never commit secrets**: Use environment variables and GitHub Secrets
2. **Rotate credentials**: Regularly update `SECRET_KEY` and `STAFF_PASSWORD`
3. **Monitor access**: Review Azure Activity Logs for unauthorized access attempts
4. **Enable HTTPS**: Azure Web Apps provide free SSL certificates
5. **Resource tagging**: Tag Azure resources for cost tracking and management

### Rollback Procedure

If a deployment fails or introduces issues:

```bash
# List previous deployments
az webapp deployment list --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP

# Redeploy a previous image by commit SHA
az webapp config container set --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_LOGIN_SERVER/asetmarker:<previous-commit-sha>
```

### Cost Optimization

- **B1 Basic Plan**: ~$13/month, suitable for development/testing
- **Production**: Consider upgrading to S1 Standard (~$70/month) for auto-scaling
- **ACR Basic**: $5/month for up to 10GB storage

### Support and Maintenance

For ongoing support:
1. Monitor application logs for errors
2. Review Azure metrics for performance issues
3. Keep dependencies updated (`pip list --outdated`)
4. Regularly update base Docker image (`python:3.11-slim`)

---

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
