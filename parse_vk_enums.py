#!/usr/bin/env python3
"""
Parse Vulkan vk.xml specification and extract enum values.
Outputs enum name, original representation, and decimal value.
"""

import urllib.request
import xml.etree.ElementTree as ET
import re

# URL to the Vulkan vk.xml specification
VK_XML_URL = "https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/main/xml/vk.xml"

def download_vk_xml():
    """Download the vk.xml file from the Vulkan-Docs repository."""
    print("Downloading vk.xml from Vulkan-Docs repository...")
    with urllib.request.urlopen(VK_XML_URL) as response:
        return response.read()

def parse_value(value_str):
    """
    Parse a value string and return (original_repr, decimal_value).
    Handles hex (0x...), decimal, and bitshift operations.
    """
    if not value_str:
        return None, None

    value_str = value_str.strip()

    # Handle hex values
    if value_str.startswith('0x') or value_str.startswith('0X'):
        try:
            decimal_val = int(value_str, 16)
            return value_str, decimal_val
        except ValueError:
            return value_str, None

    # Handle bitshift operations (e.g., "0x00000001 << 2" or "1 << 2")
    if '<<' in value_str:
        try:
            # Evaluate the bitshift expression
            decimal_val = eval(value_str)
            return value_str, decimal_val
        except:
            return value_str, None

    # Handle regular decimal values
    try:
        decimal_val = int(value_str)
        return value_str, decimal_val
    except ValueError:
        # Handle negative values
        if value_str.startswith('-'):
            try:
                decimal_val = int(value_str)
                return value_str, decimal_val
            except ValueError:
                pass
        return value_str, None

def resolve_aliases(enums_data):
    """Resolve all enum aliases to their actual values."""
    # Build a lookup dictionary for quick access
    enum_lookup = {}
    for enum in enums_data:
        if not enum['is_alias']:
            enum_lookup[enum['name']] = enum

    # Resolve aliases - may need multiple passes for chained aliases
    max_iterations = 10
    for _ in range(max_iterations):
        resolved_data = []
        unresolved_count = 0

        for enum in enums_data:
            if enum['is_alias']:
                alias_target = enum.get('alias_target')
                if alias_target and alias_target in enum_lookup:
                    target_enum = enum_lookup[alias_target]
                    resolved_enum = {
                        'enum_type': enum['enum_type'],
                        'name': enum['name'],
                        'original_repr': target_enum['original_repr'],
                        'decimal_value': target_enum['decimal_value'],
                        'is_alias': False
                    }
                    resolved_data.append(resolved_enum)
                    enum_lookup[enum['name']] = resolved_enum
                else:
                    unresolved_count += 1
            else:
                resolved_data.append(enum)

        enums_data = resolved_data
        if unresolved_count == 0:
            break

    return enums_data

