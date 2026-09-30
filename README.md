# Pebble Backend

Django REST API for Pebble, an e-commerce portfolio project built by Md. Asifur Rahman. The backend serves a Flutter storefront and a separate Flutter owner app, with PostgreSQL storing the catalog, customer accounts, carts, and orders.

## Features

- Product browsing, search, categories, and collections.
- Account registration, JWT authentication, profiles, and wishlists.
- Shopping carts, coupons, bundle pricing, and order placement.
- Order status history and shipping tracking details.
- Staff APIs for managing products, inventory, orders, and storefront content.

## Stack

Python · Django · Django REST Framework · PostgreSQL · SimpleJWT

The backend and storefront are hosted on Render. The Flutter owner app remains unpublished; its API endpoints require staff authentication.

## Demo and documentation

- [Live storefront](https://pebble-client.onrender.com/)
- [Flutter storefront source](https://github.com/oscarboyq/pebble_client)
- [Backend architecture](docs/PEBBLE_BACKEND_ARCHITECTURE.md)
- [Detailed architecture reference](docs/PEBBLE_BACKEND_ARCHITECTURE_DETAILED.md)

The storefront's visual design is inspired by the [Shopify Pebble theme](https://themes.shopify.com/themes/pebble/presets/pebble). This is an independent portfolio project and is not affiliated with Shopify or the theme's creators.
