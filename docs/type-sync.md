# Type Sync

Type sync is a feature that allows you to keep your TypeScript types and Django models in sync.

Type sync type shit

## Overview
- I want tRPC type of integration with the front end and back end. 
    - When the Django/Pydantic models changes, there should be a way for the front end TypeScript types/interfaces should get updated
        - The back end seed data should update too. 
        - The django-scripts should update 
        - Any necessary documentation/READMEs should automatically update 
            - Update the README.md file of the app it is in
        - There should be notifications or something to say - with this new model update, existing users cannot do X because of this functionality until you fix XYZ. 
    - Or have the option to automatically update it
    - Or have the option to get a message in the console/terminal saying to run X command to keep your models and TypeScript types in sync. Kinda how Django tells you that you have migration files not migrated and you need to run the migrate command. 
    - While the server is running, it should watch the models and the TypeScript types and keep them in sync. 

