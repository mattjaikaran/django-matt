# Framework Development Prompts

## **CRUD Generation**
```cursor
Create a Django viewset with Pydantic schemas for a `{{ModelName}}` model including:
- Async class-based views
- Automatic OpenAPI documentation
- TypeScript interface generation
- JWT authentication
```

## **Type Synchronization**
```cursor
Generate a migration-aware script that:
1. Compares Django model `{{ModelName}}` changes
2. Updates TypeScript interfaces in `frontend/src/types/{{modelName}}.ts`
3. Generates API documentation diffs
```

## **Auth System**
```cursor
Implement a modular auth class supporting:
- Magic links with rate limiting
- WebAuthn passkey integration
- Multi-tenant JWT claims
- OAuth2 provider config validation
```

## **Performance Optimization**
```cursor
Analyze the current endpoint `{{EndpointPath}}` and:
1. Identify ORM query bottlenecks
2. Suggest async Redis caching strategy
3. Propose Rust-accelerated validation
```