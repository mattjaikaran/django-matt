"""
API documentation views for Django Matt.

Provides Swagger UI and ReDoc interactive documentation.
"""

from django.http import HttpResponse


def get_swagger_ui(
    openapi_url: str = "/openapi.json",
    title: str = "API Documentation",
) -> HttpResponse:
    """
    Generate Swagger UI HTML page.
    
    Args:
        openapi_url: URL to the OpenAPI JSON schema
        title: Page title
    
    Returns:
        HttpResponse with Swagger UI HTML
    """
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin: 0;
            background: #fafafa;
        }}
        .swagger-ui .topbar {{
            display: none;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                url: "{openapi_url}",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true,
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
                displayRequestDuration: true,
                filter: true,
                tryItOutEnabled: true,
            }});
            window.ui = ui;
        }};
    </script>
</body>
</html>
"""
    return HttpResponse(html, content_type="text/html")


def get_redoc(
    openapi_url: str = "/openapi.json",
    title: str = "API Documentation",
) -> HttpResponse:
    """
    Generate ReDoc HTML page.
    
    Args:
        openapi_url: URL to the OpenAPI JSON schema
        title: Page title
    
    Returns:
        HttpResponse with ReDoc HTML
    """
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <redoc spec-url="{openapi_url}"></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""
    return HttpResponse(html, content_type="text/html")


def get_openapi_json(schema: dict) -> HttpResponse:
    """
    Return OpenAPI schema as JSON response.
    
    Args:
        schema: OpenAPI schema dictionary
    
    Returns:
        HttpResponse with JSON content
    """
    import json
    
    # Try to use orjson for faster serialization
    try:
        import orjson
        content = orjson.dumps(schema)
        return HttpResponse(content, content_type="application/json")
    except ImportError:
        pass
    
    content = json.dumps(schema, indent=2)
    return HttpResponse(content, content_type="application/json")
