# Django Matt

New Django API framework started Feb 2025.

I want to build my own custom API framework for Django because I feel like it.

v1 is just for me. not meant for mass adoption.

Reasons: 
- I want to learn something new and do a project I've never done before. 
    - This seems like a tough project but I'm looking forward to learning a lot.
- Lots of new Rust based tooling and other tools to enhance Python frameworks.
- I want to build a framework that has the things I need and use and find useful.
    - DX scripts to enhance productivity
    - Mixins to enhance functionality
    - CRUD generation to enhance productivity
    - I want a config folder
        - I want the config folder data to be used as a cleaner more organized way to manage the settings.py file
        - I want to be able to have different settings for different environments.
        - I want to be able to have different settings for different apps.
    - I want a deployment folder
    - I want a docs folder
    - I want a machine learning folder
    - I want a templates folder
    - I want a tests folder
    - I want a utils folder
    - I want a views folder
- I don't really enjoy how settings.py is used in Django. I want to try something different. 
- Inspired by several frameworks and tools: 
    - Django Rest Framework: mixins
    - Django Ninja: fast, newer, easy, flexible, async supported, pydantic supported
    - Django Ninja Extra: extra features to add class based views to Django Ninja
    - FastAPI: fast, can be lightweight and simple or complex
    - FastUI: React and FastAPI minimalistic full stack framework
    - Ruby on Rails: CLI integration, crud generation
        - https://guides.rubyonrails.org/command_line.html
    - [InertiaJS](https://inertiajs.com/): build single page apps with Django
- Built in Authentication and Permissions
    - JWT
    - Passwordless login
        - Email 
        - Magic Link
        - Passkeys
        - WebAuthn
    - OAuth
    - Social Auth
    - Multi tenant
- LLM/AI IDE integration
    - Cursor context files
    - I want others using this framework to have the best experience with LLM/AI IDE integration. 
- tRPC like experience. 
    - I want to sync Pydantic models on the back end and TypeScript interfaces on the front end for end to end type safety.
    - I want to generate the TypeScript interfaces automatically from the Pydantic models.
        - The TypeScript interfaces should be able to be used in the front end
        - There should be a conversion of types casing from Pydantic models to TypeScript interfaces
            - ie: datimetime_created => datetimeCreated
- I want some kind of easy deployment process. 
    - Support for Docker
    - Support for Digital Ocean
    - Support for Fly.io
    - Support for PlanetScale
    - Support for Railway
    - Support for Render
    - Support for AWS

## Features
- [UV](https://docs.astral.sh/uv/) package manager
- [Ruff](https://beta.ruff.rs/) for linting and formatting
- Class based views first class support
- CRUD generation
    - Generate front end and back end code for CRUD operations
- Generate Django models from Pydantic models
- Authentication
    - JWT
    - Passwordless login
        - Email 
        - Magic Link
        - Passkeys
        - WebAuthn
    - API Keys
- Docs
    - OpenAPI and Swagger
- Rate Limiting
- Caching

## Tech Stack

- Python 3.10+
- Django 5.1+