def extract_enums(xml_content):
    """Extract all enum values from the vk.xml content."""
    root = ET.fromstring(xml_content)
    enums_data = []

    # Find all <enums> elements (enum groups)
    for enums_elem in root.findall('.//enums'):
        enum_type = enums_elem.get('name', 'Unknown')
        enum_type_attr = enums_elem.get('type', '')

        # Only process enum and bitmask groups (skip constants)
        if enum_type_attr not in ['enum', 'bitmask']:
            continue

        # Find all <enum> elements within this group
        for enum in enums_elem.findall('enum'):
            name = enum.get('name')
            value = enum.get('value')
            bitpos = enum.get('bitpos')
            alias = enum.get('alias')

            if not name:
                continue

            # Skip string constants (they have quoted values)
            if value and (value.startswith('"') or value.startswith("'")):
                continue

            # Handle aliases
            if alias:
                enums_data.append({
                    'enum_type': enum_type,
                    'name': name,
                    'original_repr': f'alias({alias})',
                    'decimal_value': None,
                    'is_alias': True,
                    'alias_target': alias
                })
                continue

            # Handle bitpos (bit position)
            if bitpos:
                try:
                    bit_val = int(bitpos)
                    decimal_val = 1 << bit_val
                    original_repr = f"1 << {bitpos}"
                    enums_data.append({
                        'enum_type': enum_type,
                        'name': name,
                        'original_repr': original_repr,
                        'decimal_value': decimal_val,
                        'is_alias': False
                    })
                except ValueError:
                    pass
                continue

            # Handle regular value (only if it's numeric)
            if value:
                original_repr, decimal_val = parse_value(value)
                # Only add if we successfully parsed a numeric value
                if decimal_val is not None:
                    enums_data.append({
                        'enum_type': enum_type,
                        'name': name,
                        'original_repr': original_repr,
                        'decimal_value': decimal_val,
                        'is_alias': False
                    })

    # Also check for extension enums and feature enums (promoted extensions)
    for extension in root.findall('.//extension') + root.findall('.//feature'):
        ext_name = extension.get('name', '')
        for require in extension.findall('require'):
            for enum in require.findall('enum'):
                name = enum.get('name')
                value = enum.get('value')
                bitpos = enum.get('bitpos')
                offset = enum.get('offset')
                extends = enum.get('extends')
                alias = enum.get('alias')

                if not name:
                    continue

                # Skip string constants
                if value and (value.startswith('"') or value.startswith("'")):
                    continue

                # Handle aliases
                if alias:
                    enums_data.append({
                        'enum_type': extends or 'Extension',
                        'name': name,
                        'original_repr': f'alias({alias})',
                        'decimal_value': None,
                        'is_alias': True,
                        'alias_target': alias
                    })
                    continue

                # Handle offset-based values (extension enum values)
                if offset and extends:
                    try:
                        # Check for extnumber on the enum itself first, then fall back to extension number
                        extnumber = enum.get('extnumber')
                        if extnumber:
                            ext_number = int(extnumber)
                        else:
                            ext_number = int(extension.get('number', 0))

                        offset_val = int(offset)
                        # Formula from Vulkan spec for extension enum values
                        base = 1000000000
                        range_size = 1000
                        decimal_val = base + (ext_number - 1) * range_size + offset_val

                        # Check for negative flag
                        if enum.get('dir') == '-':
                            decimal_val = -decimal_val

                        # Show the calculated value as the original representation
                        original_repr = str(decimal_val)
                        enums_data.append({
                            'enum_type': extends,
                            'name': name,
                            'original_repr': original_repr,
                            'decimal_value': decimal_val,
                            'is_alias': False
                        })
                    except ValueError:
                        pass
                    continue

                # Handle bitpos
                if bitpos and extends:
                    try:
                        bit_val = int(bitpos)
                        decimal_val = 1 << bit_val
                        original_repr = f"1 << {bitpos}"
                        enums_data.append({
                            'enum_type': extends,
                            'name': name,
                            'original_repr': original_repr,
                            'decimal_value': decimal_val,
                            'is_alias': False
                        })
                    except ValueError:
                        pass
                    continue

                # Handle regular value (only if it extends an enum type)
                if value and extends:
                    original_repr, decimal_val = parse_value(value)
                    # Only add if we successfully parsed a numeric value
                    if decimal_val is not None:
                        enums_data.append({
                            'enum_type': extends,
                            'name': name,
                            'original_repr': original_repr,
                            'decimal_value': decimal_val,
                            'is_alias': False
                        })

    # Resolve all aliases
    enums_data = resolve_aliases(enums_data)

    return enums_data

def write_enums_to_file(enums_data, output_file='vk_enums.csv'):
    """Write enum data to a CSV file."""
    print(f"Writing {len(enums_data)} enum entries to {output_file}...")

    # Sort: VkResult enums (errors and success codes) first, then alphabetically
    def sort_key(enum):
        name = enum['name']
        enum_type = enum.get('enum_type', '')

        # Priority ordering:
        # 0: VkResult (all error and success codes)
        # 1: Everything else
        priority = 0 if enum_type == 'VkResult' else 1

        return (priority, name)

    sorted_enums = sorted(enums_data, key=sort_key)

    with open(output_file, 'w') as f:
        # Write CSV header
        f.write("enum_name,original_repr,decimal_value\n")

        for enum_data in sorted_enums:
            name = enum_data['name']
            original = enum_data['original_repr'] or ''
            decimal = str(enum_data['decimal_value']) if enum_data['decimal_value'] is not None else ''

            f.write(f"{name},{original},{decimal}\n")

    print(f"Done! Enum values written to {output_file}")

def main():
    """Main function to download, parse, and save enum data."""
    try:
        # Download vk.xml
        xml_content = download_vk_xml()

        # Parse enums
        print("Parsing enum values...")
        enums_data = extract_enums(xml_content)

        # Write to docs/data folder for the website
        write_enums_to_file(enums_data, 'docs/data/vk_enums.csv')

        print(f"Total enums extracted: {len(enums_data)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
