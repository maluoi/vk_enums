# Vulkan Enum Search

A quick searchable reference for Vulkan enum values!

Visit the site at: [https://maluoi.github.io/vk_enums/](https://maluoi.github.io/vk_enums/)

## Features

- Fuzzy search by enum name
- Search by hex value (e.g., `0x2`, `0x02`, `0x000002`)
- Search by decimal value

## Local use

1. Update the data (fetches latest from Vulkan spec):
```bash
python parse_vk_enums.py
```

2. Test the site locally:
```bash
cd docs
python -m http.server 8000
```