# Horilla CRM

<div align="center">
  <img src="static/favicon.ico" alt="Horilla CRM Logo" width="64" height="64">
  <h3>Enterprise Customer Relationship Management System</h3>
  <p>A comprehensive CRM solution designed for enterprise-level customer engagement, sales tracking, and business process automation.</p>
  <p><em>Horilla CRM is one of several ERP products built on the <strong>Horilla platform</strong> — shared support apps live under <code>horilla.contrib</code>, and additional ERP modules (e.g. <code>horilla_sales</code>, <code>horilla_purchase</code>) plug into the same foundation alongside CRM and HRMS.</em></p>
</div>

[![License](https://img.shields.io/badge/license-LGPL--2.1-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/django-5.2+-green.svg)](https://djangoproject.com)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://docker.com)

## ✨ Features

### 🏢 **Core CRM Modules**
- **👥 People Management**
  - **Accounts**: Manage companies and organizations with detailed profiles
  - **Contacts**: Individual contact management with relationship tracking
  - **Roles & Permissions**: Granular access control and user management

- **💼 Sales Pipeline**
  - **Leads**: Lead capture, qualification, and nurturing
  - **Opportunities**: Deal tracking with customizable sales stages
  - **Forecasting**: Revenue predictions and sales analytics
  - **Big Deal Alerts**: Automated notifications for high-value opportunities

- **📊 Marketing & Campaigns**
  - **Campaign Management**: Multi-channel campaign creation and tracking
  - **Campaign Analytics**: Performance metrics and ROI analysis
  - **Lead Source Tracking**: Attribution and conversion analysis

- **📅 Activity & Communication**
  - **Activity Tracking**: Meetings, calls, emails, and task management
  - **Calendar Integration**: Unified scheduling and event management
  - **Timeline View**: Chronological activity history
  - **Email Integration**: Built-in email composer with templates

- **📈 Analytics & Reporting**
  - **Interactive Dashboards**: Customizable widgets and charts
  - **Advanced Reports**: Detailed analytics across all modules
  - **Data Export**: CSV, Excel export capabilities
  - **Real-time Notifications**: WebSocket-based live updates

### 🌐 **Technical Features**
- **Multi-language Support**: 25+ languages including English, Arabic, German, French, Korean
- **Multi-currency**: Global currency support with conversion
- **Real-time Updates**: WebSocket integration for live notifications
- **Advanced Search**: Global search across all modules
- **Import/Export**: Bulk data operations with CSV/Excel support
- **Audit Trail**: Complete activity logging and history tracking
- **Responsive Design**: Mobile-friendly interface
- **Dark/Light Themes**: Customizable UI preferences

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (for local development)
- PostgreSQL (recommended for production)

### Option 1: Docker Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/horilla-opensource/horilla-crm.git
   cd horilla-crm
   ```

2. **Configure environment** (optional)
   ```bash
   cp .env.example .env
   # Edit .env file with your settings
   ```

3. **Start development environment**
   ```bash
   make dev
   # or
   docker-compose up --build
   ```

4. **Start production environment**
   ```bash
   make prod
   # or
   docker-compose --profile production up --build -d
   ```

5. **Create superuser**
   ```bash
   make shell
   python manage.py create_horilla_user
   ```

6. **Access the application**
   - Development: http://localhost:8000
   - Production: http://localhost (with nginx)

### Option 2: Local Development

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database**
   ```bash
   python manage.py migrate
   ```

3. **Create superuser**
   ```bash
   python manage.py create_horilla_user
   ```

4. **Run development server**
   ```bash
   python manage.py runserver
   ```

   On start you will see a one-line Horilla loading progress bar, then a banner with
   **Horilla version** (from `horilla.__version__`) instead of Django’s version line.
   See [docs/horilla/utils/startup.md](docs/horilla/utils/startup.md).

## ⬆️ Upgrading from v1.9 to v1.10.0

> Existing users on **Horilla CRM v1.9** must follow these steps once before starting the v1.10.0 server. Migrations alone are **not** enough — the v1.10.0 release renames several app labels (e.g. `horilla_activity` → `activity`, `horilla_core` → `core`), and the `sync_db` management command rewrites the migration history and content-type references to match.

### Step 1 — Pull the latest code

```bash
git pull origin main
pip install -r requirements.txt
```

### Step 2 — Enable the `sync_db` helper app

Open **`horilla/settings/local_settings.py`** and add these two lines:

```python
from horilla.settings.base import INSTALLED_APPS

INSTALLED_APPS.append("sync_db")
```

This registers the one-shot helper app that ships only the `sync_db` management command. It is intentionally kept out of `base.py` so fresh installs never run it.

### Step 3 — Run the sync command

```bash
python3 manage.py sync_db
```

This will:

- Remap legacy app labels in the `django_migrations` table
- Fake-apply the renamed migrations so Django sees the new app names as already-applied
- Update `ContentType` and permission references to point at the new app labels

When the command finishes, your v1.9 database is fully migrated to the v1.10.0 schema. You can optionally remove the two `sync_db` lines from `local_settings.py` afterwards.

### Fresh installation (no v1.9 data)

New installs **do not** need `sync_db`. Just pull the code and run:

```bash
python3 manage.py migrate
```

## 🐳 Docker Configuration

### Available Commands
```bash
make help     # Show all commands
make dev      # Development server
make prod     # Production with nginx
make build    # Build images
make stop     # Stop services
make logs     # View logs
make shell    # Open container shell
make db-shell # Open PostgreSQL shell
make clean    # Clean up
```

### Services
- **Web**: Django app with Uvicorn ASGI server (port 8000)
- **Database**: PostgreSQL 16 (port 5432)
- **Nginx**: Reverse proxy for production (port 80)

### Environment Variables
```bash
# PostgreSQL Database
POSTGRES_DB=horilla_db
POSTGRES_USER=horilla_user
POSTGRES_PASSWORD=horilla_pass

# Django Configuration
DEBUG=1
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000

# Database URL
DATABASE_URL=postgres://horilla_user:horilla_pass@db:5432/horilla_db
```

## 📦 Installation Options

### Debian/Ubuntu Package
```bash
# Install the .deb package
sudo dpkg -i horilla-crm_1.0.0-1_all.deb
sudo apt-get install -f

# Start the service
sudo systemctl start horilla-crm
sudo systemctl enable horilla-crm
```

### Windows Installer
- Download and run the Windows installer from releases
- Supports both manual and service installation
- Includes automatic Python environment setup
- Service integration with Windows Service Manager

## 🏗️ Architecture

### Technology Stack
- **Backend**: Django 5.2+ with Python 3.12+
- **Database**: PostgreSQL (recommended), SQLite (development)
- **Web Server**: Uvicorn ASGI server with WebSocket support
- **Frontend**: HTML5, TailwindCSS, HTMX for dynamic interactions
- **Real-time**: Django Channels for WebSocket communication
- **Task Queue**: APScheduler for background tasks
- **File Storage**: WhiteNoise for static files

### Platform layout — Horilla as a multi-product ERP base

The repository follows a **two-tier package layout**:

- **`horilla/`** — the **platform**. Houses framework-level helpers (`apps`, `db`, `web`, `menu`, `registry`, `shortcuts`, `utils`) plus all shared **support apps** under **`horilla.contrib.<app>`** (`core`, `mail`, `activity`, `notifications`, `dashboard`, `reports`, `automations`, `calendar`, `cadences`, `process`, `keys`, `theme`, `duplicates`, `generics`, `utils`).
- **`horilla_<product>/`** — an **ERP product package**. This repository contains **`horilla_crm/`**; the platform is also the foundation for the existing HRMS product, and future products such as **`horilla_sales`** and **`horilla_purchase`** ship as their own top-level packages on the same platform.

ERP product packages **import from `horilla.contrib`**, never the other way around. Each product keeps its **own app label and table prefix** (`horilla_crm_lead`, future `horilla_sales_order`, …), so products are independently installable and versioned while still sharing one consistent foundation for auth, mail, activity, dashboards, automations, and the rest of the platform features.

### Project Structure
```
horilla-crm/
├── horilla/                    # Django project package
│   ├── settings/               # Environment settings (base/dev/prod)
│   ├── urls/                   # Project URL configuration
│   ├── contrib/                # Shared platform modules
│   │   ├── core/               # Users, roles, settings, org data
│   │   ├── generics/           # Reusable CBVs/forms/filter helpers
│   │   ├── dashboard/          # Dashboard builder and chart components
│   │   ├── activity/           # Activity tracking
│   │   ├── calendar/           # Calendar + Google sync
│   │   ├── mail/               # Outbound/inbound mail integration
│   │   ├── notifications/      # Real-time/user notifications
│   │   ├── automations/        # Event/scheduled automations
│   │   ├── duplicates/         # Duplicate detection and merge
│   │   ├── reports/            # Report definitions and execution
│   │   ├── cadences/           # Sales cadence workflows
│   │   ├── process/            # Approvals and review processes
│   │   ├── keys/               # Keyboard shortcut management
│   │   ├── theme/              # Theme and UI customization
│   │   └── utils/              # Shared utility services
│   ├── auth/                   # Auth layer extensions
│   ├── apps/                   # AppLauncher and app bootstrap helpers
│   ├── db/                     # ORM wrappers/utilities
│   ├── web/                    # HTTP response helpers (horilla.web)
│   ├── menu/                   # Menu registry and builders
│   ├── registry/               # Feature/permission registries
│   ├── shortcuts/              # Shared shortcut helpers
│   └── utils/                  # Core utility modules
├── horilla_crm/                # CRM ERP product (this repository)
│   ├── accounts/               # Company/Account management
│   ├── contacts/               # Contact management
│   ├── leads/                  # Lead management
│   ├── opportunities/          # Deal/Opportunity tracking
│   ├── campaigns/              # Marketing campaigns
│   └── forecast/               # Sales forecasting
# Future ERP product packages plug in alongside horilla_crm at the same level:
#   horilla_sales/              # Quotes, orders, invoicing (planned)
#   horilla_purchase/           # Vendors, POs, GRNs (planned)
├── templates/                  # Global HTML templates
├── static/                     # Static assets
├── media/                      # Uploaded files
├── docker/                     # Docker configuration
├── debian/                     # Debian packaging files
└── windows-installer/          # Windows installer assets
```

## 🔧 Configuration

### Database Configuration

**SQLite (Development)**
```python
DATABASE_URL=sqlite:///db.sqlite3
```

**PostgreSQL (Production)**
```python
DATABASE_URL=postgres://username:password@localhost:5432/horilla_crm
```

**MySQL/MariaDB**
```python
DATABASE_URL=mysql://username:password@localhost:3306/horilla_crm
```

### Email Configuration
```python
# SMTP Settings
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST='smtp.gmail.com'
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER='your-email@gmail.com'
EMAIL_HOST_PASSWORD='your-app-password'
```

### Redis Configuration (Optional)
```python
# For production WebSocket scaling
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

## 🔐 Security Features

- **Role-based Access Control**: Granular permissions system
- **CSRF Protection**: Built-in Django CSRF protection
- **SQL Injection Protection**: Django ORM with parameterized queries
- **XSS Protection**: Template auto-escaping and CSP headers
- **Secure Headers**: Security middleware with HSTS, X-Frame-Options
- **Password Validation**: Strong password requirements
- **Session Security**: Secure session configuration
- **API Rate Limiting**: Built-in rate limiting for API endpoints

### Reporting Security Issues

Do **not** create public GitHub issues for security vulnerabilities. Report privately via [GitHub Private Vulnerability Reporting](https://github.com/cybroodoodev/horillacrm/security/advisories/new) only — see [SECURITY.md](SECURITY.md). We do not triage security reports by email.

## 📊 API & Integrations

### REST API
- RESTful API endpoints for all modules
- Token-based authentication
- Pagination and filtering support
- Swagger/OpenAPI documentation

### Webhook Support
- Outbound webhooks for key events
- Configurable event triggers
- Retry mechanism with exponential backoff

### Import/Export
- CSV import/export for all data
- Excel file support
- Bulk operations API
- Data validation and error reporting

## 🌍 Internationalization

### Supported Languages
- English (en)
- Arabic (ar)
- German (de)
- French (fr)
- Korean (ko)
- Malayalam (ml)
- And 20+ more languages

### Adding New Languages
1. Create translation files from the project root: `python manage.py makemessages -l <language_code>`
   - To update **platform strings only** (under `horilla/`), run from that directory: `cd horilla && python ../manage.py makemessages -l <language_code>`
   - Locale files are written to `horilla/locale/` (see `LOCALE_PATHS` in settings)
2. Translate strings in `.po` files
3. Compile messages: `python manage.py compilemessages`
4. Add language to `ALLOWED_LANGUAGES` in settings

## 📈 Performance Optimization

### Database Optimization
- Database indexing on frequently queried fields
- Query optimization with select_related and prefetch_related
- Connection pooling configuration
- Read replica support

### Caching Strategy
- Template fragment caching
- Database query caching
- Static file caching with long expiry
- Redis caching layer (optional)

### Frontend Optimization
- Minified CSS and JavaScript
- Image optimization and lazy loading
- HTMX for dynamic content without full page reloads
- CDN support for static assets

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test horilla_crm.leads

# Run with coverage
coverage run manage.py test
coverage html
```

### Test Types
- **Unit Tests**: Individual component testing
- **Integration Tests**: Module interaction testing
- **API Tests**: REST API endpoint testing
- **UI Tests**: Frontend functionality testing

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure strong `SECRET_KEY`
- [ ] Set up production database (PostgreSQL)
- [ ] Configure email settings
- [ ] Set up SSL/HTTPS
- [ ] Configure static file serving
- [ ] Set up backup strategy
- [ ] Configure monitoring and logging
- [ ] Set up Redis for caching (optional)
- [ ] Configure firewall and security groups

### Deployment Options

1. **Docker Compose** (Recommended)
   ```bash
   docker-compose --profile production up -d
   ```

2. **Kubernetes**
   - Helm charts available in `/k8s` directory
   - Supports horizontal scaling
   - Includes health checks and rolling updates

3. **Traditional Server**
   - Systemd service files included
   - Nginx configuration templates
   - Debian/Ubuntu package installation

4. **Cloud Platforms**
   - AWS ECS/Fargate ready
   - Google Cloud Run compatible
   - Azure Container Instances support

## 🔍 Monitoring & Logging

### Application Logs
```bash
# View application logs
docker-compose logs -f web

# View database logs
docker-compose logs -f db

# View nginx logs
docker-compose logs -f nginx
```

### Health Checks
- **Application**: `GET /healthz`
- **Database**: Built-in connection monitoring
- **WebSocket**: Real-time connection status

### Metrics Collection
- User activity tracking
- Performance metrics
- Error rate monitoring
- Resource usage statistics

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `python manage.py test`
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Create a Pull Request

### Code Style
- Follow PEP 8 for Python code
- Use Black for code formatting
- Run pylint for code analysis
- Write docstrings for all functions and classes

### Reporting Issues
- Use GitHub Issues for bug reports and feature requests
- Include detailed reproduction steps, environment information, and relevant logs
- **Security vulnerabilities:** do **not** use public issues — see [SECURITY.md](SECURITY.md)

## 📚 Documentation

### User Documentation
- **Admin Guide**: Complete administration documentation
- **User Manual**: End-user feature documentation
- **API Reference**: Complete API documentation
- **Integration Guide**: Third-party integration examples

### Developer Documentation
- **Architecture Guide**: System design and components
- **Contributing Guide**: Development setup and guidelines
- **API Documentation**: REST API reference
- **Deployment Guide**: Production deployment instructions

## 🆘 Support

### Community Support
- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Community Q&A and discussions
- **Documentation**: Comprehensive guides and tutorials

### Enterprise Support
- Professional support available
- Custom development services
- Training and onboarding
- SLA-backed support options

## 📋 System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 20GB
- **OS**: Linux, Windows, macOS
- **Python**: 3.12+
- **Database**: PostgreSQL 12+, MySQL 8.0+, or SQLite 3.x

### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 50GB+ SSD
- **Database**: PostgreSQL 16+
- **Redis**: 6.0+ (for caching)

## 📄 License

This project is licensed under the **GNU Lesser General Public License v2.1 (LGPL-2.1+)** — see the [LICENSE](LICENSE) file for the full text. All Horilla products (the platform, Horilla HRMS, Horilla CRM, and forthcoming ERP modules) ship under the same LGPL-2.1+ license.

## 🙏 Acknowledgments

- Django community for the excellent framework
- All contributors who have helped improve this project
- Open source libraries that make this project possible

---

<div align="center">
  <p>Made with ❤️ by the Horilla team</p>
  <p>
    <a href="https://github.com/horilla-opensource/horilla-crm">GitHub</a> •
    <a href="#documentation">Documentation</a> •
    <a href="#support">Support</a>
  </p>
</div>
