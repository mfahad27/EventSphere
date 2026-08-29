# Deployment Guide

## Docker

```bash
docker build -t eventsphere .
docker run --rm -p 5000:5000 eventsphere
```

The app will be reachable at `http://localhost:5000`.

For persistent production data, configure the SQLAlchemy database URI for a managed database and provide a production `SECRET_KEY` through environment configuration before deployment.

## CI

The GitHub Actions workflow at `.github/workflows/ci.yml` installs project dependencies and runs the integration suite on each push and pull request.
