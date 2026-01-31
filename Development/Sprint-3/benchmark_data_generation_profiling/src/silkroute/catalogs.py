from __future__ import annotations
import pandas as pd

def build_catalogs() -> dict:
    category_map = {
        "Fashion": {
            "Apparel": ["cotton tshirts", "casual shirts", "denim jeans", "hoodies", "formal trousers"],
            "Footwear": ["running shoes", "casual sneakers", "sandals", "formal leather shoes"],
            "Accessories": ["belts", "wallets", "scarves", "caps"],
        },
        "Electronics": {
            "Smartphones": ["midrange Android phones", "flagship Android devices"],
            "Laptops": ["ultrabooks", "gaming laptops", "business laptops"],
            "Audio devices": ["wireless earbuds", "overear headphones", "Bluetooth speakers"],
            "Consumer accessories": ["power banks", "phone stands", "USB hubs"],
        },
        "Attach & Addons": {
            "Chargers": ["fast chargers", "wireless chargers", "laptop power adapters"],
            "Cases & protection": ["phone cases", "laptop sleeves", "screen protectors"],
            "Extended services": ["warranty extensions", "accidental damage protection"],
        },
    }

    category_attribute_definitions = []

    def add_attr(category, name, atype, required):
        category_attribute_definitions.append({
            "category": category,
            "attribute_name": name,
            "attribute_type": atype,
            "required_flag": bool(required),
        })

    add_attr("Fashion", "material", "text", True)
    add_attr("Fashion", "fit", "text", False)
    add_attr("Fashion", "gender", "text", False)
    add_attr("Fashion", "season", "text", False)

    add_attr("Electronics", "storage_gb", "int", False)
    add_attr("Electronics", "ram_gb", "int", False)
    add_attr("Electronics", "screen_size_in", "float", False)
    add_attr("Electronics", "battery_mah", "int", False)
    add_attr("Electronics", "warranty_months", "int", True)

    add_attr("Attach & Addons", "compatibility", "text", False)
    add_attr("Attach & Addons", "warranty_months", "int", False)

    brands = {
        "Fashion": ["Outfitters", "Khaadi", "Sapphire", "Levis", "Nike", "Adidas"],
        "Electronics": ["Samsung", "Xiaomi", "OPPO", "HP", "Dell", "Lenovo", "Sony", "JBL", "Anker"],
        "Attach & Addons": ["Anker", "Baseus", "Spigen", "Belkin", "Logitech"],
    }

    return {
        "category_map": category_map,
        "category_attribute_definitions": pd.DataFrame(category_attribute_definitions),
        "brands": brands,
    }
