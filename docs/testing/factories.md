# Test Factories

Generate test data with model factories.

## ModelFactory

```python
from django_matt.testing import ModelFactory, Field, LazyAttribute, Sequence

class UserFactory(ModelFactory):
    class Meta:
        model = User

    email = Sequence(lambda n: f"user{n}@example.com")
    first_name = Field("John")
    last_name = Field("Doe")
    password = LazyAttribute(lambda o: make_password("password123"))

# Usage
user = UserFactory.create()
users = UserFactory.create_batch(10)
```

## Data Generators

```python
from django_matt.testing import DataGenerator

gen = DataGenerator(seed=42)

email = gen.email()
name = gen.name()
address = gen.address()
phone = gen.phone_number()
```
