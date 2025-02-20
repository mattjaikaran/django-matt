# Startapp Extended

## Overview
- Startapp Extended is a command that extends the functionality of the startapp command in Django.
- It allows you to create a new app with the following features:
    - CRUD generator
    - Authentication
    - Documentation
    - Admin updates
    - TypeScript interface generation
    - React component generation
    - Django model generation
    - Pydantic model generation
    - OpenAPI generation
    - Swagger generation

- I want a user to be able to type in the command and have it generate the app with the above features.
- I want to have the folder structure 



## Folder Structure
- apps
    - appname
        - admin
            - __init__.py
            - product_admin.py
            - product_category_admin.py
        - controllers
            - __init__.py
            - product_controller.py
            - product_category_controller.py
        - docs
            - __init__.py
            - README.md
        - migrations
            - __init__.py
        - models
            - __init__.py
            - product.py
            - product_category.py
        - README.md
        - tests
            - __init__.py
        - schemas
            - __init__.py
        - services
            - __init__.py
        - utils
            - __init__.py
        - views
            - __init__.py