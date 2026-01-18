# Passkeys / WebAuthn

Passwordless authentication using FIDO2/WebAuthn.

## Overview

Passkeys enable secure, phishing-resistant authentication using:
- Biometrics (fingerprint, face)
- Hardware security keys
- Platform authenticators (Touch ID, Windows Hello)

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "PASSKEYS": {
        "RP_ID": "myapp.com",  # Your domain
        "RP_NAME": "My Application",
        "ORIGIN": "https://myapp.com",
        "CHALLENGE_TIMEOUT": 300,  # 5 minutes
        "ATTESTATION": "none",  # or "direct", "indirect"
        "USER_VERIFICATION": "preferred",  # or "required", "discouraged"
    },
}
```

## PasskeyController

Use the pre-built controller:

```python
from django_matt.auth.passkeys import PasskeyController

api.register_controller(PasskeyController, prefix="/auth/passkeys")

# Provides:
# POST /auth/passkeys/register/begin - Start registration
# POST /auth/passkeys/register/complete - Complete registration
# POST /auth/passkeys/authenticate/begin - Start authentication
# POST /auth/passkeys/authenticate/complete - Complete authentication
# GET /auth/passkeys/ - List user's passkeys
# DELETE /auth/passkeys/{id} - Delete a passkey
```

## Registration Flow

### Backend

```python
from django_matt.auth.passkeys import (
    generate_registration_options,
    verify_registration_response,
)

@api.post("/passkeys/register/begin")
@jwt_required
async def begin_registration(request):
    options = generate_registration_options(request.user)
    return options.model_dump()

@api.post("/passkeys/register/complete")
@jwt_required
async def complete_registration(request, data: RegistrationResponse):
    credential = verify_registration_response(
        user=request.user,
        credential_id=data.credential_id,
        client_data=data.client_data_json,
        attestation_object=data.attestation_object,
        challenge_id=data.challenge_id,
    )
    return {"credential_id": credential.credential_id}
```

### Frontend

```javascript
// Begin registration
const optionsResponse = await fetch("/auth/passkeys/register/begin", {
    method: "POST",
    headers: { "Authorization": `Bearer ${token}` },
});
const options = await optionsResponse.json();

// Create credential
const credential = await navigator.credentials.create({
    publicKey: {
        challenge: base64ToArrayBuffer(options.challenge),
        rp: { id: options.rp_id, name: options.rp_name },
        user: {
            id: base64ToArrayBuffer(options.user_id),
            name: options.user_name,
            displayName: options.user_display_name,
        },
        pubKeyCredParams: options.pub_key_cred_params,
        authenticatorSelection: options.authenticator_selection,
        timeout: options.timeout,
        attestation: options.attestation,
    },
});

// Complete registration
await fetch("/auth/passkeys/register/complete", {
    method: "POST",
    headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
    },
    body: JSON.stringify({
        credential_id: arrayBufferToBase64(credential.rawId),
        client_data_json: arrayBufferToBase64(credential.response.clientDataJSON),
        attestation_object: arrayBufferToBase64(credential.response.attestationObject),
        challenge_id: options.challenge_id,
    }),
});
```

## Authentication Flow

### Backend

```python
from django_matt.auth.passkeys import (
    generate_authentication_options,
    verify_authentication_response,
)

@api.post("/passkeys/authenticate/begin")
async def begin_authentication(request, data: AuthBeginRequest):
    options = generate_authentication_options(email=data.email)
    return options.model_dump()

@api.post("/passkeys/authenticate/complete")
async def complete_authentication(request, data: AuthResponse):
    user, credential = verify_authentication_response(
        credential_id=data.credential_id,
        client_data=data.client_data_json,
        authenticator_data=data.authenticator_data,
        signature=data.signature,
        challenge_id=data.challenge_id,
    )
    return create_token_pair(user)
```

### Frontend

```javascript
// Begin authentication
const optionsResponse = await fetch("/auth/passkeys/authenticate/begin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "user@example.com" }),
});
const options = await optionsResponse.json();

// Get assertion
const assertion = await navigator.credentials.get({
    publicKey: {
        challenge: base64ToArrayBuffer(options.challenge),
        rpId: options.rp_id,
        allowCredentials: options.allow_credentials.map(c => ({
            type: "public-key",
            id: base64ToArrayBuffer(c.id),
        })),
        timeout: options.timeout,
        userVerification: options.user_verification,
    },
});

// Complete authentication
const tokenResponse = await fetch("/auth/passkeys/authenticate/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        credential_id: arrayBufferToBase64(assertion.rawId),
        client_data_json: arrayBufferToBase64(assertion.response.clientDataJSON),
        authenticator_data: arrayBufferToBase64(assertion.response.authenticatorData),
        signature: arrayBufferToBase64(assertion.response.signature),
        challenge_id: options.challenge_id,
    }),
});
const tokens = await tokenResponse.json();
```

## Error Handling

```python
from django_matt.auth.passkeys import (
    PasskeyError,
    PasskeyRegistrationError,
    PasskeyAuthenticationError,
    PasskeyCredentialNotFoundError,
)

@api.post("/passkeys/authenticate/complete")
async def complete_authentication(request, data: AuthResponse):
    try:
        user, credential = verify_authentication_response(...)
        return create_token_pair(user)
    except PasskeyCredentialNotFoundError:
        raise NotFoundAPIError("Passkey not found")
    except PasskeyAuthenticationError as e:
        raise AuthenticationAPIError(f"Authentication failed: {e}")
```

## Managing Passkeys

```python
@api.get("/passkeys")
@jwt_required
async def list_passkeys(request):
    credentials = await PasskeyCredential.objects.filter(
        user=request.user
    ).values("id", "name", "created_at", "last_used")
    return {"passkeys": list(credentials)}

@api.delete("/passkeys/{id}")
@jwt_required
async def delete_passkey(request, id: int):
    deleted, _ = await PasskeyCredential.objects.filter(
        id=id,
        user=request.user,
    ).adelete()
    if not deleted:
        raise NotFoundAPIError("Passkey not found")
    return {"deleted": True}
```

## Browser Support

| Browser | Support |
|---------|---------|
| Chrome | ✅ Full |
| Safari | ✅ Full |
| Firefox | ✅ Full |
| Edge | ✅ Full |

## Security Best Practices

1. **Require user verification** - Use `userVerification: "required"` for sensitive actions
2. **Store challenges securely** - Use server-side storage with expiration
3. **Validate origin** - Ensure requests come from your domain
4. **Keep credentials secure** - Never expose private keys
5. **Support multiple passkeys** - Allow users to register backup authenticators
