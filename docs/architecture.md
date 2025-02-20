# Architecture

- I want the framework to support different architecture ideologies for full stack development 
    - API only Django development 
        - But still support for the templates
        - But main purpose is to return JSON data for a separate front end to consume
    - Django API within a modular monolithic architecture
    - Django API within a monorepo
        - IE - Django API, NextJS web front end, React Native mobile app, Storybook
    - Django API with SPA
        - NextJS/Astro/RemixJS 
        - Vite and React 
        - Svelte/SvelteKit
    - Django API with HTMX
    - Tailwind support

### Setups 
- API only
    - Django API with SPA
        - Django API with NextJS
        - Django API with RemixJS
        - Django API with Astro
        - Django API with React and Vite
        - Django API with SvelteKit
    - Django API with HTMX
    - Django API within a monorepo
    - Django API with Electron
    - Django API with React Native
    - Django API with Swift
    - Django API with Kotlin
    - Django API with Flutter


## Folder Structure
1. Server and Client
    - server
        - django-apps
    - client
        - nextjs app
2. Client in API 
    - Server
        - django-apps
        - client
3. Monorepo
    - server
        - django-apps
    - client
        - nextjs app
    - mobile
        - react native app
    - desktop
        - electron app
    - docs
        - openapi.yaml
        - other documentation


## Setup
- Set up with initial architecture
    - Like what kind of app is this? B2B, B2C, social media, forum, internal facing tool, blank starting with base User with the built in JWT auth credentials setup and magic link. 
        - If it were B2B, it would set up with Organizations interacting with other Organizations and Users being a part of that Org. Also have the option to ask if the Organization needs multiple teams? Do the teams need a hierarchy? Permissions? Or Users can do business with the selling Org. Questions like that pertinent to the foundation of the application architecture. 
    - Could be cool to have eventual support for NLP to generate the initial architecture. 
