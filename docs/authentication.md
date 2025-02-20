# Authentication

## Overview
- JWT
- Passwordless login
    - Email 
    - Magic Link
    - Passkeys
    - WebAuthn


- Ideally I want to build a generic authentication with JWT and sessions and tokens and have a class that handles any specific type of oAuth that a user can bring in and pass necessary parameters for their specified configuration. 
    - Support for multi tenant auth
    - Support for micro services 
    - Support for Passkeys
    - Support for password managers (BitWarden, NordPass, Apple Password Manager, etc)
    - Support for next level type of security auth. idk