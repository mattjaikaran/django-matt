# Deployment Guide

This React Vite boilerplate can be deployed in two modes:

## 1. Standalone Mode (Default)

Deploy as a standalone Single Page Application (SPA) with its own backend API.

### Environment Variables

Create a `.env.production` file:

```env
VITE_MODE=standalone
VITE_API_BASE_URL=https://your-api-domain.com/api/v1
VITE_API_TIMEOUT=10000
VITE_API_RETRIES=3
VITE_ENABLE_TODOS=true
VITE_ENABLE_NOTIFICATIONS=true
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_DARK_MODE=true
```

### Build and Deploy

```bash
# Install dependencies
bun install

# Build for production
bun run build

# Deploy the dist/ folder to your hosting provider
# (Vercel, Netlify, AWS S3, etc.)
```

### Hosting Providers

#### Vercel

```bash
bun install -g vercel
vercel --prod
```

#### Netlify

```bash
bun install -g netlify-cli
netlify deploy --prod --dir=dist
```

#### AWS S3 + CloudFront

```bash
aws s3 sync dist/ s3://your-bucket-name --delete
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```

## 2. Django SPA Mode

Integrate as a frontend for a Django application using django-ninja or Django REST Framework.

### Django Setup

1. **Install Django and dependencies:**

```bash
pip install django django-ninja django-cors-headers
```

2. **Django settings.py:**

```python
INSTALLED_APPS = [
    # ... other apps
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ... other middleware
]

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
]

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Add React build directory to static files
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'frontend/dist'),
]
```

3. **Django template (base.html):**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="csrf-token" content="{{ csrf_token }}" />
    <title>Your App</title>
    {% load static %}
    <link rel="stylesheet" href="{% static 'assets/index.css' %}" />
  </head>
  <body>
    <div id="root"></div>

    <!-- Django data for React -->
    <script id="django-user-data" type="application/json">
      {{ user_data|safe }}
    </script>

    <script>
      window.__DJANGO_SPA__ = true;
      window.__DJANGO_USER__ = {{ user_data|safe }};
      window.__DJANGO_SETTINGS__ = {
          STATIC_URL: "{{ STATIC_URL }}",
          MEDIA_URL: "{{ MEDIA_URL }}",
          CSRF_TOKEN: "{{ csrf_token }}"
      };
    </script>

    <script src="{% static 'assets/index.js' %}"></script>
  </body>
</html>
```

4. **Django views.py:**

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import json

@login_required
def spa_view(request):
    user_data = {
        'id': request.user.id,
        'email': request.user.email,
        'firstName': request.user.first_name,
        'lastName': request.user.last_name,
        'isActive': request.user.is_active,
    } if request.user.is_authenticated else None

    return render(request, 'spa.html', {
        'user_data': json.dumps(user_data)
    })
```

5. **Django urls.py:**

```python
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('your_api.urls')),
    path('', views.spa_view, name='spa'),
    path('<path:path>', views.spa_view, name='spa_catchall'),
]
```

### React Environment Variables for Django Mode

Create a `.env.production` file:

```env
VITE_MODE=django-spa
VITE_API_BASE_URL=/api/v1
VITE_DJANGO_CSRF_TOKEN_NAME=csrftoken
VITE_DJANGO_STATIC_URL=/static/
VITE_DJANGO_MEDIA_URL=/media/
VITE_DJANGO_API_PREFIX=/api/v1
```

### Build Process for Django

```bash
# Build React app
bun run build

# Copy build files to Django static directory
cp -r dist/* /path/to/your/django/project/static/

# Collect static files
python manage.py collectstatic --noinput
```

### Automated Django Deployment Script

Create `deploy-django.sh`:

```bash
#!/bin/bash

# Build React app
echo "Building React app..."
bun run build

# Copy to Django static directory
echo "Copying files to Django..."
cp -r dist/* ../backend/static/

# Django deployment
cd ../backend
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Deployment complete!"
```

## Docker Deployment

### Standalone Mode Dockerfile

```dockerfile
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN bun ci --only=production

COPY . .
RUN bun run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Django + React Dockerfile

```dockerfile
FROM node:18-alpine as frontend

WORKDIR /app/frontend
COPY package*.json ./
RUN bun ci

COPY . .
RUN bun run build

FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
COPY --from=frontend /app/frontend/dist ./static/

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## Environment-Specific Configuration

The app automatically detects its environment and configures itself accordingly:

- **Standalone**: Uses full API URLs, handles its own authentication
- **Django SPA**: Uses relative URLs, integrates with Django's CSRF protection and user system

## Performance Optimization

### Code Splitting

The app uses React.lazy() for route-based code splitting.

### Bundle Analysis

```bash
bun run build -- --analyze
```

### PWA Support

Add PWA capabilities by installing:

```bash
bun install vite-plugin-pwa
```

## Monitoring and Analytics

### Error Tracking

Integrate with Sentry:

```bash
bun install @sentry/react @sentry/tracing
```

### Analytics

The app includes feature flags for analytics integration.

## Security Considerations

- CSRF protection in Django mode
- Content Security Policy headers
- Secure cookie settings
- API rate limiting
- Input validation and sanitization

## Troubleshooting

### Common Issues

1. **CORS errors in Django mode**: Check CORS_ALLOWED_ORIGINS settings
2. **Static files not loading**: Verify STATIC_URL and collectstatic
3. **API calls failing**: Check CSRF token configuration
4. **Build errors**: Clear node_modules and reinstall dependencies

### Debug Mode

Set `VITE_DEBUG=true` to enable detailed logging.
