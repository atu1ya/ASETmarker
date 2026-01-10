# Pre-Deployment Cleanup Guide

This guide helps you clean up the repository before final handover and deployment.

## Files to Remove

Before committing the final deployment setup, remove these development/internal files:

```bash
# Remove internal planning documents
Remove-Item "zz left to do.md"
Remove-Item "milestones.md"

# Remove development prompts (optional - keep if useful for documentation)
# Remove-Item -Recurse Prompts/

# Ensure no .env files are committed
Remove-Item -Force .env -ErrorAction SilentlyContinue
Remove-Item -Force .env.* -ErrorAction SilentlyContinue
```

## Clean Python Cache

```bash
# Remove all __pycache__ directories and .pyc files
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force | Remove-Item -Force -Recurse
Get-ChildItem -Path . -Include *.pyc,*.pyo -Recurse -Force | Remove-Item -Force
```

## Verify .gitignore

Ensure your `.gitignore` includes:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# Virtual Environment
.venv/
venv/
ENV/

# Environment Variables
.env
.env.*

# IDE
.vscode/
.idea/

# Testing
.pytest_cache/
.coverage

# OS
.DS_Store
Thumbs.db
```

## Update .gitignore

If `.gitignore` doesn't exist or is incomplete, add the above patterns.

## Freeze Dependencies (Optional)

To generate a fully pinned requirements file from your current environment:

```bash
# Activate your virtual environment first
.venv\Scripts\activate

# Generate pinned versions
pip freeze > requirements-frozen.txt
```

**Note:** The current `requirements.txt` uses minimum versions (`>=`) which is acceptable for deployment. Only create `requirements-frozen.txt` if you need exact reproducibility.

## Pre-Commit Checklist

Before pushing to GitHub:

- [ ] Removed `zz left to do.md`
- [ ] Removed `milestones.md`
- [ ] Verified no `.env` files in repository
- [ ] Cleaned all `__pycache__` directories
- [ ] Updated `.gitignore` if needed
- [ ] Tested Docker build locally: `docker build -t asetmarker:test .`
- [ ] Verified application runs in container: `docker run -p 8000:8000 -e SECRET_KEY=test -e STAFF_PASSWORD=test asetmarker:test`
- [ ] Reviewed all GitHub Secrets are configured
- [ ] Updated documentation if needed

## Local Docker Test

Before deploying to Azure, test the production Docker image locally:

```powershell
# Build the production image
docker build -t asetmarker:test .

# Run with environment variables
docker run -p 8000:8000 `
  -e SECRET_KEY="test-secret-key" `
  -e STAFF_PASSWORD="test123" `
  -e DEBUG="False" `
  asetmarker:test

# Test the application at http://localhost:8000
```

## Git Cleanup Commands

```bash
# Check what would be removed (dry run)
git clean -n -d -x

# Actually remove untracked files (BE CAREFUL!)
# git clean -f -d -x

# View what will be committed
git status

# Commit and push
git add .
git commit -m "Production deployment setup"
git push origin main
```

## Deployment Trigger

After pushing to `main`, the GitHub Actions workflow will automatically:
1. Build the Docker image
2. Push to Azure Container Registry
3. Deploy to Azure Web App

Monitor the deployment at: https://github.com/<your-org>/ASETmarker/actions
