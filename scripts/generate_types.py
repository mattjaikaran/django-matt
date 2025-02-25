import inspect
from django.apps import apps
import typescript


def export_ts_interfaces():
    models = apps.get_models()
    generator = typescript.TypeGenerator()

    for model in models:
        ts_interface = generator.from_django_model(model)
        ts_interface.add_validation_hooks()  # Generates Zod schemas

        output_path = f"frontend/src/types/{model.__name__}.ts"
        ts_interface.write(output_path)

        print(f"Updated {output_path}")


if __name__ == "__main__":
    export_ts_interfaces()
