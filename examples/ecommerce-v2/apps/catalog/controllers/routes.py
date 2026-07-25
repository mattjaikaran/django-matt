from django_matt import DjangoMattAPI

from apps.catalog.schemas import (
    CategorySchema,
    ProductSchema,
    VariantSchema,
)

from .category_controller import CategoryController
from .product_controller import ProductController
from .variant_controller import VariantController


def register_catalog_routes(api: DjangoMattAPI) -> None:
    # --- Categories ---
    api.get(
        "categories",
        tags=["Categories"],
    )(CategoryController.list_categories)

    api.post(
        "categories",
        response_model=CategorySchema,
        status_code=201,
        tags=["Categories"],
    )(CategoryController.create_category)

    api.get(
        "categories/<str:category_id>",
        response_model=CategorySchema,
        tags=["Categories"],
    )(CategoryController.get_category)

    api.patch(
        "categories/<str:category_id>",
        response_model=CategorySchema,
        tags=["Categories"],
    )(CategoryController.update_category)

    api.delete(
        "categories/<str:category_id>",
        tags=["Categories"],
    )(CategoryController.delete_category)

    # --- Products ---
    api.get(
        "products",
        tags=["Products"],
    )(ProductController.list_products)

    api.post(
        "products",
        response_model=ProductSchema,
        status_code=201,
        tags=["Products"],
    )(ProductController.create_product)

    api.get(
        "products/<str:product_id>",
        response_model=ProductSchema,
        tags=["Products"],
    )(ProductController.get_product)

    api.patch(
        "products/<str:product_id>",
        response_model=ProductSchema,
        tags=["Products"],
    )(ProductController.update_product)

    api.delete(
        "products/<str:product_id>",
        tags=["Products"],
    )(ProductController.delete_product)

    # --- Variants ---
    api.get(
        "products/<str:product_id>/variants",
        tags=["Variants"],
    )(VariantController.list_variants)

    api.post(
        "products/<str:product_id>/variants",
        response_model=VariantSchema,
        status_code=201,
        tags=["Variants"],
    )(VariantController.create_variant)

    api.get(
        "products/<str:product_id>/variants/<str:variant_id>",
        response_model=VariantSchema,
        tags=["Variants"],
    )(VariantController.get_variant)

    api.patch(
        "products/<str:product_id>/variants/<str:variant_id>",
        response_model=VariantSchema,
        tags=["Variants"],
    )(VariantController.update_variant)

    api.delete(
        "products/<str:product_id>/variants/<str:variant_id>",
        tags=["Variants"],
    )(VariantController.delete_variant)
