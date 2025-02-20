# DX Tools


- DX tools and scripts 
    - CRUD generator/built in mixins like a DRF or kinda how NestJSX/crud library for NestJS
    - Environment variables setup as default. 
    - Generate new secret key and update the environment variable value
    - Database seeding
    - Startapp Extended script 
        - Django-admin startapp command but way better. 
    - Set up templates for blog, forum, e-commerce, blank etc.
    - Somehow using the script I have which runs the command: 
        - python manage.py shell -c "from django.apps import apps; print('\n'.join([f'{model._meta.label}: {model.objects.count()}' for model in apps.get_models() if not model._meta.abstract]))" | cat